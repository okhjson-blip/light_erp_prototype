# Keycloak access token 로컬 검증(JWKS 서명 + azp) 기반 ERP SSO 세션 교환을 검증한다.
# RSA 서명 검증 자체는 test_oidc_verifier.py가 담당한다. 여기서는 검증 결과에 따라 엔드포인트가
# 올바른 상태 코드를 내는지에 집중한다.
import pytest

from app import main
from app.oidc import OidcTokenInvalid, OidcUnavailable


def _accept(claims):
    return lambda token: claims


def _reject(exc):
    def _raise(token):
        raise exc

    return _raise


def test_sso_exchanges_verified_keycloak_user(client, monkeypatch):
    monkeypatch.setattr(
        main, "verify_access_token",
        _accept({"email": "admin@standard-erp.local", "azp": "ax-erp-web", "scope": "openid ax-claims"}),
    )
    response = client.post("/api/auth/sso", headers={"Authorization": "Bearer keycloak-access-token"})
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "admin@standard-erp.local"


def test_sso_rejects_invalid_keycloak_token(client, monkeypatch):
    monkeypatch.setattr(main, "verify_access_token", _reject(OidcTokenInvalid("유효하지 않은 SSO 토큰입니다")))
    response = client.post("/api/auth/sso", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401


def test_sso_rejects_token_issued_to_another_client(client, monkeypatch):
    """azp 검증 회귀 테스트. Realm 내 다른 클라이언트 토큰이 ERP 세션으로 교환되면 안 된다."""
    monkeypatch.setattr(
        main, "verify_access_token",
        _reject(OidcTokenInvalid("이 클라이언트로 발급된 SSO 토큰이 아닙니다")),
    )
    response = client.post("/api/auth/sso", headers={"Authorization": "Bearer platform-web-token"})
    assert response.status_code == 401


def test_sso_rejects_unknown_email(client, monkeypatch):
    monkeypatch.setattr(
        main, "verify_access_token",
        _accept({"email": "nobody@example.com", "azp": "ax-erp-web", "scope": "openid ax-claims"}),
    )
    response = client.post("/api/auth/sso", headers={"Authorization": "Bearer keycloak-access-token"})
    assert response.status_code == 403


def test_sso_requires_bearer_header(client):
    assert client.post("/api/auth/sso").status_code == 401


def test_sso_reports_keycloak_outage_as_503(client, monkeypatch):
    monkeypatch.setattr(main, "verify_access_token", _reject(OidcUnavailable("Keycloak JWKS를 가져올 수 없습니다")))
    response = client.post("/api/auth/sso", headers={"Authorization": "Bearer keycloak-access-token"})
    assert response.status_code == 503


@pytest.mark.parametrize(
    "claims",
    [
        {"azp": "ax-erp-web", "scope": "openid ax-claims"},
        {"email": "", "azp": "ax-erp-web", "scope": "openid ax-claims"},
    ],
)
def test_sso_requires_email_claim(client, monkeypatch, claims):
    monkeypatch.setattr(main, "verify_access_token", _accept(claims))
    response = client.post("/api/auth/sso", headers={"Authorization": "Bearer keycloak-access-token"})
    assert response.status_code == 401
