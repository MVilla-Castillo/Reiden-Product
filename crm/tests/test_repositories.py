"""
crm/tests/test_repositories.py — Tests para los adapters de repositorio.

Cubre:
- DjangoLeadRepository (find_by_wa_id_hash, upsert, for_tenant, find_wa_id)
- DjangoSessionRepository (find_active, find_by_id, create, save, assign_salesperson, change_status, expire_if_inactive)
- DjangoMessageRepository (exists_by_provider_id, create, find_by_session)
- DjangoTenantRepository (find_id_by_phone_number)
- DjangoUserRepository (find_salespeople_by_tenant, find_by_id_and_tenant)
"""

import hashlib
import uuid
from dataclasses import replace

import pytest

from core.crypto import encrypt
from crm.adapters.database.repositories import (
    DjangoLeadRepository,
    DjangoMessageRepository,
    DjangoSessionRepository,
    DjangoTenantRepository,
    DjangoUserRepository,
)
from crm.models import AppUser, ChatSession, Lead, Message, Tenant


@pytest.fixture
def lead_repo() -> DjangoLeadRepository:
    return DjangoLeadRepository()


@pytest.fixture
def session_repo() -> DjangoSessionRepository:
    return DjangoSessionRepository()


@pytest.fixture
def message_repo() -> DjangoMessageRepository:
    return DjangoMessageRepository()


@pytest.fixture
def tenant_repo() -> DjangoTenantRepository:
    return DjangoTenantRepository()


@pytest.fixture
def user_repo() -> DjangoUserRepository:
    return DjangoUserRepository()


# ─────────────────────────────────────────────────────────
# DjangoLeadRepository
# ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_lead_find_by_wa_id_hash(
    lead_repo: DjangoLeadRepository, tenant: Tenant
) -> None:
    wa_id = "56911111111"
    wa_id_hash = hashlib.sha256(wa_id.encode()).hexdigest()
    Lead.objects.create(tenant=tenant, wa_id=encrypt(wa_id), wa_id_hash=wa_id_hash)

    result = lead_repo.find_by_wa_id_hash(tenant.id, wa_id_hash)

    assert result is not None
    assert result.wa_id_hash == wa_id_hash


@pytest.mark.django_db
def test_lead_find_by_wa_id_hash_not_found(
    lead_repo: DjangoLeadRepository, tenant: Tenant
) -> None:
    result = lead_repo.find_by_wa_id_hash(tenant.id, "nonexistent")
    assert result is None


@pytest.mark.django_db
def test_lead_upsert_creates_new(
    lead_repo: DjangoLeadRepository, tenant: Tenant
) -> None:
    wa_id = "56922222222"
    wa_id_hash = hashlib.sha256(wa_id.encode()).hexdigest()

    result = lead_repo.upsert(
        tenant.id, wa_id_hash, {"wa_id": wa_id, "first_name": "Carlos"}
    )

    assert result.first_name == "Carlos"
    assert Lead.objects.filter(wa_id_hash=wa_id_hash).count() == 1


@pytest.mark.django_db
def test_lead_upsert_updates_existing(
    lead_repo: DjangoLeadRepository, tenant: Tenant
) -> None:
    wa_id = "56933333333"
    wa_id_hash = hashlib.sha256(wa_id.encode()).hexdigest()
    Lead.objects.create(
        tenant=tenant, wa_id=encrypt(wa_id), wa_id_hash=wa_id_hash, first_name="Old"
    )

    result = lead_repo.upsert(
        tenant.id, wa_id_hash, {"wa_id": wa_id, "first_name": "New"}
    )

    assert result.first_name == "New"


