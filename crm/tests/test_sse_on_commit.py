"""
crm/tests/test_sse_on_commit.py — Tests defensivos para SSE on_commit.

Verifica que cada endpoint que muta DB programa `broadcaster.publish_*`
DENTRO de un `transaction.on_commit`, no fuera. Si alguien mueve un publish
fuera del callback el test se rompe.

Patrón:
1. mock_patch envuelve broadcaster.publish_* → captura llamadas.
2. django_capture_on_commit_callbacks(execute=True) ejecuta los callbacks
   programados al cerrar el bloque atomic del test.
3. Si el publish está fuera de on_commit, se llama ANTES del execute=True
   (durante el request) y el assert sigue pasando — pero el test
   complementario verifica que SIN execute=True, el publish NO se llama:
   eso prueba que está dentro del callback diferido.
"""

from __future__ import annotations

import hashlib
import json
from unittest.mock import patch as mock_patch

import pytest
from django.test import Client, override_settings

from core.crypto import encrypt
from crm.adapters.messaging.twilio_adapter import TwilioMessageProvider
from crm.domain.ports import SendMessageRequest, SendMessageResult
from crm.models import AppUser, ChatSession, Lead, Tenant


# ─────────────────────────────────────────────────────────
# Middleware mock + fixtures
# ─────────────────────────────────────────────────────────


class _ManagerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = Tenant.objects.order_by("created_at").first()
        if request.tenant:
            user, _ = AppUser.objects.get_or_create(
                tenant=request.tenant,
                oidc_sub=f"mock-manager-{request.tenant.id}",
                defaults={
                    "email": f"mock-manager-{request.tenant.id}@test.cl",
                    "role": AppUser.Role.MANAGER,
                    "is_active": True,
                    "oidc_issuer": "https://test.supabase.co/auth/v1",
                },
            )
            request.user = user
        return self.get_response(request)


_OVERM = override_settings(
    MIDDLEWARE=["crm.tests.test_sse_on_commit._ManagerMiddleware"]
)


@pytest.fixture
def salesperson(db, tenant: Tenant) -> AppUser:
    return AppUser.objects.create(
        email="vendedor-oncommit@test.cl",
        oidc_sub="sp-oncommit-001",
        tenant=tenant,
        role=AppUser.Role.SALESPERSON,
        is_active=True,
    )


@pytest.fixture
def con_vendedor_session(db, tenant: Tenant, lead: Lead, salesperson: AppUser):
    return ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.CON_VENDEDOR,
        salesperson=salesperson,
    )


@pytest.fixture
def mock_twilio_send(monkeypatch):
    def fake_send(self, req: SendMessageRequest) -> SendMessageResult:
        return SendMessageResult(provider_message_id="SM_ONCOMMIT", success=True)

    monkeypatch.setattr(TwilioMessageProvider, "send_message", fake_send)


def _make_extra_lead(tenant: Tenant, suffix: str) -> Lead:
    wa_id = f"5611{suffix:0>7}"
    return Lead.objects.create(
        tenant=tenant,
        wa_id=encrypt(wa_id),
        wa_id_hash=hashlib.sha256(wa_id.encode()).hexdigest(),
    )


# ─────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSendMessageOnCommit:
    def test_publish_message_fires_only_after_commit(
        self,
        client: Client,
        con_vendedor_session: ChatSession,
        mock_twilio_send,
        django_capture_on_commit_callbacks,
    ):
        # Arrange — capturamos publish_message y NO ejecutamos callbacks.
        with _OVERM:
            with mock_patch(
                "crm.views.dashboard_messages.broadcaster.publish_message"
            ) as mock_publish:
                with django_capture_on_commit_callbacks(execute=False) as callbacks:
                    response = client.post(
                        f"/api/dashboard/leads/{con_vendedor_session.id}/messages/send/",
                        data=json.dumps({"body": "hola"}),
                        content_type="application/json",
                    )

                # Assert pre-commit: el publish NO se llama todavía.
                assert response.status_code == 200
                assert not mock_publish.called
                assert len(callbacks) >= 1

                # Ejecutar callbacks → ahora sí se llama.
                for cb in callbacks:
                    cb()
                assert mock_publish.called


