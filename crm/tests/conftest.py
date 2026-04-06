"""
crm/tests/conftest.py — Fixtures compartidas para los tests del Sprint 3.

Usa factories simples (sin factory_boy para no sobre-ingenierizar en V1).
Patrón: crear las entidades mínimas necesarias para testear el comportamiento.
"""

import os

# Set encryption key BEFORE Django loads so module-level encrypt() calls work
from cryptography.fernet import Fernet

_TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()
os.environ["WA_ID_ENCRYPTION_KEY"] = _TEST_ENCRYPTION_KEY

import pytest
from crm.models import Tenant, Lead, ChatSession, AppUser
import hashlib
from core.crypto import encrypt, reset_fernet


@pytest.fixture(autouse=True)
def _setup_encryption_key(settings):
    """Ensure encryption key is set for every test."""
    original_key = getattr(settings, "WA_ID_ENCRYPTION_KEY", None)
    settings.WA_ID_ENCRYPTION_KEY = _TEST_ENCRYPTION_KEY
    reset_fernet()
    yield
    settings.WA_ID_ENCRYPTION_KEY = original_key
    reset_fernet()


@pytest.fixture
def tenant(db) -> Tenant:
    """Fixture: Tenant de prueba para tests del webhook worker."""
    return Tenant.objects.create(
        nombre_legal="Automotora Test S.A.",
        rut_empresa="76.000.000-0",
        phone_number_id="56912345678",
        waba_id="WABA_TEST_001",
        is_verified=True,
    )


@pytest.fixture
def lead(db, tenant: Tenant) -> Lead:
    """Fixture: Lead de prueba con wa_id cifrado y wa_id_hash correcto."""
    wa_id = "56987654321"
    return Lead.objects.create(
        tenant=tenant,
        wa_id=encrypt(wa_id),
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


@pytest.fixture
def salesperson(db, tenant: Tenant) -> AppUser:
    """Fixture: Vendedor de prueba para asignar a sesiones."""
    return AppUser.objects.create(
        tenant=tenant,
        email="vendedor@test.com",
        role=AppUser.Role.SALESPERSON,
        oidc_sub="test-salesperson-sub",
        oidc_issuer="accounts.google.com",
    )
