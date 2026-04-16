"""
crm/tests/test_change_session_status.py — Tests para cambio de estado de sesión.

Coverage:
- ChangeSessionStatusUseCase: Transiciones GANADO, PERDIDO, ABANDONO_BOT
- change_session_status_api endpoint

Reglas:
- Solo estados válidos: GANADO, PERDIDO, ABANDONO_BOT
- PERDIDO requiere lost_reason
- AuditLog dentro de transacción atómica
"""

import pytest
from uuid import uuid4

from django.test import Client, override_settings

from crm.models import Tenant, Lead, ChatSession, AuditLog


class MockMiddleware:
    """Middleware para inyectar el tenant en tests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = Tenant.objects.order_by("created_at").first()
        return self.get_response(request)


OVERM = override_settings(
    MIDDLEWARE=["crm.tests.test_change_session_status.MockMiddleware"]
)


@pytest.mark.django_db
class TestChangeSessionStatusApi:
    """Tests para change_session_status_api endpoint."""

    def test_change_status_ganado_returns_200(
        self, client: Client, tenant: Tenant, lead: Lead
    ) -> None:
        """PATCH con status GANADO debe retornar 200."""
        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
        )

        response = client.patch(
            f"/api/dashboard/leads/{session.id}/status/",
            data='{"status": "GANADO"}',
            content_type="application/json",
        )

        assert response.status_code == 200
        assert response.json()["status"] == "GANADO"

    def test_change_status_perdido_returns_200(
        self, client: Client, tenant: Tenant, lead: Lead
    ) -> None:
        """PATCH con status PERDIDO y lost_reason debe retornar 200."""
        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
        )

        response = client.patch(
            f"/api/dashboard/leads/{session.id}/status/",
            data='{"status": "PERDIDO", "lost_reason": "Sin respuesta"}',
            content_type="application/json",
        )

        assert response.status_code == 200
        assert response.json()["status"] == "PERDIDO"

    def test_change_status_perdido_without_reason_returns_400(
        self, client: Client, tenant: Tenant, lead: Lead
    ) -> None:
        """PATCH con status PERDIDO sin lost_reason debe retornar 400."""
        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
        )

        response = client.patch(
            f"/api/dashboard/leads/{session.id}/status/",
            data='{"status": "PERDIDO"}',
            content_type="application/json",
        )

        assert response.status_code == 400
        assert "lost_reason" in response.json()["error"]

    def test_change_status_invalid_returns_400(
        self, client: Client, tenant: Tenant, lead: Lead
    ) -> None:
        """PATCH con status inválido debe retornar 400."""
        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
        )

        response = client.patch(
            f"/api/dashboard/leads/{session.id}/status/",
            data='{"status": "INVALIDO"}',
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_change_status_nonexistent_returns_404(
        self, client: Client, tenant: Tenant
    ) -> None:
        """PATCH con session_id inexistente debe retornar 404."""
        fake_id = uuid4()
        response = client.patch(
            f"/api/dashboard/leads/{fake_id}/status/",
            data='{"status": "GANADO"}',
            content_type="application/json",
        )

        assert response.status_code == 404

    def test_change_status_invalid_json_returns_400(
        self, client: Client, tenant: Tenant, lead: Lead
    ) -> None:
        """PATCH con JSON inválido debe retornar 400."""
        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
        )

        response = client.patch(
            f"/api/dashboard/leads/{session.id}/status/",
            data="not json",
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_change_status_missing_status_returns_400(
        self, client: Client, tenant: Tenant, lead: Lead
    ) -> None:
        """PATCH sin status debe retornar 400."""
        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
        )

        response = client.patch(
            f"/api/dashboard/leads/{session.id}/status/",
            data='{"other_field": "value"}',
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_change_status_get_method_not_allowed(
        self, client: Client, tenant: Tenant, lead: Lead
    ) -> None:
        """GET no debe ser permitido."""
        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
        )

        response = client.get(f"/api/dashboard/leads/{session.id}/status/")

        assert response.status_code == 405


@pytest.mark.django_db
class TestChangeSessionStatusAuditLog:
    """Tests para AuditLog en cambio de estado."""

    def test_audit_log_created_on_status_change(
        self, client: Client, tenant: Tenant, lead: Lead
    ) -> None:
        """Debe crear AuditLog con acción STATUS_CHANGED."""
        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
        )

        response = client.patch(
            f"/api/dashboard/leads/{session.id}/status/",
            data='{"status": "GANADO"}',
            content_type="application/json",
        )

        assert response.status_code == 200
        audit_log = AuditLog.objects.filter(
            session=session,
            action="STATUS_CHANGED",
        ).first()
        assert audit_log is not None
        assert audit_log.old_value["status"] == "CON_VENDEDOR"
        assert audit_log.new_value["status"] == "GANADO"
