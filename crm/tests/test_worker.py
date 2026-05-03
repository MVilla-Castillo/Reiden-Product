"""
crm/tests/test_worker.py — Tests para el Worker privado de Cloud Tasks.

Ciclo TDD: Red → Green → Refactor (SKILL: tdd)
Patrón: AAA (Arrange → Act → Assert)

El worker ahora delega a ProcessMessageUseCase, así que mockeamos
los adapters en lugar de las funciones sueltas.
"""

import hashlib
import json
import pytest
from django.test import Client
from django.conf import settings

from core.crypto import encrypt
from crm.adapters.dependency_injection import DIContainer
from crm.adapters.messaging.twilio_adapter import InMemoryMessageProvider
from crm.models import AuditLog, Lead, Message, ChatSession


def _make_payload(message_sid: str = "SMtest0000000000000000000000001") -> dict:
    return {
        "MessageSid": message_sid,
        "AccountSid": "ACtest",
        "From": "whatsapp:+56987654321",
        "To": "whatsapp:+56912345678",
        "WaId": "56987654321",
        "Body": "Hola, quiero info sobre un SUV",
        "ButtonText": "",
        "ButtonPayload": "",
        "MessageType": "text",
        "NumMedia": "0",
        "MediaUrl0": "",
        "MediaContentType0": "",
        "ListId": "",
        "ListTitle": "",
        "ReferralNumMedia": "0",
        "ReferralSourceType": "",
        "ReferralSourceUrl": "",
        "Timestamp": "2026-03-18T15:00:00Z",
    }


def _post_to_worker(client: Client, payload: dict) -> object:
    internal_secret = settings.INTERNAL_SECRET
    return client.post(
        "/api/workers/process-message/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_INTERNAL_SECRET=internal_secret,
    )


@pytest.fixture(autouse=True)
def _setup_di_with_mock_provider():
    """Inject InMemoryMessageProvider to avoid real Twilio API calls."""
    DIContainer.reset()
    container = DIContainer.instance()
    container.set_message_provider(InMemoryMessageProvider())
    yield
    DIContainer.reset()


# ==============================================================================
# TEST: Happy Path — Nuevo mensaje → Lead, Session y Message creados en DB
# ==============================================================================
@pytest.mark.django_db
def test_new_message_creates_lead_session_and_message(tenant) -> None:
    """
    ARRANGE: Tenant existe. Primer mensaje de un lead nuevo.
    ACT: POST al worker con un payload válido.
    ASSERT: Lead, ChatSession y Message creados. Status 200.
    """
    client = Client()
    payload = _make_payload("SMhappy00000000000000000000001")

    response = _post_to_worker(client, payload)

    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    assert response.json()["created"] is True

    wa_id_hash = hashlib.sha256("56987654321".encode()).hexdigest()
    assert Lead.objects.filter(wa_id_hash=wa_id_hash).exists()
    assert ChatSession.objects.filter(lead__wa_id_hash=wa_id_hash).exists()
    assert Message.objects.filter(
        provider_message_id="SMhappy00000000000000000000001"
    ).exists()


# ==============================================================================
# TEST: Idempotencia — Mismo MessageSid procesado dos veces → 1 solo Message
# ==============================================================================
@pytest.mark.django_db
def test_duplicate_message_is_idempotent(tenant) -> None:
    """
    ARRANGE: Tenant existe. Se procesa el mismo payload dos veces.
    ACT: Dos POST consecutivos al worker con el mismo MessageSid.
    ASSERT: Solo 1 Message en DB. Ambas respuestas son 200 OK.
    """
    client = Client()
    payload = _make_payload("SMduplicate000000000000000001")

    response_1 = _post_to_worker(client, payload)
    response_2 = _post_to_worker(client, payload)

    assert response_1.status_code == 200
    assert response_2.status_code == 200
    assert response_2.json()["status"] == "duplicate_ignored"

    count = Message.objects.filter(
        provider_message_id="SMduplicate000000000000000001"
    ).count()
    assert count == 1, f"Se esperaba 1 Message, se encontraron {count}"


# ==============================================================================
# TEST: Edge Case 1 — Secreto interno inválido → 403
# ==============================================================================
@pytest.mark.django_db
def test_invalid_internal_secret_returns_403() -> None:
    """
    ARRANGE: Request con header X-Internal-Secret incorrecto.
    ACT: POST al worker con secreto incorrecto.
    ASSERT: 403 Forbidden. Ningún dato creado en DB.
    """
    client = Client()
    payload = _make_payload("SMsecret000000000000000000001")

    response = client.post(
        "/api/workers/process-message/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_INTERNAL_SECRET="wrong-secret-hackeando",
    )

    assert response.status_code == 403
    assert not Message.objects.filter(
        provider_message_id="SMsecret000000000000000000001"
    ).exists()


