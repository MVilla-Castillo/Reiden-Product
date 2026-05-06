"""
crm/tests/test_tenant_isolation.py — Defensiva contra IDOR cross-tenant.

Verifica que un usuario del tenant B no puede leer ni mutar recursos del tenant A
a través de las vistas del dashboard, aún cuando conoce los UUID del tenant A.

Estos tests son una red de seguridad sobre el patrón TenantManager.for_tenant():
si una vista olvida filtrar por tenant, alguno de estos tests debería romperse.
"""

from __future__ import annotations

import hashlib
import json
import uuid

import pytest
from django.test import Client, override_settings

from core.crypto import encrypt
from crm.models import AppUser, ChatSession, Lead, Tenant


class _IsolatedTenantMiddleware:
    """Middleware mock que inyecta tenant + user según un classvar.

    Permite alternar el "actor" entre tenants A y B dentro del mismo test.
    Bypassa OIDC y CSRF.
    """

    current_tenant_id: uuid.UUID | None = None
    current_user_id: uuid.UUID | None = None

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if _IsolatedTenantMiddleware.current_tenant_id is not None:
            request.tenant = Tenant.objects.get(
                id=_IsolatedTenantMiddleware.current_tenant_id
            )
        if _IsolatedTenantMiddleware.current_user_id is not None:
            request.user = AppUser.objects.get(
                id=_IsolatedTenantMiddleware.current_user_id
            )
        return self.get_response(request)


def _act_as(tenant: Tenant, user: AppUser) -> None:
    _IsolatedTenantMiddleware.current_tenant_id = tenant.id
    _IsolatedTenantMiddleware.current_user_id = user.id


_MIDDLEWARE_PATH = "crm.tests.test_tenant_isolation._IsolatedTenantMiddleware"


@pytest.fixture
def two_tenants(db) -> tuple[Tenant, Tenant]:
    tenant_a = Tenant.objects.create(
        nombre_legal="Tenant A S.A.",
        rut_empresa="76.000.000-1",
        phone_number_id="56911111111",
        waba_id="WABA_A",
        is_verified=True,
        routing_mode="MANUAL",
    )
    tenant_b = Tenant.objects.create(
        nombre_legal="Tenant B S.A.",
        rut_empresa="76.000.000-2",
        phone_number_id="56922222222",
        waba_id="WABA_B",
        is_verified=True,
        routing_mode="MANUAL",
    )
    return tenant_a, tenant_b


@pytest.fixture
def manager_a(db, two_tenants: tuple[Tenant, Tenant]) -> AppUser:
    tenant_a, _ = two_tenants
    return AppUser.objects.create(
        tenant=tenant_a,
        email="manager-a@test.cl",
        role=AppUser.Role.MANAGER,
        oidc_sub="manager-a-sub",
        oidc_issuer="https://test.supabase.co/auth/v1",
        is_active=True,
    )


@pytest.fixture
def manager_b(db, two_tenants: tuple[Tenant, Tenant]) -> AppUser:
    _, tenant_b = two_tenants
    return AppUser.objects.create(
        tenant=tenant_b,
        email="manager-b@test.cl",
        role=AppUser.Role.MANAGER,
        oidc_sub="manager-b-sub",
        oidc_issuer="https://test.supabase.co/auth/v1",
        is_active=True,
    )


@pytest.fixture
def session_in_a(db, two_tenants: tuple[Tenant, Tenant]) -> ChatSession:
    tenant_a, _ = two_tenants
    wa_id = "56911000001"
    lead = Lead.objects.create(
        tenant=tenant_a,
        wa_id=encrypt(wa_id),
        wa_id_hash=hashlib.sha256(wa_id.encode()).hexdigest(),
    )
    return ChatSession.objects.create(
        tenant=tenant_a,
        lead=lead,
        status=ChatSession.Status.CON_VENDEDOR,
        urgency_score=80,
    )


@pytest.mark.django_db
def test_leads_dashboard_no_devuelve_sesiones_de_otro_tenant(
    client: Client,
    session_in_a: ChatSession,
    manager_b: AppUser,
    two_tenants: tuple[Tenant, Tenant],
) -> None:
    _, tenant_b = two_tenants
    _act_as(tenant_b, manager_b)

    with override_settings(MIDDLEWARE=[_MIDDLEWARE_PATH]):
        response = client.get("/api/dashboard/leads/")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0
    assert data["leads"] == []


@pytest.mark.django_db
def test_pending_leads_no_devuelve_sesiones_de_otro_tenant(
    client: Client,
    session_in_a: ChatSession,
    manager_b: AppUser,
    two_tenants: tuple[Tenant, Tenant],
) -> None:
    _, tenant_b = two_tenants
    session_in_a.status = ChatSession.Status.PENDING_ASSIGNMENT
    session_in_a.save()
    _act_as(tenant_b, manager_b)

    with override_settings(MIDDLEWARE=[_MIDDLEWARE_PATH]):
        response = client.get("/api/dashboard/leads/pending/")

    assert response.status_code == 200
    assert response.json()["pending_leads"] == []


@pytest.mark.django_db
def test_session_messages_de_otro_tenant_responde_404(
    client: Client,
    session_in_a: ChatSession,
    manager_b: AppUser,
    two_tenants: tuple[Tenant, Tenant],
) -> None:
    _, tenant_b = two_tenants
    _act_as(tenant_b, manager_b)

    with override_settings(MIDDLEWARE=[_MIDDLEWARE_PATH]):
        response = client.get(
            f"/api/dashboard/leads/{session_in_a.id}/messages/?limit=10"
        )

    assert response.status_code in (403, 404)


@pytest.mark.django_db
def test_change_session_status_de_otro_tenant_no_muta_recurso(
    client: Client,
    session_in_a: ChatSession,
    manager_b: AppUser,
    two_tenants: tuple[Tenant, Tenant],
) -> None:
    _, tenant_b = two_tenants
    original_status = session_in_a.status
    _act_as(tenant_b, manager_b)

    with override_settings(MIDDLEWARE=[_MIDDLEWARE_PATH]):
        response = client.patch(
            f"/api/dashboard/leads/{session_in_a.id}/status/",
            data=json.dumps({"status": "GANADO"}),
            content_type="application/json",
        )

    assert response.status_code in (403, 404)
    session_in_a.refresh_from_db()
    assert session_in_a.status == original_status


@pytest.mark.django_db
def test_tenant_settings_get_solo_devuelve_config_propia(
    client: Client,
    manager_b: AppUser,
    two_tenants: tuple[Tenant, Tenant],
) -> None:
    tenant_a, tenant_b = two_tenants
    _act_as(tenant_b, manager_b)

    with override_settings(MIDDLEWARE=[_MIDDLEWARE_PATH]):
        response = client.get("/api/dashboard/settings/")

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == str(tenant_b.id)
    assert data["tenant_id"] != str(tenant_a.id)


@pytest.mark.django_db
def test_tenant_settings_requiere_usuario_autenticado(
    client: Client,
    two_tenants: tuple[Tenant, Tenant],
) -> None:
    tenant_a, _ = two_tenants
    _IsolatedTenantMiddleware.current_tenant_id = tenant_a.id
    _IsolatedTenantMiddleware.current_user_id = None

    with override_settings(MIDDLEWARE=[_MIDDLEWARE_PATH]):
        response = client.get("/api/dashboard/settings/")

    assert response.status_code == 401
