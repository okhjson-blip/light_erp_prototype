"""RBAC 인증/인가 — Access+Refresh 이중 토큰 (v5), Refresh 회전+재사용 탐지 (v6, task-plan-refresh-rotation.md).
설계 결정: OAuth2 대신 자체 JWT 구현(hmac/base64/json 표준 라이브러리만 사용, 신규 의존성 없음).

v5 완전 무상태 전환: v4까지는 JWT 포맷이었지만 매 요청마다 세션 테이블을 대조해 사실상 무상태가
아니었다. v5부터 토큰을 두 종류로 분리한다.
- **Access token**: TTL 30분. payload에 sub/name/email/roles를 전부 담아 `current_user()`가
  **DB를 전혀 조회하지 않고** 서명+만료만 검증해 그대로 반환한다 — 매 요청 완전 무상태.
- **Refresh token**: 기존 `session` 테이블을 그대로 재사용. TTL 8시간(로그인 시점 기준 고정 —
  회전해도 연장되지 않음). `POST /api/auth/refresh`로 access token을 재발급받는다.
- **로그아웃**: refresh token이 속한 family 전체를 즉시 삭제해 재발급을 차단한다. 단, 이미 발급된
  access token은 자체 만료(최대 30분)까지 여전히 유효하다 — 완전 무상태화의 명시적 트레이드오프
  (AskUserQuestion에서 사용자가 인지하고 선택, TTL을 짧게 유지해 이 창을 최소화).

v6 refresh 회전(rotation) + 재사용 탐지: `/api/auth/refresh` 호출마다 새 refresh token을 발급하고
기존 토큰은 폐기(`rotated_at` 기록)한다. 이미 폐기된 토큰이 다시 제시되면(탈취 의심) 그 토큰이 속한
family(`family_id`) 전체를 즉시 무효화하고 `RefreshTokenReuseDetected`를 발생시킨다 — 정상 클라이언트는
항상 최신 토큰만 쓰므로, 오래된 토큰의 재등장은 탈취 신호로 간주한다(session 테이블 `family_id`/
`rotated_at` 컬럼, migrations/versions/0002_session_rotation.py).

인가 범위: GET(조회)은 로그인만 하면 역할 무관 가능(v4). v5에서 회계 전표/GL계정/CFO Copilot만
관리자 전용으로 좁혔다(task-plan-v5.md) — 그 외 세부 역할별 조회 제한은 여전히 비범위.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, Header, HTTPException

from .database import get_conn, run, one, rows_to_list

ACCESS_TTL_MINUTES = 30
REFRESH_TTL_HOURS = 8

# JWT 서명 비밀키. 실제 운영 전환 시 환경변수로 반드시 교체할 것(README 참고) — 데모/개발 기본값 사용 중.
JWT_SECRET = os.environ.get("JWT_SECRET", "standard-erp-prototype-dev-secret-change-in-production")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _jwt_encode(payload: dict) -> str:
    header_b64 = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(JWT_SECRET.encode(), f"{header_b64}.{payload_b64}".encode(), hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


def _jwt_verify(token: str) -> dict:
    """서명을 검증하고 payload를 반환한다. 형식 오류/서명 위조 시 None(만료는 호출부에서 별도 확인)."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    header_b64, payload_b64, signature_b64 = parts
    expected_sig = hmac.new(JWT_SECRET.encode(), f"{header_b64}.{payload_b64}".encode(), hashlib.sha256).digest()
    try:
        actual_sig = _b64url_decode(signature_b64)
    except Exception:
        return None
    if not hmac.compare_digest(expected_sig, actual_sig):
        return None
    try:
        return json.loads(_b64url_decode(payload_b64))
    except Exception:
        return None


def hash_password(password: str, salt: str = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    if not stored or "$" not in stored:
        return False
    salt, _ = stored.split("$", 1)
    return secrets.compare_digest(hash_password(password, salt), stored)


def get_user_roles(conn, user_id: int):
    rows = rows_to_list(run(
        conn,
        "SELECT r.name AS name FROM user_role ur JOIN role r ON r.role_id = ur.role_id WHERE ur.user_id=?",
        (user_id,),
    ))
    return [r["name"] for r in rows]


def create_access_token(user_id: int, name: str, email: str, roles: list) -> str:
    """완전 무상태 access token. payload에 필요한 정보를 전부 담아 이후 검증 시 DB 조회가 필요 없다."""
    now = datetime.utcnow()
    return _jwt_encode({
        "typ": "access",
        "sub": user_id,
        "name": name,
        "email": email,
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ACCESS_TTL_MINUTES)).timestamp()),
        "jti": secrets.token_hex(8),
    })


class RefreshTokenReuseDetected(Exception):
    """이미 회전으로 폐기된 refresh token이 다시 제시됨 — 탈취 의심. 호출부(main.py)가 401 응답+로깅한다."""

    def __init__(self, user_id: int, family_id: str):
        self.user_id = user_id
        self.family_id = family_id
        super().__init__(f"refresh token reuse detected: user_id={user_id} family_id={family_id}")


