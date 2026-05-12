"""crm/tests/test_guides.py — Tests del endpoint guides_api.

Coverage:
- Acceso por rol (MANAGER, SALESPERSON, ADMIN)
- Tabs restringidos (dashboard, reports) → 403 para SALESPERSON
- Tabs compartidos (leads, chat) → 200 con contenido distinto por rol
- Tab inválido → 404
- Método no permitido → 405
- Usuario no autenticado → 401
"""

import json

import pytest
from django.test import RequestFactory

from crm.models import AppUser, Tenant
from crm.views.guides import guides_api


@pytest.fixture
def request_factory() -> RequestFactory:
    return RequestFactory()


@pytest.fixture
def manager_user(db, tenant: Tenant) -> AppUser:
    return AppUser.objects.create(
        tenant=tenant,
        email="manager@test.com",
        role=AppUser.Role.MANAGER,
        oidc_sub="test-manager-sub",
        oidc_issuer="accounts.google.com",
        is_active=True,
    )


@pytest.fixture
def admin_user(db, tenant: Tenant) -> AppUser:
    return AppUser.objects.create(
        tenant=tenant,
        email="admin@test.com",
        role=AppUser.Role.ADMIN,
        oidc_sub="test-admin-sub",
        oidc_issuer="accounts.google.com",
        is_active=True,
    )


def _call(factory: RequestFactory, tab: str, user, method: str = "GET"):
    request = getattr(factory, method.lower())(f"/api/dashboard/guides/{tab}/")
    request.user = user
    return guides_api(request, tab)


@pytest.mark.django_db
class TestGuidesApiManagerAccess:
    """MANAGER puede ver todas las tabs."""

    def test_manager_accesses_dashboard_guide(
        self, request_factory: RequestFactory, manager_user: AppUser
    ) -> None:
        # Arrange
        # Act
        response = _call(request_factory, "dashboard", manager_user)
        # Assert
        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["tab"] == "dashboard"
        assert body["role"] == "manager"
        assert isinstance(body["steps"], list) and len(body["steps"]) > 0
        first = body["steps"][0]
        assert {"id", "selector", "title", "desc", "placement"} <= set(first.keys())

    def test_manager_accesses_leads_guide(
        self, request_factory: RequestFactory, manager_user: AppUser
    ) -> None:
        response = _call(request_factory, "leads", manager_user)
        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["role"] == "manager"
        # Manager debe ver elementos exclusivos como assign-col y batch-toolbar
        ids = {step["id"] for step in body["steps"]}
        assert "assign-col" in ids
        assert "batch-toolbar" in ids

    def test_manager_accesses_chat_guide(
        self, request_factory: RequestFactory, manager_user: AppUser
    ) -> None:
        response = _call(request_factory, "chat", manager_user)
        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["tab"] == "chat"
        assert body["role"] == "manager"

    def test_manager_accesses_reports_guide(
        self, request_factory: RequestFactory, manager_user: AppUser
    ) -> None:
        response = _call(request_factory, "reports", manager_user)
        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["tab"] == "reports"
        assert body["role"] == "manager"


@pytest.mark.django_db
class TestGuidesApiSalespersonAccess:
    """SALESPERSON tiene acceso a leads y chat, no a dashboard/reports."""

    def test_salesperson_accesses_leads_guide_with_reduced_content(
        self, request_factory: RequestFactory, salesperson: AppUser
    ) -> None:
        # Arrange + Act
        response = _call(request_factory, "leads", salesperson)
        # Assert
        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["role"] == "salesperson"
        ids = {step["id"] for step in body["steps"]}
        # Vendedor NO debe ver elementos exclusivos de gerente
        assert "assign-col" not in ids
        assert "batch-toolbar" not in ids

    def test_salesperson_accesses_chat_guide(
        self, request_factory: RequestFactory, salesperson: AppUser
    ) -> None:
        response = _call(request_factory, "chat", salesperson)
        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["role"] == "salesperson"
        assert len(body["steps"]) > 0

    def test_salesperson_blocked_from_dashboard_guide(
        self, request_factory: RequestFactory, salesperson: AppUser
    ) -> None:
        response = _call(request_factory, "dashboard", salesperson)
        assert response.status_code == 403

    def test_salesperson_blocked_from_reports_guide(
        self, request_factory: RequestFactory, salesperson: AppUser
    ) -> None:
        response = _call(request_factory, "reports", salesperson)
        assert response.status_code == 403


@pytest.mark.django_db
class TestGuidesApiAdminAccess:
    """ADMIN se mapea a 'manager' y puede ver todas las tabs."""

    def test_admin_accesses_dashboard_guide(
        self, request_factory: RequestFactory, admin_user: AppUser
    ) -> None:
        response = _call(request_factory, "dashboard", admin_user)
        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["role"] == "manager"


@pytest.mark.django_db
class TestGuidesApiValidation:
    """Validación de input y métodos."""

    def test_invalid_tab_returns_404(
        self, request_factory: RequestFactory, manager_user: AppUser
    ) -> None:
        response = _call(request_factory, "no-existe", manager_user)
        assert response.status_code == 404

    def test_post_method_returns_405(
        self, request_factory: RequestFactory, manager_user: AppUser
    ) -> None:
        response = _call(request_factory, "leads", manager_user, method="POST")
        assert response.status_code == 405

    def test_unauthenticated_returns_401(self, request_factory: RequestFactory) -> None:
        # Arrange: AnonymousUser-like (is_authenticated=False)
        from django.contrib.auth.models import AnonymousUser

        request = request_factory.get("/api/dashboard/guides/leads/")
        request.user = AnonymousUser()
        # Act
        response = guides_api(request, "leads")
        # Assert
        assert response.status_code == 401
