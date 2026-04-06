"""
crm/tests/test_send_outbound_message.py — Tests para envío de mensajes salientes.

Coverage:
- send_message_api endpoint (POST /messages/send/)

Reglas:
- Solo sesiones en estado CON_VENDEDOR pueden recibir mensajes
- AuditLog con acción OUTBOUND_MESSAGE_SENT
"""

import pytest
from django.test import Client, override_settings
from unittest.mock import patch, MagicMock

from crm.models import Tenant, Lead, ChatSession, AppUser, Message
from core.crypto import encrypt


class MockMiddleware:
    """Middleware para inyectar el tenant en tests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = Tenant.objects.order_by("created_at").first()
        return self.get_response(request)


OVERM = override_settings(
    MIDDLEWARE=["crm.tests.test_send_outbound_message.MockMiddleware"]
)


@pytest.mark.django_db
class TestSendMessageApi:
    """Tests para send_message_api endpoint."""

    def test_send_message_returns_200(
        self, client: Client, tenant: Tenant, lead: Lead, salesperson: AppUser
    ) -> None:
        """POST con mensaje válido debe retornar 200."""
        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
            salesperson=salesperson,
        )

        with patch(
            "crm.adapters.messaging.twilio_adapter.TwilioMessageProvider.send_message"
        ) as mock_send:
            mock_send.return_value = MagicMock(
                provider_message_id="SM_FAKE_001",
                success=True,
            )

            response = client.post(
                f"/api/dashboard/leads/{session.id}/messages/send/",
                data='{"body": "Hola"}',
                content_type="application/json",
            )

        assert response.status_code == 200

    def test_send_message_to_bot_returns_403(
        self, client: Client, tenant: Tenant, lead: Lead
    ) -> None:
        """POST a sesión en BOT debe retornar 403."""
        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.BOT,
        )

        response = client.post(
            f"/api/dashboard/leads/{session.id}/messages/send/",
            data='{"body": "Hola"}',
            content_type="application/json",
        )

        assert response.status_code == 403

    def test_send_message_invalid_json_returns_400(
        self, client: Client, tenant: Tenant, lead: Lead, salesperson: AppUser
    ) -> None:
        """POST con JSON inválido debe retornar 400."""
        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
            salesperson=salesperson,
        )

        response = client.post(
            f"/api/dashboard/leads/{session.id}/messages/send/",
            data="not json",
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_send_message_missing_body_returns_400(
        self, client: Client, tenant: Tenant, lead: Lead, salesperson: AppUser
    ) -> None:
        """POST sin body debe retornar 400."""
        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
            salesperson=salesperson,
        )

        response = client.post(
            f"/api/dashboard/leads/{session.id}/messages/send/",
            data='{"other": "value"}',
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_send_message_get_not_allowed(
        self, client: Client, tenant: Tenant, lead: Lead, salesperson: AppUser
    ) -> None:
        """GET no debe ser permitido."""
        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
            salesperson=salesperson,
        )

        response = client.get(f"/api/dashboard/leads/{session.id}/messages/send/")

        assert response.status_code == 405


@pytest.mark.django_db
class TestSendMessageAuditLog:
    """Tests para AuditLog al enviar mensaje."""

    def test_audit_log_created_on_send_message(
        self, client: Client, tenant: Tenant, lead: Lead, salesperson: AppUser
    ) -> None:
        """Debe crear AuditLog con acción OUTBOUND_MESSAGE_SENT."""
        from crm.models import AuditLog

        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
            salesperson=salesperson,
        )

        with patch(
            "crm.adapters.messaging.twilio_adapter.TwilioMessageProvider.send_message"
        ) as mock_send:
            mock_send.return_value = MagicMock(
                provider_message_id="SM_FAKE_001",
                success=True,
            )

            response = client.post(
                f"/api/dashboard/leads/{session.id}/messages/send/",
                data='{"body": "Hola"}',
                content_type="application/json",
            )

        assert response.status_code == 200
        audit_log = AuditLog.objects.filter(
            session=session,
            action="OUTBOUND_MESSAGE_SENT",
        ).first()
        assert audit_log is not None