def create_refresh_token(
    conn, user_id: int, family_id: str = None, expires_at: str = None, user_agent: str = None,
) -> str:
    """session 테이블에 refresh token을 저장한다(불투명 JWT, DB 대조 필수).
    family_id/expires_at을 지정하면 회전(같은 family 유지, 만료시각은 로그인 시점 기준 고정)이고,
    지정하지 않으면 새 로그인(새 family, 새 만료시각)이다.
    v8: user_agent(디바이스 식별용 표시 정보)와 last_seen_at(발급/재발급 시각)을 함께 기록해
    세션 관리 UI(GET /api/auth/sessions)에서 "어떤 기기/언제"를 보여줄 수 있게 한다."""
    if family_id is None:
        family_id = secrets.token_hex(16)
    if expires_at is None:
        expires_at = (datetime.utcnow() + timedelta(hours=REFRESH_TTL_HOURS)).isoformat()
    token = _jwt_encode({
        "typ": "refresh",
        "sub": user_id,
        "iat": int(datetime.utcnow().timestamp()),
        "exp": int(datetime.fromisoformat(expires_at).timestamp()),
        "jti": secrets.token_hex(8),
    })
    now = datetime.utcnow().isoformat()
    run(
        conn,
        "INSERT INTO session (token, user_id, expires_at, family_id, user_agent, last_seen_at) "
        "VALUES (?,?,?,?,?,?)",
        (token, user_id, expires_at, family_id, user_agent, now),
    )
    return token


def delete_refresh_token(conn, token: str):
    """토큰이 속한 family 전체를 삭제한다 — 로그아웃은 그 로그인에서 파생된 모든 refresh token
    (회전으로 발급된 이전/이후 토큰 포함)을 무효화하는 게 자연스러운 의미다."""
    sess = one(run(conn, "SELECT family_id FROM session WHERE token=?", (token,)))
    if sess is not None:
        run(conn, "DELETE FROM session WHERE family_id=?", (sess["family_id"],))


def issue_tokens(conn, user_id: int, name: str, email: str, user_agent: str = None) -> dict:
    roles = get_user_roles(conn, user_id)
    return {
        "access_token": create_access_token(user_id, name, email, roles),
        "refresh_token": create_refresh_token(conn, user_id, user_agent=user_agent),
        "roles": roles,
    }


def rotate_tokens(conn, refresh_token: str) -> dict:
    """refresh token을 검증(서명+DB+만료)하고 (신규 access_token, 신규 refresh_token)을 발급한다.
    실패 시 None. 이미 회전으로 폐기된 토큰이 재사용되면 RefreshTokenReuseDetected를 발생시키고
    해당 family 전체를 무효화한다(task-plan-refresh-rotation.md)."""
    payload = _jwt_verify(refresh_token)
    if payload is None or payload.get("typ") != "refresh":
        return None
    sess = one(run(conn, "SELECT * FROM session WHERE token=?", (refresh_token,)))
    if sess is None:
        return None
    if sess["expires_at"] < datetime.utcnow().isoformat():
        run(conn, "DELETE FROM session WHERE family_id=?", (sess["family_id"],))
        return None
    if sess["rotated_at"] is not None:
        run(conn, "DELETE FROM session WHERE family_id=?", (sess["family_id"],))
        raise RefreshTokenReuseDetected(sess["user_id"], sess["family_id"])
    user = one(run(conn, "SELECT user_id, name, email FROM app_user WHERE user_id=?", (sess["user_id"],)))
    if user is None:
        return None
    roles = get_user_roles(conn, user["user_id"])
    new_access = create_access_token(user["user_id"], user["name"], user["email"], roles)
    new_refresh = create_refresh_token(
        conn, user["user_id"], family_id=sess["family_id"], expires_at=sess["expires_at"],
        user_agent=sess["user_agent"],
    )
    run(conn, "UPDATE session SET rotated_at=? WHERE token=?", (datetime.utcnow().isoformat(), refresh_token))
    return {"access_token": new_access, "refresh_token": new_refresh}


def current_user(authorization: str = Header(None)) -> dict:
    """Authorization: Bearer <access_token> 헤더를 검증해 현재 사용자+역할을 반환. 실패 시 401.
    payload에 담긴 정보만으로 반환하며 DB를 조회하지 않는다(완전 무상태) — 로그아웃/역할변경은
    이 access token이 자연 만료(최대 30분)될 때까지 반영되지 않는 게 의도된 트레이드오프다."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "로그인이 필요합니다")
    token = authorization[len("Bearer "):].strip()
    payload = _jwt_verify(token)
    if payload is None:
        raise HTTPException(401, "토큰 서명이 유효하지 않습니다. 다시 로그인하세요")
    if payload.get("typ") != "access":
        raise HTTPException(401, "access token이 아닙니다")
    if payload.get("exp", 0) < datetime.utcnow().timestamp():
        raise HTTPException(401, "토큰이 만료되었습니다. 다시 로그인하거나 토큰을 갱신하세요")
    return {
        "user_id": payload["sub"],
        "name": payload["name"],
        "email": payload["email"],
        "roles": payload["roles"],
    }


def require_roles(*allowed_roles):
    """지정된 역할 중 하나라도 있어야 통과하는 FastAPI dependency를 만든다."""
    def _dep(user: dict = Depends(current_user)) -> dict:
        if not set(user["roles"]) & set(allowed_roles):
            raise HTTPException(403, f"권한이 없습니다 (필요 역할: {', '.join(allowed_roles)})")
        return user
    return _dep
