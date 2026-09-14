"""Keycloak access token 로컬 검증 — JWKS 서명 + iss/exp/azp 확인.

설계 결정(2026-07-31 SSO 리뷰 P0-2): userinfo 호출만으로는 "Realm 안의 어떤 클라이언트가 발급한
토큰이든" ERP 도메인 세션으로 교환되는 confused deputy 문제가 있었다. userinfo 응답에는 azp가
없으므로 access token 자체를 검증해 발급 대상까지 확인한다.

- 서명: Keycloak JWKS(RS256)를 받아 kid로 매칭. 응답은 프로세스 내 캐시(TTL), 모르는 kid가 오면 1회 강제 갱신.
- 클레임: iss(정확 일치), exp/nbf(PyJWT), azp(허용 클라이언트 목록에 포함)를 확인한다.
- aud는 Keycloak 공개 클라이언트에서 관례적으로 "account"가 되므로 검증하지 않고 azp로 대체한다.
"""
import os
import threading
import time

import httpx
import jwt
from jwt import PyJWKClient

_JWKS_TTL_SECONDS = 300
_HTTP_TIMEOUT_SECONDS = 5.0

_lock = threading.Lock()
_jwks_client: PyJWKClient | None = None
_jwks_loaded_at = 0.0
_jwks_issuer = ""


class OidcConfigurationError(RuntimeError):
    """검증에 필요한 설정이 잘못된 경우."""


class OidcUnavailable(RuntimeError):
    """Keycloak JWKS를 가져오지 못한 경우 — 503으로 매핑한다."""


class OidcTokenInvalid(ValueError):
    """토큰 서명/클레임 검증 실패 — 401로 매핑한다."""


def issuer() -> str:
    return os.environ.get("OIDC_ISSUER", "http://localhost:8081/realms/ax-enterprise").rstrip("/")


def allowed_azp() -> set[str]:
    raw = os.environ.get("OIDC_ALLOWED_AZP", "ax-erp-web")
    values = {item.strip() for item in raw.split(",") if item.strip()}
    if not values:
        raise OidcConfigurationError("OIDC_ALLOWED_AZP가 비어 있습니다")
    return values


def _client(force_refresh: bool = False) -> PyJWKClient:
    """JWKS 클라이언트를 TTL 캐시로 재사용한다. issuer가 바뀌면 캐시를 버린다."""
    global _jwks_client, _jwks_loaded_at, _jwks_issuer
    current_issuer = issuer()
    with _lock:
        expired = (time.monotonic() - _jwks_loaded_at) > _JWKS_TTL_SECONDS
        if force_refresh or _jwks_client is None or expired or _jwks_issuer != current_issuer:
            try:
                _jwks_client = PyJWKClient(
                    f"{current_issuer}/protocol/openid-connect/certs",
                    cache_keys=False,
                    timeout=_HTTP_TIMEOUT_SECONDS,
                )
                # 즉시 1회 조회해 Keycloak 미기동 상태를 401이 아닌 503으로 구분한다.
                _jwks_client.get_signing_keys()
            except Exception as exc:
                _jwks_client = None
                raise OidcUnavailable("Keycloak JWKS를 가져올 수 없습니다") from exc
            _jwks_loaded_at = time.monotonic()
            _jwks_issuer = current_issuer
        return _jwks_client


def reset_cache() -> None:
    """테스트와 설정 변경용 캐시 초기화."""
    global _jwks_client, _jwks_loaded_at, _jwks_issuer
    with _lock:
        _jwks_client = None
        _jwks_loaded_at = 0.0
        _jwks_issuer = ""


def verify_access_token(token: str) -> dict:
    """Keycloak access token을 검증하고 클레임을 반환한다.

    OidcUnavailable(503) / OidcTokenInvalid(401) 중 하나를 던지거나 클레임 dict를 반환한다.
    """
    if not token:
        raise OidcTokenInvalid("SSO 토큰이 비어 있습니다")

    def decode(force_refresh: bool) -> dict:
        signing_key = _client(force_refresh).get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer(),
            options={"verify_aud": False, "require": ["exp", "iss"]},
        )

    try:
        claims = decode(force_refresh=False)
    except OidcUnavailable:
        raise
    except jwt.PyJWKClientError:
        # 키 회전 직후에는 캐시에 없는 kid가 올 수 있다. 1회만 강제 갱신 후 재시도한다.
        try:
            claims = decode(force_refresh=True)
        except OidcUnavailable:
            raise
        except Exception as exc:
            raise OidcTokenInvalid("SSO 토큰 서명을 확인할 수 없습니다") from exc
    except jwt.InvalidTokenError as exc:
        raise OidcTokenInvalid("유효하지 않은 SSO 토큰입니다") from exc

    azp = claims.get("azp")
    if azp not in allowed_azp():
        raise OidcTokenInvalid("이 클라이언트로 발급된 SSO 토큰이 아닙니다")

    scope = claims.get("scope", "")
    if "openid" not in scope.split():
        raise OidcTokenInvalid("openid scope가 없는 SSO 토큰입니다")

    return claims


def fetch_userinfo(token: str) -> dict:
    """서명 검증을 통과한 토큰에 한해 userinfo로 최신 프로필을 보강한다(선택 경로)."""
    try:
        response = httpx.get(
            f"{issuer()}/protocol/openid-connect/userinfo",
            headers={"Authorization": f"Bearer {token}"},
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise OidcUnavailable("SSO 사용자 정보를 확인할 수 없습니다") from exc
    if response.status_code != 200:
        raise OidcTokenInvalid("유효하지 않은 SSO 토큰입니다")
    return response.json()
