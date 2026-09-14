# app/oidc.py의 Keycloak access token 검증을 실제 RSA 키로 검증한다.
# 서명·iss·exp·azp·openid scope 중 하나라도 어긋나면 거부되어야 한다.
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app import oidc

ISSUER = "http://localhost:8081/realms/ax-enterprise"
KID = "test-key-1"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_token(**overrides):
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "sub": "user-1",
        "email": "admin@standard-erp.local",
        "azp": "ax-erp-web",
        "scope": "openid ax-claims",
        "exp": now + 300,
        "iat": now,
    }
    claims.update(overrides)
    return jwt.encode(claims, _private_key, algorithm="RS256", headers={"kid": KID})


@pytest.fixture(autouse=True)
def _local_jwks(monkeypatch):
    """PyJWKClient를 우회해 테스트 키로 서명 검증이 이뤄지도록 한다."""
    monkeypatch.setenv("OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("OIDC_ALLOWED_AZP", "ax-erp-web")
    oidc.reset_cache()

    class _Key:
        key = _private_key.public_key()

    class _Client:
        def get_signing_keys(self):
            return [_Key()]

        def get_signing_key_from_jwt(self, token):
            header = jwt.get_unverified_header(token)
            if header.get("kid") != KID:
                raise jwt.PyJWKClientError("unknown kid")
            return _Key()

    monkeypatch.setattr(oidc, "PyJWKClient", lambda *args, **kwargs: _Client())
    yield
    oidc.reset_cache()


def test_accepts_valid_token():
    claims = oidc.verify_access_token(make_token())
    assert claims["email"] == "admin@standard-erp.local"


def test_rejects_token_from_another_client():
    with pytest.raises(oidc.OidcTokenInvalid):
        oidc.verify_access_token(make_token(azp="ax-platform-web"))


def test_rejects_token_without_openid_scope():
    with pytest.raises(oidc.OidcTokenInvalid):
        oidc.verify_access_token(make_token(scope="ax-claims"))


def test_rejects_expired_token():
    with pytest.raises(oidc.OidcTokenInvalid):
        oidc.verify_access_token(make_token(exp=int(time.time()) - 10))


def test_rejects_wrong_issuer():
    with pytest.raises(oidc.OidcTokenInvalid):
        oidc.verify_access_token(make_token(iss="http://evil.local/realms/other"))


def test_rejects_token_signed_by_unknown_key():
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode({"iss": ISSUER, "exp": int(time.time()) + 300}, other_key,
                       algorithm="RS256", headers={"kid": KID})
    with pytest.raises(oidc.OidcTokenInvalid):
        oidc.verify_access_token(token)


def test_rejects_empty_token():
    with pytest.raises(oidc.OidcTokenInvalid):
        oidc.verify_access_token("")
