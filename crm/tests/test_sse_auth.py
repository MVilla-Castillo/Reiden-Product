"""
crm/tests/test_sse_auth.py — Tests de autorización para los endpoints SSE.

Cubre tres brechas de seguridad corregidas en crm/views/sse.py:
  1. Snapshot del dashboard filtrado por rol.
  2. Eventos delta del broadcaster filtrados por rol.
  3. Ownership check en /api/sse/messages/<session_id>/.
"""

import hashlib
import json
import uuid

import pytest
from django.http import StreamingHttpResponse
from django.test import RequestFactory

from core.crypto import encrypt
from crm.models import AppUser, ChatSession, Lead, Tenant
from crm.views.sse import (
    _build_dashboard_snapshot,
    _should_forward_to_salesperson,
    messages_sse_view,
)


# ─────────────────────────────────────────────────────────────
# Fixtures locales
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def manager(db, tenant: Tenant) -> AppUser:
    return AppUser.objects.create(
        tenant=tenant,
        email="manager@test.cl",
        role=AppUser.Role.MANAGER,
        oidc_sub="sse-manager-sub",
        oidc_issuer="https://test.supabase.co/auth/v1",
        is_active=True,
    )


@pytest.fixture
def salesperson_a(db, tenant: Tenant) -> AppUser:
    return AppUser.objects.create(
        tenant=tenant,
        email="vendedor_a@test.cl",
        role=AppUser.Role.SALESPERSON,
        oidc_sub="sse-sp-a-sub",
        oidc_issuer="https://test.supabase.co/auth/v1",
        is_active=True,
    )


@pytest.fixture
def salesperson_b(db, tenant: Tenant) -> AppUser:
    return AppUser.objects.create(
        tenant=tenant,
        email="vendedor_b@test.cl",
        role=AppUser.Role.SALESPERSON,
        oidc_sub="sse-sp-b-sub",
        oidc_issuer="https://test.supabase.co/auth/v1",
        is_active=True,
    )


def _make_lead(tenant: Tenant, wa_id: str) -> Lead:
    """Crea un lead con wa_id único para evitar la restricción unique_active_session_per_lead."""
    return Lead.objects.create(
        tenant=tenant,
        wa_id=encrypt(wa_id),
        wa_id_hash=hashlib.sha256(wa_id.encode()).hexdigest(),
    )


@pytest.fixture
def pending_session(db, tenant: Tenant) -> ChatSession:
    lead = _make_lead(tenant, "56900000001")
    return ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.PENDING_ASSIGNMENT,
    )


@pytest.fixture
def session_a(db, tenant: Tenant, salesperson_a: AppUser) -> ChatSession:
    """Sesión asignada al vendedor A (lead propio para evitar constraint)."""
    lead = _make_lead(tenant, "56900000002")
    return ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.CON_VENDEDOR,
        salesperson=salesperson_a,
    )


@pytest.fixture
def session_b(db, tenant: Tenant, salesperson_b: AppUser) -> ChatSession:
    """Sesión asignada al vendedor B con su propio lead."""
    lead = _make_lead(tenant, "56900000003")
    return ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.CON_VENDEDOR,
        salesperson=salesperson_b,
    )


def _make_request(user: AppUser, tenant: Tenant, path: str = "/api/sse/test/"):
    """Construye un HttpRequest con user y tenant inyectados (bypass de middleware)."""
    factory = RequestFactory()
    request = factory.get(path)
    request.user = user
    request.tenant = tenant
    return request


# ─────────────────────────────────────────────────────────────
# Tests unitarios: _should_forward_to_salesperson
# ─────────────────────────────────────────────────────────────


class TestShouldForwardToSalesperson:
    def _make_sse_msg(self, event: str, payload: dict) -> str:
        data = json.dumps(payload)
        return f"event: {event}\ndata: {data}\n\n"

    def test_pending_leads_matching_id_returns_true(self):
        user_id = str(uuid.uuid4())
        msg = self._make_sse_msg(
            "pending_leads", {"salesperson_id": user_id, "action": "assigned"}
        )
        assert _should_forward_to_salesperson(msg, user_id) is True

    def test_pending_leads_different_id_returns_false(self):
        msg = self._make_sse_msg(
            "pending_leads", {"salesperson_id": str(uuid.uuid4()), "action": "assigned"}
        )
        assert _should_forward_to_salesperson(msg, str(uuid.uuid4())) is False

    def test_pending_leads_without_salesperson_id_returns_false(self):
        msg = self._make_sse_msg(
            "pending_leads", {"action": "new_inbound_message", "pending_delta": 1}
        )
        assert _should_forward_to_salesperson(msg, str(uuid.uuid4())) is False

    def test_settings_event_returns_false(self):
        msg = self._make_sse_msg("settings", {"routing_mode": "AUTO"})
        assert _should_forward_to_salesperson(msg, str(uuid.uuid4())) is False

    def test_malformed_msg_returns_false(self):
        assert (
            _should_forward_to_salesperson("garbage_data", str(uuid.uuid4())) is False
        )

    def test_empty_msg_returns_false(self):
        assert _should_forward_to_salesperson("", str(uuid.uuid4())) is False