@pytest.mark.django_db
class TestAssignLeadOnCommit:
    def test_publish_dashboard_fires_only_after_commit(
        self,
        client: Client,
        active_session: ChatSession,
        salesperson: AppUser,
        django_capture_on_commit_callbacks,
    ):
        # Arrange
        with _OVERM:
            with mock_patch(
                "crm.views.dashboard_messages.broadcaster.publish_dashboard"
            ) as mock_publish:
                with django_capture_on_commit_callbacks(execute=False) as callbacks:
                    response = client.post(
                        f"/api/dashboard/leads/{active_session.id}/assign/",
                        data=json.dumps({"salesperson_id": str(salesperson.id)}),
                        content_type="application/json",
                    )

                assert response.status_code == 200
                assert not mock_publish.called
                assert len(callbacks) >= 1

                for cb in callbacks:
                    cb()
                assert mock_publish.called
                args, _ = mock_publish.call_args
                assert args[1] == "pending_leads"
                assert args[2]["action"] == "assigned"


@pytest.mark.django_db
class TestReassignLeadOnCommit:
    def test_publish_dashboard_fires_only_after_commit(
        self,
        client: Client,
        con_vendedor_session: ChatSession,
        tenant: Tenant,
        django_capture_on_commit_callbacks,
    ):
        # Arrange — segundo vendedor.
        new_sp = AppUser.objects.create(
            email="reassign-oncommit@test.cl",
            oidc_sub="sp-reassign-001",
            tenant=tenant,
            role=AppUser.Role.SALESPERSON,
            is_active=True,
        )

        with _OVERM:
            with mock_patch(
                "crm.views.dashboard_messages.broadcaster.publish_dashboard"
            ) as mock_publish:
                with django_capture_on_commit_callbacks(execute=False) as callbacks:
                    response = client.patch(
                        f"/api/dashboard/leads/{con_vendedor_session.id}/reassign/",
                        data=json.dumps({"salesperson_id": str(new_sp.id)}),
                        content_type="application/json",
                    )

                assert response.status_code == 200
                assert not mock_publish.called
                assert len(callbacks) >= 1

                for cb in callbacks:
                    cb()
                assert mock_publish.called
                _args, _ = mock_publish.call_args
                assert _args[2]["action"] == "reassigned"


@pytest.mark.django_db
class TestChangeSessionStatusOnCommit:
    def test_publishes_dashboard_and_message_only_after_commit(
        self,
        client: Client,
        con_vendedor_session: ChatSession,
        django_capture_on_commit_callbacks,
    ):
        # Arrange
        with _OVERM:
            with (
                mock_patch(
                    "crm.views.dashboard_messages.broadcaster.publish_dashboard"
                ) as mock_dashboard,
                mock_patch(
                    "crm.views.dashboard_messages.broadcaster.publish_message"
                ) as mock_message,
            ):
                with django_capture_on_commit_callbacks(execute=False) as callbacks:
                    response = client.patch(
                        f"/api/dashboard/leads/{con_vendedor_session.id}/status/",
                        data=json.dumps({"status": "GANADO"}),
                        content_type="application/json",
                    )

                # Pre-commit: ninguno se llamó.
                assert response.status_code == 200
                assert not mock_dashboard.called
                assert not mock_message.called
                assert len(callbacks) >= 2

                for cb in callbacks:
                    cb()
                assert mock_dashboard.called
                assert mock_message.called


@pytest.mark.django_db
class TestTenantSettingsOnCommit:
    def test_publishes_settings_only_after_commit(
        self,
        client: Client,
        tenant: Tenant,
        django_capture_on_commit_callbacks,
    ):
        # Arrange — tenant ya existe, PATCH a routing_mode.
        with _OVERM:
            with mock_patch(
                "crm.views.dashboard.broadcaster.publish_dashboard"
            ) as mock_publish:
                with django_capture_on_commit_callbacks(execute=False) as callbacks:
                    response = client.patch(
                        "/api/dashboard/settings/",
                        data=json.dumps({"routing_mode": "AUTO"}),
                        content_type="application/json",
                    )

                assert response.status_code == 200
                assert not mock_publish.called
                assert len(callbacks) >= 1

                for cb in callbacks:
                    cb()
                assert mock_publish.called
                args, _ = mock_publish.call_args
                assert args[1] == "settings"
                assert args[2]["routing_mode"] == "AUTO"