# ==============================================================================
# TEST: Edge Case 2 — Tenant no encontrado → 200 OK (no reintentar)
# ==============================================================================
@pytest.mark.django_db
def test_unknown_tenant_returns_200_no_retry(db) -> None:
    """
    ARRANGE: No existe ningún Tenant. El número 'To' no está registrado.
    ACT: POST al worker con un número 'To' desconocido.
    ASSERT: 200 OK (para que Cloud Tasks no reintente un error permanente).
             Ningún Lead ni Message creado en DB.
    """
    client = Client()
    payload = _make_payload("SMnotenant000000000000000001")

    response = _post_to_worker(client, payload)

    assert response.status_code == 200
    assert "tenant_not_found" in response.json().get("status", "")
    assert not Lead.objects.exists()
    assert not Message.objects.exists()


# ==============================================================================
# TEST: Edge Case 3 — Body JSON inválido → 400 Bad Request
# ==============================================================================
@pytest.mark.django_db
def test_invalid_json_body_returns_400() -> None:
    """
    ARRANGE: Request con body que no es JSON válido.
    ACT: POST al worker con plaintext.
    ASSERT: 400 Bad Request.
    """
    client = Client()
    internal_secret = settings.INTERNAL_SECRET

    response = client.post(
        "/api/workers/process-message/",
        data="esto no es json {{{",
        content_type="application/json",
        HTTP_X_INTERNAL_SECRET=internal_secret,
    )

    assert response.status_code == 400


# ==============================================================================
# TEST: AuditLog A — SESSION_START escrito al primer contacto del lead
# ==============================================================================
@pytest.mark.django_db
def test_auditlog_session_start_created(tenant) -> None:
    """
    ARRANGE: Tenant existe. Primer mensaje de un lead nuevo.
    ACT: POST al worker con payload válido (primer contacto).
    ASSERT: Existe exactamente 1 AuditLog con action='SESSION_START'.
    """
    client = Client()
    payload = _make_payload("SMaudit_session_start_01")

    response = _post_to_worker(client, payload)

    assert response.status_code == 200
    session_start_logs = AuditLog.objects.filter(action="SESSION_START")
    assert session_start_logs.count() == 1, (
        f"Se esperaba 1 AuditLog SESSION_START, se encontraron {session_start_logs.count()}"
    )
    log = session_start_logs.first()
    assert log is not None
    assert "lead_id" in log.new_value
    assert log.new_value["status"] == "BOT"


# ==============================================================================
# TEST: AuditLog B — MSG_RECEIVED escrito en cada mensaje entrante
# ==============================================================================
@pytest.mark.django_db
def test_auditlog_msg_received_written_per_message(tenant) -> None:
    """
    ARRANGE: Tenant existe. Lead con sesión activa (returning lead).
    ACT: POST al worker con un nuevo MessageSid (mensaje número 2 en la sesión).
    ASSERT: Se escribe 1 AuditLog con action='MSG_RECEIVED'.
             El campo new_value contiene 'message_sid' y 'body_length'.
    """
    wa_id = "56987654321"
    lead = Lead.objects.create(
        tenant=tenant,
        wa_id=encrypt(wa_id),
        wa_id_hash=hashlib.sha256(wa_id.encode()).hexdigest(),
    )
    ChatSession.objects.create(tenant=tenant, lead=lead, status=ChatSession.Status.BOT)

    client = Client()
    payload = _make_payload("SMaudit_msg_received_02")

    response = _post_to_worker(client, payload)

    assert response.status_code == 200
    msg_logs = AuditLog.objects.filter(action="MSG_RECEIVED")
    assert msg_logs.count() == 1, (
        f"Se esperaba 1 AuditLog MSG_RECEIVED, se encontraron {msg_logs.count()}"
    )
    log = msg_logs.first()
    assert log is not None
    assert log.new_value["message_sid"] == "SMaudit_msg_received_02"
    assert "body_length" in log.new_value
    assert log.new_value["is_new_session"] is False


# ==============================================================================
# TEST: FSM Transition — AuditLog FSM_TRANSITION al avanzar de paso
# ==============================================================================
@pytest.mark.django_db
def test_auditlog_fsm_transition_written(tenant) -> None:
    """
    ARRANGE: Tenant existe. Lead en paso VEHICLE_TYPE.
    ACT: POST con respuesta vt_suv.
    ASSERT: AuditLog FSM_TRANSITION creado con old/new state.
    """
    wa_id = "56987654321"
    lead = Lead.objects.create(
        tenant=tenant,
        wa_id=encrypt(wa_id),
        wa_id_hash=hashlib.sha256(wa_id.encode()).hexdigest(),
    )
    session = ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.BOT,
        fsm_answers={"current_step": "VEHICLE_TYPE"},
    )

    client = Client()
    payload = _make_payload("SMfsm_transition_01")
    payload["Body"] = "vt_suv"
    payload["ButtonPayload"] = "vt_suv"

    response = _post_to_worker(client, payload)

    assert response.status_code == 200
    fsm_logs = AuditLog.objects.filter(action="FSM_TRANSITION")
    assert fsm_logs.count() == 1
    log = fsm_logs.first()
    assert log.new_value["status"] == "BOT"


