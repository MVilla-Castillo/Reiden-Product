"""
crm/tests/test_oidc.py — Tests para el middleware OIDC (Google only).
"""

import base64
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import Client, override_settings

from crm.models import AppUser, Tenant


def _b64url(n: int) -> str:
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _generate_key_pair():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()
    return private_key, public_key


PRIVATE_KEY, PUBLIC_KEY = _generate_key_pair()


def _make_google_token(
    kid: str = "test-kid-001",
    sub: str = "google-sub-123",
    exp_offset: int = 3600,
    issuer: str = "https://accounts.google.com",
) -> str:
    payload = {
        "iss": issuer,
        "sub": sub,
        "aud": "test-client-id.apps.googleusercontent.com",
        "exp": int(time.time()) + exp_offset,
        "iat": int(time.time()),
        "email": "testuser@gmail.com",
    }
    private_pem = PRIVATE_KEY.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jwt.encode(
        payload,
        private_pem,
        algorithm="RS256",
        headers={"kid": kid},
    )


GOOGLE_JWKS = {
    "keys": [
        {
            "kty": "RSA",
            "kid": "test-kid-001",
            "n": _b64url(PUBLIC_KEY.public_numbers().n),
            "e": _b64url(PUBLIC_KEY.public_numbers().e),
        }
    ]
}


@pytest.fixture
def mock_jwks_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests

    class FakeResponse:
        def json(self):
            return GOOGLE_JWKS

        def raise_for_status(self):
            pass

    def fake_get(url, timeout=5):
        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)


@pytest.fixture
def oidc_user(db, tenant: Tenant) -> AppUser:
    return AppUser.objects.create(
        email="testuser@gmail.com",
        oidc_sub="google-sub-123",
        oidc_issuer="https://accounts.google.com",
        tenant=tenant,
        role=AppUser.Role.SALESPERSON,
        is_active=True,
    )


@pytest.mark.django_db
@override_settings(
    OIDC_GOOGLE_ISSUER="https://accounts.google.com",
    OIDC_GOOGLE_AUDIENCE="test-client-id.apps.googleusercontent.com",
)
def test_oidc_bypass_dev_mode(client: Client, tenant: Tenant) -> None:
    with override_settings(DEBUG=True):
        response = client.get("/api/dashboard/leads/")

    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(
    OIDC_GOOGLE_ISSUER="https://accounts.google.com",
    OIDC_GOOGLE_AUDIENCE="test-client-id.apps.googleusercontent.com",
)
def test_oidc_no_token_returns_401(client: Client) -> None:
    with override_settings(DEBUG=False):
        response = client.get("/api/dashboard/leads/")

    assert response.status_code == 401
    data = response.json()
    assert "Token no proveído" in data["detail"]


@pytest.mark.django_db
@override_settings(
    OIDC_GOOGLE_ISSUER="https://accounts.google.com",
    OIDC_GOOGLE_AUDIENCE="test-client-id.apps.googleusercontent.com",
)
def test_oidc_unsupported_issuer_returns_401(client: Client) -> None:
    token = jwt.encode(
        {
            "iss": "https://sts.windows.net/fake",
            "sub": "fake-sub",
            "aud": "test-client-id.apps.googleusercontent.com",
            "exp": int(time.time()) + 3600,
        },
        PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": "test-kid-001"},
    )
    with override_settings(DEBUG=False):
        response = client.get(
            "/api/dashboard/leads/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    assert response.status_code == 401
    assert "Issuer no soportado" in response.json()["detail"]


@pytest.mark.django_db
@override_settings(
    OIDC_GOOGLE_ISSUER="https://accounts.google.com",
    OIDC_GOOGLE_AUDIENCE="test-client-id.apps.googleusercontent.com",
)
def test_oidc_expired_token_returns_401(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    import jwt as pyjwt

    original_decode = pyjwt.decode

    def fake_decode(*args, **kwargs):
        raise pyjwt.ExpiredSignatureError("Token has expired")

    monkeypatch.setattr(pyjwt, "decode", fake_decode)

    token = jwt.encode(
        {
            "iss": "https://accounts.google.com",
            "sub": "google-sub-123",
            "aud": "test-client-id.apps.googleusercontent.com",
            "exp": int(time.time()) + 3600,
        },
        PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": "test-kid-001"},
    )
    with override_settings(DEBUG=False):
        response = client.get(
            "/api/dashboard/leads/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    assert response.status_code == 401
    assert "Token expirado" in response.json()["detail"]


@pytest.mark.django_db
@override_settings(
    OIDC_GOOGLE_ISSUER="https://accounts.google.com",
    OIDC_GOOGLE_AUDIENCE="test-client-id.apps.googleusercontent.com",
)
def test_oidc_public_paths_bypass(client: Client) -> None:
    response = client.get("/health/liveness")
    assert response.status_code == 200

    response = client.get("/health/readiness")
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(
    OIDC_GOOGLE_ISSUER="https://accounts.google.com",
    OIDC_GOOGLE_AUDIENCE="test-client-id.apps.googleusercontent.com",
)
def test_oidc_malformed_token_missing_kid(client: Client) -> None:
    token = jwt.encode(
        {
            "iss": "https://accounts.google.com",
            "sub": "google-sub-123",
            "aud": "test-client-id.apps.googleusercontent.com",
            "exp": int(time.time()) + 3600,
        },
        PRIVATE_KEY,
        algorithm="RS256",
    )
    with override_settings(DEBUG=False):
        response = client.get(
            "/api/dashboard/leads/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    assert response.status_code == 401
    assert "kid faltante" in response.json()["detail"]