@pytest.mark.django_db
def test_lead_for_tenant(lead_repo: DjangoLeadRepository, tenant: Tenant) -> None:
    other_tenant = Tenant.objects.create(
        nombre_legal="Other", rut_empresa="9-9", phone_number_id="56999999999"
    )
    Lead.objects.create(
        tenant=tenant,
        wa_id=encrypt("56944444444"),
        wa_id_hash=hashlib.sha256(b"444").hexdigest(),
    )
    Lead.objects.create(
        tenant=other_tenant,
        wa_id=encrypt("56955555555"),
        wa_id_hash=hashlib.sha256(b"555").hexdigest(),
    )

    results = lead_repo.for_tenant(tenant.id)

    assert len(results) == 1


@pytest.mark.django_db
def test_lead_find_wa_id(lead_repo: DjangoLeadRepository, tenant: Tenant) -> None:
    wa_id = "56966666666"
    lead = Lead.objects.create(
        tenant=tenant,
        wa_id=encrypt(wa_id),
        wa_id_hash=hashlib.sha256(wa_id.encode()).hexdigest(),
    )

    result = lead_repo.find_wa_id(lead.id)

    assert result == wa_id


@pytest.mark.django_db
def test_lead_find_wa_id_not_found(lead_repo: DjangoLeadRepository) -> None:
    result = lead_repo.find_wa_id(uuid.uuid4())
    assert result is None


# ─────────────────────────────────────────────────────────
# DjangoSessionRepository
# ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_session_find_active(
    session_repo: DjangoSessionRepository, tenant: Tenant, lead: Lead
) -> None:
    ChatSession.objects.create(tenant=tenant, lead=lead, status=ChatSession.Status.BOT)

    result = session_repo.find_active(tenant.id, lead.id)

    assert result is not None
    assert result.status == "BOT"


@pytest.mark.django_db
def test_session_find_active_none(
    session_repo: DjangoSessionRepository, tenant: Tenant, lead: Lead
) -> None:
    result = session_repo.find_active(tenant.id, lead.id)
    assert result is None


@pytest.mark.django_db
def test_session_find_by_id(
    session_repo: DjangoSessionRepository, tenant: Tenant, lead: Lead
) -> None:
    session = ChatSession.objects.create(
        tenant=tenant, lead=lead, status=ChatSession.Status.BOT
    )

    result = session_repo.find_by_id(session.id, tenant.id)

    assert result is not None
    assert result.id == session.id


@pytest.mark.django_db
def test_session_find_by_id_not_found(
    session_repo: DjangoSessionRepository, tenant: Tenant
) -> None:
    result = session_repo.find_by_id(uuid.uuid4(), tenant.id)
    assert result is None


@pytest.mark.django_db
def test_session_create(
    session_repo: DjangoSessionRepository, tenant: Tenant, lead: Lead
) -> None:
    result = session_repo.create(tenant.id, lead.id, status="BOT")

    assert result.status == "BOT"
    assert result.tenant_id == tenant.id
    assert result.lead_id == lead.id


@pytest.mark.django_db
def test_session_save_updates_fields(
    session_repo: DjangoSessionRepository, tenant: Tenant, lead: Lead
) -> None:
    session = session_repo.create(tenant.id, lead.id, status="BOT")
    session = replace(session, status="PENDING_ASSIGNMENT")

    saved = session_repo.save(session)

    assert saved.status == "PENDING_ASSIGNMENT"

    model = ChatSession.objects.get(id=session.id)
    assert model.status == "PENDING_ASSIGNMENT"


@pytest.mark.django_db
def test_session_assign_salesperson(
    session_repo: DjangoSessionRepository, tenant: Tenant, lead: Lead
) -> None:
    session = ChatSession.objects.create(
        tenant=tenant, lead=lead, status=ChatSession.Status.BOT
    )
    sp = AppUser.objects.create(
        email="sp@test.cl",
        oidc_sub="sp-1",
        tenant=tenant,
        role=AppUser.Role.SALESPERSON,
        is_active=True,
    )

    result = session_repo.assign_salesperson(session.id, tenant.id, sp.id)

    assert result is not None
    assert result.status == "CON_VENDEDOR"
    assert result.salesperson_id == sp.id


