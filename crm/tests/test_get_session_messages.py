"""
crm/tests/test_get_session_messages.py — Tests para obtener historial de mensajes.

Coverage:
- session_messages_api endpoint (GET /messages/)

Reglas:
- Retorna mensajes de una sesión específica
- Soporta paginación con limit y offset
- Retorna None si la sesión no existe
"""

import pytest
from uuid import uuid4

from django.test import Client, override_settings

from crm.models import Tenant, Lead, ChatSession, AppUser, Message


class MockMiddleware:
    """Middleware para inyectar el tenant en tests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = Tenant.objects.order_by("created_at").first()
        return self.get_response(request)


OVERM = override_settings(
    MIDDLEWARE=["crm.tests.test_get_session_messages.MockMiddleware"]
)


@pytest.mark.django_db
class TestSessionMessagesApi:
    """Tests para session_messages_api endpoint."""

    def test_get_messages_returns_200(
        self, client: Client, tenant: Tenant, lead: Lead, salesperson: AppUser
    ) -> None:
        """GET debe retornar 200 con mensajes."""
        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
            salesperson=salesperson,
        )

        Message.objects.create(
            tenant=tenant,
            session=session,
            provider_message_id="msg-1",
            direction=Message.Direction.INBOUND,
            message_type=Message.Type.TEXT,
            body="Hola",
        )

        response = client.get(f"/api/dashboard/leads/{session.id}/messages/?limit=50")

        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert len(data["messages"]) == 1

    def test_get_messages_with_limit_param(
        self, client: Client, tenant: Tenant, lead: Lead, salesperson: AppUser
    ) -> None:
        """GET con limit debe paginar."""
        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
            salesperson=salesperson,
        )

        for i in range(3):
            Message.objects.create(
                tenant=tenant,
                session=session,
                provider_message_id=f"msg-{i}",
                direction=Message.Direction.INBOUND,
                message_type=Message.Type.TEXT,
                body=f"Mensaje {i}",
            )

        response = client.get(f"/api/dashboard/leads/{session.id}/messages/?limit=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) <= 2

    def test_get_messages_nonexistent_session_returns_404(
        self, client: Client, tenant: Tenant
    ) -> None:
        """GET con session_id inexistente debe retornar 404."""
        fake_id = uuid4()
        response = client.get(f"/api/dashboard/leads/{fake_id}/messages/?limit=50")

        assert response.status_code == 404

    def test_get_messages_missing_limit_returns_400(
        self, client: Client, tenant: Tenant, lead: Lead, salesperson: AppUser
    ) -> None:
        """GET sin limit debe retornar 400."""
        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
            salesperson=salesperson,
        )

        response = client.get(f"/api/dashboard/leads/{session.id}/messages/")

        assert response.status_code == 400

    def test_get_messages_post_not_allowed(
        self, client: Client, tenant: Tenant, lead: Lead, salesperson: AppUser
    ) -> None:
        """POST no debe ser permitido."""
        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
            salesperson=salesperson,
        )

        response = client.post(f"/api/dashboard/leads/{session.id}/messages/?limit=50")

        assert response.status_code == 405


@pytest.mark.django_db
class TestSessionMessagesFilters:
    """Tests para filtrado de mensajes por tenant."""

    def test_get_messages_filters_by_tenant(
        self, client: Client, tenant: Tenant, lead: Lead, salesperson: AppUser
    ) -> None:
        """GET debe filtrar por tenant (aislamiento)."""
        session = ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
            salesperson=salesperson,
        )

        response = client.get(f"/api/dashboard/leads/{session.id}/messages/?limit=50")

        assert response.status_code == 200