# ==============================================================================
# TEST: Auto-Routing — Modo AUTO asigna automáticamente al vendedor
# ==============================================================================
@pytest.mark.django_db
def test_auto_routing_assigns_in_auto_mode(db, tenant, salesperson) -> None:
    """
    ARRANGE: Tenant en modo AUTO. Hay vendedores activos.
            Sesión en paso PURCHASE_INTENT (último paso antes de PENDING_ASSIGNMENT).
    ACT: POST con mensaje que completa la FSM (pi_hoy).
    ASSERT: Sesión queda en CON_VENDEDOR con salesperson asignado.
    """
    tenant.routing_mode = "AUTO"
    tenant.save()

    wa_id = "56987654321"
    lead = Lead.objects.create(
        tenant=tenant,
        wa_id=encrypt(wa_id),
        wa_id_hash=hashlib.sha256(wa_id.encode()).hexdigest(),
    )
    session = ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.BOT,
        fsm_answers={
            "current_step": "PURCHASE_INTENT",
            "budget_range": "MAS_15M",
            "payment_method": "CONTADO",
        },
    )

    client = Client()
    payload = _make_payload("SMauto_routing_01")
    payload["Body"] = "pi_hoy"

    response = _post_to_worker(client, payload)

    session.refresh_from_db()
    assert response.status_code == 200
    assert session.status == ChatSession.Status.CON_VENDEDOR
    assert session.salesperson_id is not None
    assert session.salesperson_id == salesperson.id


# ==============================================================================
# TEST: Auto-Routing — Modo MANUAL no asigna automáticamente
# ==============================================================================
@pytest.mark.django_db
def test_auto_routing_skips_in_manual_mode(tenant, salesperson) -> None:
    """
    ARRANGE: Tenant en modo MANUAL (default). Hay vendedores activos.
            Sesión en paso PURCHASE_INTENT.
    ACT: POST con mensaje que completa la FSM (pi_hoy).
    ASSERT: Sesión queda en PENDING_ASSIGNMENT (sin asignar).
    """
    assert tenant.routing_mode == "MANUAL"

    wa_id = "56987654321"
    lead = Lead.objects.create(
        tenant=tenant,
        wa_id=encrypt(wa_id),
        wa_id_hash=hashlib.sha256(wa_id.encode()).hexdigest(),
    )
    session = ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.BOT,
        fsm_answers={
            "current_step": "PURCHASE_INTENT",
            "budget_range": "MAS_15M",
            "payment_method": "CONTADO",
        },
    )

    client = Client()
    payload = _make_payload("SMmanual_routing_01")
    payload["Body"] = "pi_hoy"

    response = _post_to_worker(client, payload)

    session.refresh_from_db()
    assert response.status_code == 200
    assert session.status == ChatSession.Status.PENDING_ASSIGNMENT
    assert session.salesperson_id is None


# ==============================================================================
# TEST: Auto-Routing — Sin vendedores no falla el flujo
# ==============================================================================
@pytest.mark.django_db
def test_auto_routing_no_salespeople_no_crash(db, tenant) -> None:
    """
    ARRANGE: Tenant en modo AUTO. NO hay vendedores.
            Sesión en paso PURCHASE_INTENT.
    ACT: POST con mensaje que completa la FSM (pi_hoy).
    ASSERT: Sesión queda en PENDING_ASSIGNMENT. 200 OK (flujo no falla).
    """
    tenant.routing_mode = "AUTO"
    tenant.save()

    wa_id = "56987654321"
    lead = Lead.objects.create(
        tenant=tenant,
        wa_id=encrypt(wa_id),
        wa_id_hash=hashlib.sha256(wa_id.encode()).hexdigest(),
    )
    session = ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.BOT,
        fsm_answers={
            "current_step": "PURCHASE_INTENT",
            "budget_range": "MAS_15M",
            "payment_method": "CONTADO",
        },
    )

    client = Client()
    payload = _make_payload("SMno_sales_01")
    payload["Body"] = "pi_hoy"

    response = _post_to_worker(client, payload)

    session.refresh_from_db()
    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    assert session.status == ChatSession.Status.PENDING_ASSIGNMENT
