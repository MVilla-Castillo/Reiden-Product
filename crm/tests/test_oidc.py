"""
crm/tests/test_oidc.py — Tests para el middleware OIDC (Supabase Auth).
"""

import time
from unittest.mock import MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from django.test import Client, override_settings

from crm.models import AppUser, Tenant


TEST_SUPABASE_URL = "https://nviceqkfcntxejybnpzd.supabase.co"
TEST_SUPABASE_ISSUER = f"{TEST_SUPABASE_URL}/auth/v1"

_TEST_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
_TEST_PUBLIC_KEY = _TEST_PRIVATE_KEY.public_key()


@pytest.fixture(autouse=True)
def mock_jwks(monkeypatch):
    mock_signing_key = MagicMock()
    mock_signing_key.key = _TEST_PUBLIC_KEY
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
    monkeypatch.setattr("core.auth.oidc._get_jwks_client", lambda: mock_client)
    import core.auth.oidc as oidc_module

    oidc_module._jwks_client = None
    yield
    oidc_module._jwks_client = None


def _make_supabase_token(
    sub: str = "550e8400-e29b-41d4-a716-446655440000",
    exp_offset: int = 3600,
    issuer: str = TEST_SUPABASE_ISSUER,
) -> str:
    payload = {
        "iss": issuer,
        "sub": sub,
        "aud": "authenticated",
        "exp": int(time.time()) + exp_offset,
        "iat": int(time.time()),
        "email": "testuser@example.com",
    }
    return jwt.encode(payload, _TEST_PRIVATE_KEY, algorithm="ES256")


@pytest.fixture
def oidc_user(db, tenant: Tenant) -> AppUser:
    return AppUser.objects.create(
        email="testuser@example.com",
        oidc_sub="550e8400-e29b-41d4-a716-446655440000",
        oidc_issuer=TEST_SUPABASE_ISSUER,
        tenant=tenant,
        role=AppUser.Role.SALESPERSON,
        is_active=True,
    )


@pytest.mark.django_db
@override_settings(
    SUPABASE_URL=TEST_SUPABASE_URL,
    DEBUG=False,
)
def test_oidc_valid_user_gets_200(client: Client, oidc_user: AppUser) -> None:
    """El flujo OIDC completo devuelve 200 para usuario válido."""
    token = _make_supabase_token(sub=oidc_user.oidc_sub)
    response = client.get(
        "/api/dashboard/leads/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(
    SUPABASE_URL=TEST_SUPABASE_URL,
    DEBUG=False,
)
def test_oidc_no_token_returns_401(client: Client) -> None:
    response = client.get("/api/dashboard/leads/")
    assert response.status_code == 401
    data = response.json()
    assert "Token no proveído" in data["detail"]