@pytest.mark.django_db
def test_session_unassign_salesperson(
    session_repo: DjangoSessionRepository, tenant: Tenant, lead: Lead
) -> None:
    sp = AppUser.objects.create(
        email="sp@test.cl",
        oidc_sub="sp-1",
        tenant=tenant,
        role=AppUser.Role.SALESPERSON,
        is_active=True,
    )
    session = ChatSession.objects.create(
        tenant=tenant, lead=lead, status=ChatSession.Status.CON_VENDEDOR, salesperson=sp
    )

    result = session_repo.assign_salesperson(session.id, tenant.id, None)

    assert result is not None
    assert result.status == "PENDING_ASSIGNMENT"
    assert result.salesperson_id is None


@pytest.mark.django_db
def test_session_change_status(
    session_repo: DjangoSessionRepository, tenant: Tenant, lead: Lead
) -> None:
    session = ChatSession.objects.create(
        tenant=tenant, lead=lead, status=ChatSession.Status.BOT
    )

    result = session_repo.change_status(session.id, tenant.id, "GANADO")

    assert result is not None
    assert result.status == "GANADO"


@pytest.mark.django_db
def test_session_change_status_not_found(
    session_repo: DjangoSessionRepository, tenant: Tenant
) -> None:
    result = session_repo.change_status(uuid.uuid4(), tenant.id, "GANADO")
    assert result is None


@pytest.mark.django_db
def test_session_find_active_for_update(
    session_repo: DjangoSessionRepository, tenant: Tenant, lead: Lead
) -> None:
    ChatSession.objects.create(tenant=tenant, lead=lead, status=ChatSession.Status.BOT)

    result = session_repo.find_active_for_update(tenant.id, lead.id)

    assert result is not None
    assert result.status == "BOT"


@pytest.mark.django_db
def test_session_find_active_for_update_none(
    session_repo: DjangoSessionRepository, tenant: Tenant, lead: Lead
) -> None:
    result = session_repo.find_active_for_update(tenant.id, lead.id)
    assert result is None


@pytest.mark.django_db
def test_session_expire_if_inactive_active(
    session_repo: DjangoSessionRepository, tenant: Tenant, lead: Lead
) -> None:
    ChatSession.objects.create(tenant=tenant, lead=lead, status=ChatSession.Status.BOT)

    result = session_repo.expire_if_inactive(tenant.id, lead.id, hours=24)

    assert result is not None
    assert result.status == "BOT"


@pytest.mark.django_db
def test_session_expire_if_inactive_expired(
    session_repo: DjangoSessionRepository, tenant: Tenant, lead: Lead
) -> None:
    from datetime import timedelta
    from django.utils import timezone

    session = ChatSession.objects.create(
        tenant=tenant, lead=lead, status=ChatSession.Status.BOT
    )
    ChatSession.objects.filter(id=session.id).update(
        created_at=timezone.now() - timedelta(hours=48),
        updated_at=timezone.now() - timedelta(hours=48),
    )

    result = session_repo.expire_if_inactive(tenant.id, lead.id, hours=24)

    assert result is None
    session.refresh_from_db()
    assert session.status == "ABANDONO_BOT"


# ─────────────────────────────────────────────────────────
# DjangoMessageRepository
# ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_message_exists_by_provider_id(
    message_repo: DjangoMessageRepository, tenant: Tenant, lead: Lead
) -> None:
    session = ChatSession.objects.create(tenant=tenant, lead=lead)
    Message.objects.create(
        tenant=tenant,
        session=session,
        provider_message_id="SM_EXISTS",
        direction="INBOUND",
        message_type="TEXT",
        body="test",
    )

    assert message_repo.exists_by_provider_id("SM_EXISTS") is True
    assert message_repo.exists_by_provider_id("SM_NOT_EXISTS") is False


@pytest.mark.django_db
def test_message_create(
    message_repo: DjangoMessageRepository, tenant: Tenant, lead: Lead
) -> None:
    session = ChatSession.objects.create(tenant=tenant, lead=lead)

    result = message_repo.create(
        tenant_id=tenant.id,
        session_id=session.id,
        provider_message_id="SM_NEW",
        direction="OUTBOUND",
        message_type="TEXT",
        body="Hola",
    )

    assert result.body == "Hola"
    assert result.direction == "OUTBOUND"


