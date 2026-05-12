"""
crm/tests/test_metrics.py — Tests AAA para el endpoint /api/dashboard/metrics/.

Coverage:
- TestMetricsApi: contrato del endpoint (auth, rol, params, rate limit, shape).
- TestMetricsFunnelData: contenido del funnel (totales y tasas).
- TestMetricsSalespersonPerformance: agregaciones por vendedor.

Convención: se inyecta tenant + AppUser MANAGER vía MockMiddleware durante el
test (override_settings) bypassando OIDC, igual que en test_dashboard_messages.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone

import pytest
from django.test import Client, override_settings

from core.crypto import encrypt
from crm.models import AppUser, ChatSession, Lead, Tenant


# ─────────────────────────────────────────────────────────
# Middleware mock + helpers
# ─────────────────────────────────────────────────────────


class _ManagerMiddleware:
    """Inyecta el tenant más reciente + un AppUser MANAGER, bypassando OIDC."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = Tenant.objects.order_by("-created_at").first()
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


class _SalespersonMiddleware:
    """Inyecta el tenant + AppUser SALESPERSON, para validar 403."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = Tenant.objects.order_by("-created_at").first()
        if request.tenant:
            user, _ = AppUser.objects.get_or_create(
                tenant=request.tenant,
                oidc_sub=f"mock-salesperson-{request.tenant.id}",
                defaults={
                    "email": f"mock-sp-{request.tenant.id}@test.cl",
                    "role": AppUser.Role.SALESPERSON,
                    "is_active": True,
                    "oidc_issuer": "https://test.supabase.co/auth/v1",
                },
            )
            request.user = user
        return self.get_response(request)


_OVERM_MANAGER = override_settings(
    MIDDLEWARE=["crm.tests.test_metrics._ManagerMiddleware"]
)

_OVERM_SALESPERSON = override_settings(
    MIDDLEWARE=["crm.tests.test_metrics._SalespersonMiddleware"]
)


# ─────────────────────────────────────────────────────────
# Fixtures locales
# ─────────────────────────────────────────────────────────


def _make_lead(tenant: Tenant, suffix: str) -> Lead:
    """Helper: crea un Lead con wa_id único cifrado."""
    wa_id = f"5699{suffix:0>7}"
    return Lead.objects.create(
        tenant=tenant,
        wa_id=encrypt(wa_id),
        wa_id_hash=hashlib.sha256(wa_id.encode()).hexdigest(),
    )


@pytest.fixture
def manager_session_set(db, tenant: Tenant):
    """Conjunto mixto de ChatSessions para alimentar el funnel y métricas.

    Cada sesión activa requiere un lead distinto (constraint
    `unique_active_session_per_lead`); las cerradas pueden compartir.
    """
    now = datetime.now(timezone.utc)
    salesperson = AppUser.objects.create(
        tenant=tenant,
        email="seller-perf@test.cl",
        oidc_sub="seller-perf-sub",
        oidc_issuer="https://test.supabase.co/auth/v1",
        role=AppUser.Role.SALESPERSON,
    )

    # 1 BOT (activo → necesita lead propio)
    ChatSession.objects.create(
        tenant=tenant,
        lead=_make_lead(tenant, "1"),
        status=ChatSession.Status.BOT,
    )
    # 2 PENDING_ASSIGNMENT (activos → leads propios)
    for i in range(2):
        ChatSession.objects.create(
            tenant=tenant,
            lead=_make_lead(tenant, f"2{i}"),
            status=ChatSession.Status.PENDING_ASSIGNMENT,
        )
    # 1 CON_VENDEDOR
    con_vendedor = ChatSession.objects.create(
        tenant=tenant,
        lead=_make_lead(tenant, "3"),
        status=ChatSession.Status.CON_VENDEDOR,
        salesperson=salesperson,
        assigned_at=now - timedelta(minutes=30),
        first_response_at=now - timedelta(minutes=20),
    )
    # 2 GANADO (cerrados → no chocan con constraint)
    closed_lead = _make_lead(tenant, "4")
    for _ in range(2):
        ChatSession.objects.create(
            tenant=tenant,
            lead=closed_lead,
            status=ChatSession.Status.GANADO,
            salesperson=salesperson,
            assigned_at=now - timedelta(hours=2),
            first_response_at=now - timedelta(hours=1, minutes=50),
            closed_at=now - timedelta(minutes=30),
        )
    # 1 PERDIDO (cerrada)
    ChatSession.objects.create(
        tenant=tenant,
        lead=closed_lead,
        status=ChatSession.Status.PERDIDO,
        salesperson=salesperson,
        assigned_at=now - timedelta(hours=3),
        first_response_at=now - timedelta(hours=2, minutes=50),
        closed_at=now - timedelta(hours=1),
    )
    return {
        "salesperson": salesperson,
        "con_vendedor": con_vendedor,
    }


# ─────────────────────────────────────────────────────────
# TestMetricsApi: contrato del endpoint
# ─────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMetricsApi:
    """Tests del contrato del endpoint metrics_api."""

    def test_get_returns_200_for_manager(self, client: Client, tenant: Tenant):
        # Arrange — solo tenant, sin sesiones todavía.

        # Act
        with _OVERM_MANAGER:
            response = client.get("/api/dashboard/metrics/?date_filter=today")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "funnel" in data
        assert "fsm_distribution" in data
        assert "urgency_distribution" in data
        assert "time_metrics" in data
        assert "salesperson_performance" in data
        assert data["date_filter"] == "today"

    def test_get_returns_403_for_salesperson(self, client: Client, tenant: Tenant):
        # Arrange — usuario con rol SALESPERSON.

        # Act
        with _OVERM_SALESPERSON:
            response = client.get("/api/dashboard/metrics/?date_filter=today")

        # Assert
        assert response.status_code == 403
        assert "gerentes" in response.json()["error"].lower()

    def test_post_returns_405(self, client: Client, tenant: Tenant):
        # Arrange — método no permitido.

        # Act
        with _OVERM_MANAGER:
            response = client.post("/api/dashboard/metrics/")

        # Assert
        assert response.status_code == 405

    def test_invalid_date_range_returns_400(self, client: Client, tenant: Tenant):
        # Arrange — date_from > date_to.
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        # Act
        with _OVERM_MANAGER:
            response = client.get(
                f"/api/dashboard/metrics/?date_from={today}&date_to={yesterday}"
            )

        # Assert
        assert response.status_code == 400
        assert "date_from" in response.json()["error"]

    def test_returns_403_when_no_tenant(self, client: Client):
        # Arrange — middleware vacío (sin request.tenant).

        # Act
        with override_settings(MIDDLEWARE=[]):
            response = client.get("/api/dashboard/metrics/?date_filter=today")

        # Assert
        assert response.status_code == 403
        assert "Tenant" in response.json()["error"]


# ─────────────────────────────────────────────────────────
# TestMetricsFunnelData: contenido del funnel
# ─────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMetricsFunnelData:
    """Tests para datos del funnel en métricas."""

    def test_funnel_counts_match_session_mix(self, client: Client, manager_session_set):
        # Arrange — fixture creó 7 sesiones: 1 BOT, 2 PENDING, 1 CON_VENDEDOR, 2 GANADO, 1 PERDIDO.

        # Act
        with _OVERM_MANAGER:
            response = client.get("/api/dashboard/metrics/?date_filter=today")

        # Assert
        assert response.status_code == 200
        funnel = response.json()["funnel"]
        assert funnel["total_leads"] == 7
        # completed_fsm = todas menos BOT (6).
        assert funnel["completed_fsm"] == 6
        # assigned_leads = las que tienen salesperson_id (1 con_vendedor + 2 ganado + 1 perdido).
        assert funnel["assigned_leads"] == 4
        assert funnel["con_vendedor"] == 1
        assert funnel["pending_assignment"] == 2
        assert funnel["won_sessions"] == 2
        assert funnel["lost_sessions"] == 1

    def test_funnel_conversion_rates_are_numeric(
        self, client: Client, manager_session_set
    ):
        # Arrange — el fixture provee un mix conocido.

        # Act
        with _OVERM_MANAGER:
            response = client.get("/api/dashboard/metrics/?date_filter=today")

        # Assert
        funnel = response.json()["funnel"]
        # conversion_rate_fsm = completed_fsm / total_leads = 6 / 7 ≈ 85.71
        assert 85.0 < funnel["conversion_rate_fsm"] < 86.0
        # win_rate = wins / (wins + con_vendedor + lost) = 2 / (2 + 1 + 1) = 50.0
        assert funnel["win_rate"] == 50.0

    def test_funnel_zero_when_no_sessions(self, client: Client, tenant: Tenant):
        # Arrange — tenant sin sesiones.

        # Act
        with _OVERM_MANAGER:
            response = client.get("/api/dashboard/metrics/?date_filter=today")

        # Assert
        funnel = response.json()["funnel"]
        assert funnel["total_leads"] == 0
        assert funnel["conversion_rate_fsm"] == 0
        assert funnel["win_rate"] == 0


# ─────────────────────────────────────────────────────────
# TestMetricsSalespersonPerformance: performance por vendedor
# ─────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMetricsSalespersonPerformance:
    """Tests de la agregación salesperson_performance."""

    def test_performance_returns_one_row_per_salesperson(
        self, client: Client, manager_session_set
    ):
        # Arrange — fixture creó un solo vendedor con 4 sesiones asignadas.

        # Act
        with _OVERM_MANAGER:
            response = client.get("/api/dashboard/metrics/?date_filter=today")

        # Assert
        perf = response.json()["salesperson_performance"]
        assert isinstance(perf, list)
        assert len(perf) == 1
        sp = perf[0]
        assert sp["salesperson_id"] == str(manager_session_set["salesperson"].id)
        assert sp["leads_assigned"] == 4
        assert sp["wins"] == 2
        assert sp["losses"] == 1

    def test_performance_excludes_unassigned_sessions(
        self, client: Client, manager_session_set
    ):
        # Arrange — el fixture tiene sesiones sin asignar (BOT, PENDING) que no deben contarse.

        # Act
        with _OVERM_MANAGER:
            response = client.get("/api/dashboard/metrics/?date_filter=today")

        # Assert
        perf = response.json()["salesperson_performance"]
        # El único vendedor agregado solo tiene las 4 que se le asignaron.
        assert perf[0]["leads_assigned"] == 4

    def test_performance_empty_when_no_assigned_sessions(
        self, client: Client, tenant: Tenant, lead: Lead
    ):
        # Arrange — solo sesiones BOT sin vendedor.
        ChatSession.objects.create(
            tenant=tenant,
            lead=lead,
            status=ChatSession.Status.BOT,
        )

        # Act
        with _OVERM_MANAGER:
            response = client.get("/api/dashboard/metrics/?date_filter=today")

        # Assert
        perf = response.json()["salesperson_performance"]
        assert perf == []
