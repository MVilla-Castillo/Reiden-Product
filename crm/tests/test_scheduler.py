"""
crm/tests/test_scheduler.py — Tests para endpoints de Cloud Scheduler.

Coverage:
- scheduler_cleanup_bot_view: BOT > 4h → ABANDONO_BOT
- scheduler_cleanup_sales_view: CON_VENDEDOR > 7d → PERDIDO
- scheduler_ttl_warning_view: Alertas TTL
- scheduler_cleanup_rate_limits_view: Limpieza de rate limits

Autenticación: X-Internal-Secret header.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from django.test import Client
from django.utils import timezone

from crm.models import Tenant, Lead, ChatSession, AppUser, AuditLog
import hashlib
from core.crypto import encrypt


@pytest.fixture
def tenant_with_unverified(db) -> Tenant:
    """Tenant no verificado (no debe ser procesado por scheduler)."""
    return Tenant.objects.create(
        nombre_legal="Automotora No Verificada",
        rut_empresa="76.000.001-0",
        phone_number_id="56911111111",
        waba_id="WABA_UNVERIFIED",
        is_verified=False,
    )


@pytest.fixture
def old_bot_session(db, tenant: Tenant, lead: Lead) -> ChatSession:
    """Sesión BOT con más de 4 horas de inactividad."""
    session = ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.BOT,
        created_at=timezone.now() - timedelta(hours=5),
        last_client_message_at=timezone.now() - timedelta(hours=5),
    )
    return session


@pytest.fixture
def recent_bot_session(db, tenant: Tenant, lead: Lead) -> ChatSession:
    """Sesión BOT reciente (menos de 4h, no debe ser limpiada)."""
    return ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.BOT,
        last_client_message_at=timezone.now() - timedelta(hours=2),
    )


@pytest.fixture
def old_con_vendedor_session(
    db, tenant: Tenant, lead: Lead, salesperson: AppUser
) -> ChatSession:
    """Sesión CON_VENDEDOR con más de 7 días de inactividad."""
    session = ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.CON_VENDEDOR,
        salesperson=salesperson,
        last_client_message_at=timezone.now() - timedelta(days=8),
        updated_at=timezone.now() - timedelta(days=8),
    )
    return session


@pytest.fixture
def old_con_vendedor_no_response(
    db, tenant: Tenant, lead: Lead, salesperson: AppUser
) -> ChatSession:
    """Sesión CON_VENDEDOR cerca de TTL (6 días 22 horas) para warning."""
    session = ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.CON_VENDEDOR,
        salesperson=salesperson,
        last_client_message_at=timezone.now() - timedelta(days=6, hours=22),
    )
    return session


@pytest.fixture
def salesperson(db, tenant: Tenant) -> AppUser:
    """Vendedor para asignar a sesiones."""
    return AppUser.objects.create(
        tenant=tenant,
        email="vendedor@test.com",
        role=AppUser.Role.SALESPERSON,
        oidc_sub="test-salesperson-sub",
        oidc_issuer="accounts.google.com",
    )


class TestSchedulerCleanupBot:
    """Tests para scheduler_cleanup_bot_view."""

    def test_cleanup_bot_success(
        self, client: Client, tenant: Tenant, old_bot_session: ChatSession
    ) -> None:
        """Verifica que sesiones BOT > 4h se marcan como ABANDONO_BOT."""
        response = client.post(
            "/api/schedulers/cleanup-bot/",
            HTTP_X_INTERNAL_SECRET="dev-internal-secret-change-in-prod",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["cleaned"] == 1

        old_bot_session.refresh_from_db()
        assert old_bot_session.status == ChatSession.Status.ABANDONO_BOT

    def test_cleanup_bot_audit_log_created(
        self, client: Client, tenant: Tenant, old_bot_session: ChatSession
    ) -> None:
        """Verifica que se crea AuditLog con acción SCHEDULER_CLEANUP_BOT."""
        response = client.post(
            "/api/schedulers/cleanup-bot/",
            HTTP_X_INTERNAL_SECRET="dev-internal-secret-change-in-prod",
        )

        assert response.status_code == 200
        audit_log = AuditLog.objects.filter(
            session=old_bot_session,
            action="SCHEDULER_CLEANUP_BOT",
        ).first()
        assert audit_log is not None
        assert audit_log.old_value["status"] == "BOT"
        assert audit_log.new_value["status"] == "ABANDONO_BOT"

    def test_cleanup_bot_recent_sessions_not_affected(
        self, client: Client, recent_bot_session: ChatSession
    ) -> None:
        """Sesiones BOT recientes (< 4h) no deben ser limpiadas."""
        response = client.post(
            "/api/schedulers/cleanup-bot/",
            HTTP_X_INTERNAL_SECRET="dev-internal-secret-change-in-prod",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["cleaned"] == 0

        recent_bot_session.refresh_from_db()
        assert recent_bot_session.status == ChatSession.Status.BOT

    def test_cleanup_bot_unverified_tenant_excluded(
        self, client: Client, tenant_with_unverified: Tenant, lead: Lead
    ) -> None:
        """Tenants no verificados no deben ser procesados."""
        unverified_lead = Lead.objects.create(
            tenant=tenant_with_unverified,
            wa_id=encrypt("56999999999"),
            wa_id_hash=hashlib.sha256("56999999999".encode()).hexdigest(),
        )
        old_session = ChatSession.objects.create(
            tenant=tenant_with_unverified,
            lead=unverified_lead,
            status=ChatSession.Status.BOT,
            last_client_message_at=timezone.now() - timedelta(hours=5),
            created_at=timezone.now() - timedelta(hours=5),
        )

        response = client.post(
            "/api/schedulers/cleanup-bot/",
            HTTP_X_INTERNAL_SECRET="dev-internal-secret-change-in-prod",
        )

        assert response.status_code == 200
        assert response.json()["cleaned"] == 0

        old_session.refresh_from_db()
        assert old_session.status == ChatSession.Status.BOT

    def test_cleanup_bot_missing_auth_returns_403(self, client: Client) -> None:
        """Sin X-Internal-Secret debe retornar 403."""
        response = client.post("/api/schedulers/cleanup-bot/")

        assert response.status_code == 403

    def test_cleanup_bot_invalid_auth_returns_403(self, client: Client) -> None:
        """Con X-Internal-Secret incorrecto debe retornar 403."""
        response = client.post(
            "/api/schedulers/cleanup-bot/",
            HTTP_X_INTERNAL_SECRET="wrong-secret",
        )

        assert response.status_code == 403

    def test_cleanup_bot_get_method_not_allowed(self, client: Client) -> None:
        """Método GET no debe ser permitido."""
        response = client.get(
            "/api/schedulers/cleanup-bot/",
            HTTP_X_INTERNAL_SECRET="dev-internal-secret-change-in-prod",
        )

        assert response.status_code == 405


class TestSchedulerCleanupSales:
    """Tests para scheduler_cleanup_sales_view."""

    def test_cleanup_sales_success(
        self, client: Client, old_con_vendedor_session: ChatSession
    ) -> None:
        """Verifica que sesiones CON_VENDEDOR > 7d se marcan como PERDIDO."""
        response = client.post(
            "/api/schedulers/cleanup-sales/",
            HTTP_X_INTERNAL_SECRET="dev-internal-secret-change-in-prod",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["cleaned"] == 1

        old_con_vendedor_session.refresh_from_db()
        assert old_con_vendedor_session.status == ChatSession.Status.PERDIDO

    def test_cleanup_sales_audit_log_created(
        self, client: Client, old_con_vendedor_session: ChatSession
    ) -> None:
        """Verifica que se crea AuditLog con acción SCHEDULER_CLEANUP_SALES."""
        response = client.post(
            "/api/schedulers/cleanup-sales/",
            HTTP_X_INTERNAL_SECRET="dev-internal-secret-change-in-prod",
        )

        assert response.status_code == 200
        audit_log = AuditLog.objects.filter(
            session=old_con_vendedor_session,
            action="SCHEDULER_CLEANUP_SALES",
        ).first()
        assert audit_log is not None
        assert audit_log.old_value["status"] == "CON_VENDEDOR"
        assert audit_log.new_value["status"] == "PERDIDO"

    def test_cleanup_sales_missing_auth_returns_403(self, client: Client) -> None:
        """Sin X-Internal-Secret debe retornar 403."""
        response = client.post("/api/schedulers/cleanup-sales/")

        assert response.status_code == 403


class TestSchedulerTtlWarning:
    """Tests para scheduler_ttl_warning_view."""

    def test_ttl_warning_sends_notification(
        self, client: Client, old_con_vendedor_no_response: ChatSession
    ) -> None:
        """Verifica que se envía notificación de TTL warning."""
        response = client.post(
            "/api/schedulers/ttl-warning/",
            HTTP_X_INTERNAL_SECRET="dev-internal-secret-change-in-prod",
        )

        assert response.status_code == 200

    @patch("crm.views.scheduler.DIContainer.instance")
    def test_ttl_warning_no_salesperson_skipped(
        self, mock_di, client: Client, lead: Lead
    ) -> None:
        """Sesiones sin vendedor asignado deben ser omitidas."""
        mock_push = MagicMock()
        mock_di.return_value.push_adapter = mock_push

        session_without_salesperson = ChatSession.objects.create(
            tenant=lead.tenant,
            lead=lead,
            status=ChatSession.Status.CON_VENDEDOR,
            salesperson=None,
            last_client_message_at=timezone.now() - timedelta(days=6, hours=22),
        )

        response = client.post(
            "/api/schedulers/ttl-warning/",
            HTTP_X_INTERNAL_SECRET="dev-internal-secret-change-in-prod",
        )

        assert response.status_code == 200
        assert response.json()["warnings_sent"] == 0
        mock_push.send_ttl_warning.assert_not_called()

    @patch("crm.views.scheduler.DIContainer.instance")
    def test_ttl_warning_exception_handled(
        self, mock_di, client: Client, old_con_vendedor_no_response: ChatSession
    ) -> None:
        """Si falla el envío de warning, no debe fallar el endpoint."""
        mock_push = MagicMock()
        mock_push.send_ttl_warning.side_effect = Exception("Push service down")
        mock_di.return_value.push_adapter = mock_push

        response = client.post(
            "/api/schedulers/ttl-warning/",
            HTTP_X_INTERNAL_SECRET="dev-internal-secret-change-in-prod",
        )

        assert response.status_code == 200

    def test_ttl_warning_missing_auth_returns_403(self, client: Client) -> None:
        """Sin X-Internal-Secret debe retornar 403."""
        response = client.post("/api/schedulers/ttl-warning/")

        assert response.status_code == 403


class TestSchedulerCleanupRateLimits:
    """Tests para scheduler_cleanup_rate_limits_view."""

    @pytest.mark.django_db
    def test_cleanup_rate_limits_success(self, client: Client) -> None:
        """Verifica que se limpian rate limits antiguos."""
        from crm.services.rate_limiter import cleanup_old_rate_limits

        deleted = cleanup_old_rate_limits(hours=1)

        response = client.post(
            "/api/schedulers/cleanup-rate-limits/",
            HTTP_X_INTERNAL_SECRET="dev-internal-secret-change-in-prod",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_cleanup_rate_limits_missing_auth_returns_403(self, client: Client) -> None:
        """Sin X-Internal-Secret debe retornar 403."""
        response = client.post("/api/schedulers/cleanup-rate-limits/")

        assert response.status_code == 403