@pytest.mark.django_db
def test_message_find_by_session(
    message_repo: DjangoMessageRepository, tenant: Tenant, lead: Lead
) -> None:
    session = ChatSession.objects.create(tenant=tenant, lead=lead)
    Message.objects.create(
        tenant=tenant,
        session=session,
        provider_message_id="SM_1",
        direction="INBOUND",
        message_type="TEXT",
        body="Msg 1",
    )
    Message.objects.create(
        tenant=tenant,
        session=session,
        provider_message_id="SM_2",
        direction="OUTBOUND",
        message_type="TEXT",
        body="Msg 2",
    )

    results = message_repo.find_by_session(session.id, tenant.id)

    assert len(results) == 2
    assert results[0].body == "Msg 1"
    assert results[1].body == "Msg 2"


# ─────────────────────────────────────────────────────────
# DjangoTenantRepository
# ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_tenant_find_id_by_phone_number(
    tenant_repo: DjangoTenantRepository, tenant: Tenant
) -> None:
    result = tenant_repo.find_id_by_phone_number(tenant.phone_number_id)
    assert result == tenant.id


@pytest.mark.django_db
def test_tenant_find_id_by_phone_number_not_found(
    tenant_repo: DjangoTenantRepository,
) -> None:
    result = tenant_repo.find_id_by_phone_number("nonexistent")
    assert result is None


# ─────────────────────────────────────────────────────────
# DjangoUserRepository
# ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_user_find_salespeople_by_tenant(
    user_repo: DjangoUserRepository, tenant: Tenant
) -> None:
    AppUser.objects.create(
        email="sp1@test.cl",
        oidc_sub="sp1",
        tenant=tenant,
        role=AppUser.Role.SALESPERSON,
        is_active=True,
    )
    AppUser.objects.create(
        email="admin@test.cl",
        oidc_sub="admin",
        tenant=tenant,
        role=AppUser.Role.ADMIN,
        is_active=True,
    )

    results = user_repo.find_salespeople_by_tenant(tenant.id)

    assert len(results) == 1
    assert results[0]["email"] == "sp1@test.cl"


@pytest.mark.django_db
def test_user_find_by_id_and_tenant(
    user_repo: DjangoUserRepository, tenant: Tenant
) -> None:
    sp = AppUser.objects.create(
        email="sp2@test.cl",
        oidc_sub="sp2",
        tenant=tenant,
        role=AppUser.Role.SALESPERSON,
        is_active=True,
    )

    result = user_repo.find_by_id_and_tenant(sp.id, tenant.id)

    assert result is not None
    assert result["email"] == "sp2@test.cl"
    assert result["role"] == "SALESPERSON"


@pytest.mark.django_db
def test_user_find_by_id_and_tenant_not_found(
    user_repo: DjangoUserRepository, tenant: Tenant
) -> None:
    result = user_repo.find_by_id_and_tenant(uuid.uuid4(), tenant.id)
    assert result is None


@pytest.mark.django_db
def test_user_find_by_id_and_tenant_with_role(
    user_repo: DjangoUserRepository, tenant: Tenant
) -> None:
    sp = AppUser.objects.create(
        email="sp3@test.cl",
        oidc_sub="sp3",
        tenant=tenant,
        role=AppUser.Role.SALESPERSON,
        is_active=True,
    )
    AppUser.objects.create(
        email="mgr@test.cl",
        oidc_sub="mgr",
        tenant=tenant,
        role=AppUser.Role.MANAGER,
        is_active=True,
    )

    result = user_repo.find_by_id_and_tenant(sp.id, tenant.id, role="SALESPERSON")
    assert result is not None

    result = user_repo.find_by_id_and_tenant(sp.id, tenant.id, role="ADMIN")
    assert result is None