@pytest.mark.django_db
@override_settings(
    SUPABASE_URL=TEST_SUPABASE_URL,
    DEBUG=False,
)
def test_oidc_unsupported_issuer_returns_401(client: Client) -> None:
    token = jwt.encode(
        {
            "iss": "https://sts.windows.net/fake",
            "sub": "fake-sub",
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        },
        _TEST_PRIVATE_KEY,
        algorithm="ES256",
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
    SUPABASE_URL=TEST_SUPABASE_URL,
    DEBUG=False,
)
def test_oidc_expired_token_returns_401(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    import jwt as pyjwt

    def fake_decode(*args, **kwargs):
        raise pyjwt.ExpiredSignatureError("Token has expired")

    monkeypatch.setattr(pyjwt, "decode", fake_decode)

    token = _make_supabase_token(exp_offset=3600)
    with override_settings(DEBUG=False):
        response = client.get(
            "/api/dashboard/leads/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    assert response.status_code == 401
    assert "Token expirado" in response.json()["detail"]


@pytest.mark.django_db
@override_settings(
    SUPABASE_URL=TEST_SUPABASE_URL,
    DEBUG=False,
)
def test_oidc_public_paths_bypass(client: Client) -> None:
    response = client.get("/health/liveness")
    assert response.status_code == 200

    response = client.get("/health/readiness")
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(
    SUPABASE_URL=TEST_SUPABASE_URL,
    DEBUG=False,
)
def test_oidc_malformed_token_missing_iss(client: Client) -> None:
    token = jwt.encode(
        {
            "sub": "550e8400-e29b-41d4-a716-446655440000",
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        },
        _TEST_PRIVATE_KEY,
        algorithm="ES256",
    )
    with override_settings(DEBUG=False):
        response = client.get(
            "/api/dashboard/leads/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    assert response.status_code == 401
    assert "iss faltante" in response.json()["detail"]


@pytest.mark.django_db
@override_settings(
    SUPABASE_URL=TEST_SUPABASE_URL,
    DEBUG=False,
)
def test_oidc_valid_token_returns_200(client: Client, oidc_user: AppUser) -> None:
    token = _make_supabase_token(sub=oidc_user.oidc_sub)
    response = client.get(
        "/api/dashboard/leads/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )

    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(
    SUPABASE_URL=TEST_SUPABASE_URL,
    DEBUG=False,
)
def test_oidc_invalid_signature_returns_401(client: Client) -> None:
    wrong_key = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode(
        {
            "iss": TEST_SUPABASE_ISSUER,
            "sub": "550e8400-e29b-41d4-a716-446655440000",
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        },
        wrong_key,
        algorithm="ES256",
    )
    with override_settings(DEBUG=False):
        response = client.get(
            "/api/dashboard/leads/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    assert response.status_code == 401
    assert "Token inválido" in response.json()["detail"]


@pytest.mark.django_db
@override_settings(
    SUPABASE_URL=TEST_SUPABASE_URL,
    DEBUG=False,
)
def test_oidc_user_not_found_returns_401(client: Client) -> None:
    token = _make_sub("non-existent-sub")
    response = client.get(
        "/api/dashboard/leads/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )

    assert response.status_code == 401
    assert "Usuario asociado al Token denegado" in response.json()["detail"]


def _make_sub(sub: str) -> str:
    return jwt.encode(
        {
            "iss": TEST_SUPABASE_ISSUER,
            "sub": sub,
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        },
        _TEST_PRIVATE_KEY,
        algorithm="ES256",
    )


@pytest.mark.django_db
@override_settings(
    SUPABASE_URL=TEST_SUPABASE_URL,
    DEBUG=False,
)
def test_sse_ticket_valid(client: Client, oidc_user: AppUser) -> None:
    """Ticket SSE válido de un solo uso da acceso al endpoint SSE."""
    from django.core.cache import cache

    ticket = "test-ticket-uuid-1234"
    cache.set(
        f"sse_ticket_{ticket}",
        {"sub": oidc_user.oidc_sub, "issuer": oidc_user.oidc_issuer},
        timeout=30,
    )
    response = client.get(f"/api/sse/dashboard/?ticket={ticket}")
    assert response.status_code in (200, 204)
    assert cache.get(f"sse_ticket_{ticket}") is None


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_sse_ticket_invalid_returns_401(client: Client) -> None:
    """Ticket SSE inexistente devuelve 401."""
    response = client.get("/api/sse/dashboard/?ticket=fake-ticket")
    assert response.status_code == 401


@pytest.mark.django_db
@override_settings(DEBUG=True, SUPABASE_URL=TEST_SUPABASE_URL)
@pytest.mark.parametrize(
    "path",
    [
        "/api/dashboard/leads/",
        "/api/dashboard/leads/pending/",
        "/api/sse/dashboard/",
    ],
)
def test_no_jwt_bypass_when_debug_true(client: Client, path: str) -> None:
    """Regresión: con DEBUG=True las rutas protegidas siguen exigiendo JWT."""
    response = client.get(path)
    assert response.status_code == 401, (
        f"REGRESIÓN CRÍTICA: {path} aceptó request sin JWT con DEBUG=True"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True, SUPABASE_URL=TEST_SUPABASE_URL)
def test_invalid_token_rejected_when_debug_true(client: Client) -> None:
    """Regresión: con DEBUG=True un Bearer mal formado sigue siendo 401."""
    response = client.get(
        "/api/dashboard/leads/",
        HTTP_AUTHORIZATION="Bearer not-a-real-token",
    )
    assert response.status_code == 401
