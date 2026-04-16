"""Tests para DjangoAuditLogger."""

import pytest

from crm.adapters.database.repositories import DjangoAuditLogger
from crm.domain.ports import AuditEntry
from crm.models import AuditLog, ChatSession, Lead, Tenant


@pytest.fixture
def audit_logger() -> DjangoAuditLogger:
    return DjangoAuditLogger()


@pytest.mark.django_db
def test_audit_logger_record(
    audit_logger: DjangoAuditLogger, tenant: Tenant, lead: Lead
) -> None:
    session = ChatSession.objects.create(tenant=tenant, lead=lead)

    entry = AuditEntry(
        session_id=session.id,
        tenant_id=tenant.id,
        action="TEST_ACTION",
        old_value={"status": "BOT"},
        new_value={"status": "QUALIFIED"},
    )

    audit_logger.record(entry)

    assert AuditLog.objects.filter(session_id=session.id).count() == 1
    log = AuditLog.objects.get(session_id=session.id)
    assert log.action == "TEST_ACTION"
    assert log.old_value == {"status": "BOT"}
    assert log.new_value == {"status": "QUALIFIED"}


@pytest.mark.django_db
def test_audit_logger_with_actor(
    audit_logger: DjangoAuditLogger, tenant: Tenant, lead: Lead
) -> None:
    from crm.models import AppUser

    session = ChatSession.objects.create(tenant=tenant, lead=lead)
    user = AppUser.objects.create(
        email="actor@test.cl",
        oidc_sub="actor-1",
        tenant=tenant,
        role=AppUser.Role.SALESPERSON,
        is_active=True,
    )

    entry = AuditEntry(
        session_id=session.id,
        tenant_id=tenant.id,
        action="LEAD_ASSIGNED",
        old_value={"salesperson_id": None},
        new_value={"salesperson_id": str(user.id)},
        actor_id=user.id,
    )

    audit_logger.record(entry)

    log = AuditLog.objects.get(session_id=session.id)
    assert log.actor_id == user.id