# ─────────────────────────────────────────────────────────────
# Tests de integración: _build_dashboard_snapshot
# ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBuildDashboardSnapshot:
    def _parse_snapshot(self, tenant: Tenant, user: AppUser) -> dict:
        frame = _build_dashboard_snapshot(tenant, user)
        # Formato: "event: snapshot\ndata: {...}\n\n"
        data_line = next(
            line for line in frame.split("\n") if line.startswith("data: ")
        )
        return json.loads(data_line[6:])

    def test_manager_sees_pending_leads(
        self, tenant: Tenant, manager: AppUser, pending_session: ChatSession
    ):
        payload = self._parse_snapshot(tenant, manager)
        session_ids = [s["session_id"] for s in payload["pending_leads"]]
        assert str(pending_session.id) in session_ids

    def test_manager_sees_all_active_leads(
        self,
        tenant: Tenant,
        manager: AppUser,
        session_a: ChatSession,
        session_b: ChatSession,
    ):
        payload = self._parse_snapshot(tenant, manager)
        session_ids = [s["session_id"] for s in payload["leads"]]
        assert str(session_a.id) in session_ids
        assert str(session_b.id) in session_ids

    def test_manager_receives_salespeople_list(
        self, tenant: Tenant, manager: AppUser, salesperson_a: AppUser
    ):
        payload = self._parse_snapshot(tenant, manager)
        assert len(payload["salespeople"]) >= 1

    def test_manager_receives_settings(self, tenant: Tenant, manager: AppUser):
        payload = self._parse_snapshot(tenant, manager)
        assert "routing_mode" in payload["settings"]

    def test_salesperson_gets_empty_pending_leads(
        self, tenant: Tenant, salesperson_a: AppUser, pending_session: ChatSession
    ):
        payload = self._parse_snapshot(tenant, salesperson_a)
        assert payload["pending_leads"] == []

    def test_salesperson_sees_only_own_leads(
        self,
        tenant: Tenant,
        salesperson_a: AppUser,
        session_a: ChatSession,
        session_b: ChatSession,
    ):
        payload = self._parse_snapshot(tenant, salesperson_a)
        session_ids = [s["session_id"] for s in payload["leads"]]
        assert str(session_a.id) in session_ids
        assert str(session_b.id) not in session_ids

    def test_salesperson_gets_empty_salespeople_list(
        self, tenant: Tenant, salesperson_a: AppUser
    ):
        payload = self._parse_snapshot(tenant, salesperson_a)
        assert payload["salespeople"] == []

    def test_salesperson_gets_no_settings(self, tenant: Tenant, salesperson_a: AppUser):
        payload = self._parse_snapshot(tenant, salesperson_a)
        assert payload["settings"].get("routing_mode") is None


# ─────────────────────────────────────────────────────────────
# Tests de autorización: messages_sse_view
# ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMessagesSSEAuth:
    def test_assigned_salesperson_gets_streaming_response(
        self,
        tenant: Tenant,
        salesperson_a: AppUser,
        session_a: ChatSession,
    ):
        request = _make_request(salesperson_a, tenant)
        response = messages_sse_view(request, session_a.id)
        assert isinstance(response, StreamingHttpResponse)
        assert response.status_code == 200

    def test_unassigned_salesperson_gets_403(
        self,
        tenant: Tenant,
        salesperson_b: AppUser,
        session_a: ChatSession,
    ):
        # salesperson_b intenta acceder a la sesión de salesperson_a
        request = _make_request(salesperson_b, tenant)
        response = messages_sse_view(request, session_a.id)
        assert response.status_code == 403
        assert "error" in json.loads(response.content)

    def test_manager_can_access_any_session(
        self,
        tenant: Tenant,
        manager: AppUser,
        session_a: ChatSession,
    ):
        request = _make_request(manager, tenant)
        response = messages_sse_view(request, session_a.id)
        assert isinstance(response, StreamingHttpResponse)
        assert response.status_code == 200

    def test_nonexistent_session_gets_404_for_salesperson(
        self,
        tenant: Tenant,
        salesperson_a: AppUser,
    ):
        fake_id = uuid.uuid4()
        request = _make_request(salesperson_a, tenant)
        response = messages_sse_view(request, fake_id)
        assert response.status_code == 404

    def test_session_without_salesperson_gets_403(
        self,
        db,
        tenant: Tenant,
        salesperson_a: AppUser,
    ):
        # Sesión pendiente sin salesperson asignado — ningún vendedor puede acceder
        lead = _make_lead(tenant, "56900000099")
        unassigned = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.PENDING_ASSIGNMENT,
        )
        request = _make_request(salesperson_a, tenant)
        response = messages_sse_view(request, unassigned.id)
        assert response.status_code == 403
