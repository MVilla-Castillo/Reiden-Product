"""crm/tests/test_update_lead.py — Tests del endpoint update_lead_api.

Cubre la regresión del bug donde el PATCH se bloqueaba por CSRF.
Verifica además: persistencia, history, validación, broadcaster SSE.
"""

from __future__ import annotations

import json
from unittest.mock import patch as mock_patch
from uuid import uuid4

import pytest
from django.test import Client, override_settings

from crm.models import AppUser, ChatSession, Lead, LeadNameHistory, Tenant


_MIDDLEWARE = ["crm.tests.test_update_lead.MockMiddleware"]


class MockMiddleware:
    """Middleware de test que inyecta tenant + usuario MANAGER en cada request."""

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


@pytest.mark.django_db
class TestUpdateLeadApi:
    """Tests del endpoint PATCH /api/dashboard/leads/<id>/lead/."""

    @pytest.fixture(autouse=True)
    def _apply_middleware(self):
        with override_settings(MIDDLEWARE=_MIDDLEWARE):
            yield

    def _make_session(self, tenant: Tenant, lead: Lead) -> ChatSession:
        return ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
        )

    def test_patch_new_name_persists_in_db(
        self, client: Client, tenant: Tenant, lead: Lead
    ) -> None:
        """Regresión del bug: PATCH debe persistir el nuevo nombre en Lead.profile_name."""
        lead.profile_name = "Original"
        lead.save(update_fields=["profile_name"])
        session = self._make_session(tenant, lead)

        response = client.patch(
            f"/api/dashboard/leads/{session.id}/lead/",
            data=json.dumps({"lead_profile_name": "Nuevo Nombre"}),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert response.json()["lead_profile_name"] == "Nuevo Nombre"
        lead.refresh_from_db()
        assert lead.profile_name == "Nuevo Nombre"

    def test_patch_creates_name_history_entry(
        self, client: Client, tenant: Tenant, lead: Lead
    ) -> None:
        lead.profile_name = "Original"
        lead.save(update_fields=["profile_name"])
        session = self._make_session(tenant, lead)

        client.patch(
            f"/api/dashboard/leads/{session.id}/lead/",
            data=json.dumps({"lead_profile_name": "Renombrado"}),
            content_type="application/json",
        )

        history = LeadNameHistory.objects.filter(lead=lead)
        assert history.count() == 1
        entry = history.first()
        assert entry.old_name == "Original"
        assert entry.new_name == "Renombrado"

    def test_patch_same_name_does_not_create_history(
        self, client: Client, tenant: Tenant, lead: Lead
    ) -> None:
        lead.profile_name = "Igual"
        lead.save(update_fields=["profile_name"])
        session = self._make_session(tenant, lead)

        response = client.patch(
            f"/api/dashboard/leads/{session.id}/lead/",
            data=json.dumps({"lead_profile_name": "Igual"}),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert LeadNameHistory.objects.filter(lead=lead).count() == 0

    def test_patch_invalid_json_returns_400(
        self, client: Client, tenant: Tenant, lead: Lead
    ) -> None:
        session = self._make_session(tenant, lead)

        response = client.patch(
            f"/api/dashboard/leads/{session.id}/lead/",
            data="{ not json",
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_patch_nonexistent_session_returns_404(
        self, client: Client, tenant: Tenant
    ) -> None:
        response = client.patch(
            f"/api/dashboard/leads/{uuid4()}/lead/",
            data=json.dumps({"lead_profile_name": "X"}),
            content_type="application/json",
        )

        assert response.status_code == 404

    def test_get_returns_name_and_history(
        self, client: Client, tenant: Tenant, lead: Lead
    ) -> None:
        lead.profile_name = "Actual"
        lead.save(update_fields=["profile_name"])
        LeadNameHistory.objects.create(lead=lead, old_name="Viejo", new_name="Actual")
        session = self._make_session(tenant, lead)

        response = client.get(f"/api/dashboard/leads/{session.id}/lead/")

        assert response.status_code == 200
        body = response.json()
        assert body["lead_profile_name"] == "Actual"
        assert len(body["name_history"]) == 1
        assert body["name_history"][0]["new_name"] == "Actual"

    def test_patch_publishes_lead_updated_event(
        self,
        client: Client,
        tenant: Tenant,
        lead: Lead,
        django_capture_on_commit_callbacks,
    ) -> None:
        """Tras un cambio real de nombre se publica un evento SSE para sincronizar otras vistas."""
        lead.profile_name = "Antes"
        lead.save(update_fields=["profile_name"])
        session = self._make_session(tenant, lead)

        with mock_patch(
            "crm.views.dashboard_messages.broadcaster.publish_dashboard"
        ) as mock_publish:
            with django_capture_on_commit_callbacks(execute=True):
                response = client.patch(
                    f"/api/dashboard/leads/{session.id}/lead/",
                    data=json.dumps({"lead_profile_name": "Despues"}),
                    content_type="application/json",
                )

        assert response.status_code == 200
        assert mock_publish.called
        args, _kwargs = mock_publish.call_args
        assert args[0] == str(tenant.id)
        assert args[1] == "lead_updated"
        payload = args[2]
        assert payload["session_id"] == str(session.id)
        assert payload["lead_id"] == str(lead.id)
        assert payload["lead_profile_name"] == "Despues"

    def test_patch_same_name_does_not_publish_event(
        self,
        client: Client,
        tenant: Tenant,
        lead: Lead,
        django_capture_on_commit_callbacks,
    ) -> None:
        lead.profile_name = "Igual"
        lead.save(update_fields=["profile_name"])
        session = self._make_session(tenant, lead)

        with mock_patch(
            "crm.views.dashboard_messages.broadcaster.publish_dashboard"
        ) as mock_publish:
            with django_capture_on_commit_callbacks(execute=True):
                client.patch(
                    f"/api/dashboard/leads/{session.id}/lead/",
                    data=json.dumps({"lead_profile_name": "Igual"}),
                    content_type="application/json",
                )

        assert not mock_publish.called

    def test_patch_passes_csrf_middleware(
        self, client: Client, tenant: Tenant, lead: Lead
    ) -> None:
        """Test guardián del bug: confirma que @csrf_exempt está aplicado."""
        session = self._make_session(tenant, lead)

        enforced_client = Client(enforce_csrf_checks=True)
        response = enforced_client.patch(
            f"/api/dashboard/leads/{session.id}/lead/",
            data=json.dumps({"lead_profile_name": "Sin CSRF"}),
            content_type="application/json",
        )

        # Debe ser 200, no 403. Antes del fix retornaba 403.
        assert response.status_code == 200
        lead.refresh_from_db()
        assert lead.profile_name == "Sin CSRF"
