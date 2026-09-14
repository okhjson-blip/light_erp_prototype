import base64
import json


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def test_token_is_three_part_jwt(tokens):
    token = tokens["admin"]["Authorization"].split(" ", 1)[1]
    parts = token.split(".")
    assert len(parts) == 3


def test_header_alg_typ(tokens):
    token = tokens["admin"]["Authorization"].split(" ", 1)[1]
    header_b64 = token.split(".")[0]
    header = json.loads(_b64url_decode(header_b64))
    assert header["alg"] == "HS256"
    assert header["typ"] == "JWT"


def test_payload_claims(tokens):
    token = tokens["admin"]["Authorization"].split(" ", 1)[1]
    payload_b64 = token.split(".")[1]
    payload = json.loads(_b64url_decode(payload_b64))
    assert payload["typ"] == "access"
    assert "sub" in payload
    assert "iat" in payload
    assert "exp" in payload
    assert "jti" in payload
    # v5: access token은 완전 무상태라 roles까지 payload에 담아 DB 조회 없이 검증한다.
    assert "roles" in payload
    assert "name" in payload
    assert "email" in payload


def test_tampered_signature_rejected(client, tokens):
    token = tokens["admin"]["Authorization"].split(" ", 1)[1]
    header_b64, payload_b64, sig_b64 = token.split(".")
    bad_sig = sig_b64[:-1] + ("A" if sig_b64[-1] != "A" else "B")
    bad_token = f"{header_b64}.{payload_b64}.{bad_sig}"
    r = client.get("/api/materials", headers={"Authorization": f"Bearer {bad_token}"})
    assert r.status_code == 401


def test_tampered_payload_rejected(client, tokens):
    token = tokens["admin"]["Authorization"].split(" ", 1)[1]
    header_b64, payload_b64, sig_b64 = token.split(".")
    payload = json.loads(_b64url_decode(payload_b64))
    payload["sub"] = 999999
    tampered_payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()
    bad_token = f"{header_b64}.{tampered_payload_b64}.{sig_b64}"
    r = client.get("/api/materials", headers={"Authorization": f"Bearer {bad_token}"})
    assert r.status_code == 401


def test_malformed_token_rejected(client):
    r = client.get("/api/materials", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


# ---------- v5: Access+Refresh 이중 토큰 (완전 무상태 전환) ----------
# 아래 테스트는 세션-스코프 tokens fixture를 공유하면 다른 테스트에 영향을 주므로(로그아웃 등),
# 매번 독립적으로 새 로그인을 수행한다.

def _fresh_login(client, email="sales@standard-erp.local"):
    r = client.post("/api/auth/login", json={"email": email, "password": "demo1234"})
    assert r.status_code == 200, r.text
    return r.json()


def test_refresh_issues_new_access_token(client):
    tokens_body = _fresh_login(client)
    r = client.post("/api/auth/refresh", json={"refresh_token": tokens_body["refresh_token"]})
    assert r.status_code == 200
    new_tokens = r.json()
    assert new_tokens["access_token"] != tokens_body["access_token"]
    ok = client.get("/api/materials", headers={"Authorization": f"Bearer {new_tokens['access_token']}"})
    assert ok.status_code == 200


def test_refresh_rejects_access_token_as_refresh(client):
    tokens_body = _fresh_login(client)
    r = client.post("/api/auth/refresh", json={"refresh_token": tokens_body["access_token"]})
    assert r.status_code == 401


def test_refresh_rejects_unknown_token(client):
    r = client.post("/api/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert r.status_code == 401


def test_logout_blocks_refresh_but_not_existing_access_token(client):
    """완전 무상태화의 의도된 트레이드오프: 로그아웃은 refresh만 즉시 무효화하고,
    이미 발급된 access token은 자연 만료(최대 30분) 전까지 계속 유효하다."""
    tokens_body = _fresh_login(client)
    access, refresh_token = tokens_body["access_token"], tokens_body["refresh_token"]

    logout = client.post("/api/auth/logout", json={"refresh_token": refresh_token})
    assert logout.status_code == 200

    still_valid = client.get("/api/materials", headers={"Authorization": f"Bearer {access}"})
    assert still_valid.status_code == 200

    refresh_after_logout = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_after_logout.status_code == 401


# ---------- v6: Refresh token 회전(rotation) + 재사용 탐지 ----------

def test_refresh_rotates_refresh_token(client):
    """회전: refresh 호출마다 새 refresh_token이 발급되고 이전 것과 달라야 한다."""
    tokens_body = _fresh_login(client)
    r = client.post("/api/auth/refresh", json={"refresh_token": tokens_body["refresh_token"]})
    assert r.status_code == 200
    new_refresh = r.json()["refresh_token"]
    assert new_refresh != tokens_body["refresh_token"]


def test_old_refresh_token_rejected_after_rotation(client):
    """회전 후 예전(폐기된) refresh_token은 더 이상 통과하지 않는다(재사용 방지)."""
    tokens_body = _fresh_login(client)
    old_refresh = tokens_body["refresh_token"]
    first = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert first.status_code == 200

    reuse = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401


def test_refresh_reuse_invalidates_whole_family(client):
    """탈취 탐지: 폐기된 토큰이 재사용되면 그 로그인에서 파생된 최신(아직 안 쓴) refresh_token까지
    전부 무효화되어야 한다 — 공격자가 훔친 옛 토큰을 쓰면 정상 사용자의 최신 토큰도 함께 잠긴다."""
    tokens_body = _fresh_login(client)
    old_refresh = tokens_body["refresh_token"]
    rotated = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert rotated.status_code == 200
    latest_refresh = rotated.json()["refresh_token"]

    reuse = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401

    latest_now_blocked = client.post("/api/auth/refresh", json={"refresh_token": latest_refresh})
    assert latest_now_blocked.status_code == 401


def test_logout_invalidates_entire_family_not_just_current_token(client):
    """로그아웃은 회전으로 발급된 전체 family를 지운다 — 회전 후의 최신 refresh_token으로도
    로그아웃하면 그 이전에 발급됐던(이미 폐기된) 토큰들도 당연히 못 쓰고, 최신 토큰도 못 쓴다."""
    tokens_body = _fresh_login(client)
    rotated = client.post("/api/auth/refresh", json={"refresh_token": tokens_body["refresh_token"]})
    assert rotated.status_code == 200
    latest_refresh = rotated.json()["refresh_token"]

    logout = client.post("/api/auth/logout", json={"refresh_token": latest_refresh})
    assert logout.status_code == 200

    r = client.post("/api/auth/refresh", json={"refresh_token": latest_refresh})
    assert r.status_code == 401
