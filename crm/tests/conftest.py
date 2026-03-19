"""
crm/tests/conftest.py — Fixtures compartidas para los tests del Sprint 3.

Usa factories simples (sin factory_boy para no sobre-ingenierizar en V1).
Patrón: crear las entidades mínimas necesarias para testear el comportamiento.
"""
import pytest
from crm.models import Tenant, Lead, ChatSession
import hashlib


@pytest.fixture
def tenant(db) -> Tenant:
    """Fixture: Tenant de prueba para tests del webhook worker."""
    return Tenant.objects.create(
        nombre_legal="Automotora Test S.A.",
        rut_empresa="76.000.000-0",
        phone_number_id="56912345678",  # El número 'To' que usará el worker
        waba_id="WABA_TEST_001",
        is_verified=True,
    )


@pytest.fixture
def lead(db, tenant: Tenant) -> Lead:
    """Fixture: Lead de prueba con wa_id_hash correcto."""
    wa_id = "56987654321"
    return Lead.objects.create(
        tenant=tenant,
        wa_id=wa_id,
        wa_id_hash=hashlib.sha256(wa_id.encode()).hexdigest(),
    )


@pytest.fixture
def active_session(db, tenant: Tenant, lead: Lead) -> ChatSession:
    """Fixture: ChatSession activa en estado BOT para el lead de prueba."""
    return ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.BOT,
    )
