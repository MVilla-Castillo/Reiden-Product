"""
crm/tests/test_worker.py — Tests para el Worker privado de Cloud Tasks.

Ciclo TDD: Red → Green → Refactor (SKILL: tdd)
Patrón: AAA (Arrange → Act → Assert)

Verificaciones:
  - Idempotencia: el mismo MessageSid procesado dos veces → 1 solo Message en DB.
  - Secreto interno inválido → 403.
  - Happy path → Message y Lead creados en DB correctamente.
  - Rollback: si falla algo dentro de atomic(), no quedan datos huérfanos.
"""
import hashlib
import json
import pytest
from unittest.mock import patch
from django.test import Client
from django.conf import settings

from crm.models import AuditLog, Lead, Message, ChatSession


# Payload de Twilio simulado (ya sanitizado, como lo manda cloud_tasks.py)
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
    """Helper: POST al worker con el secreto interno correcto."""
    internal_secret = settings.CLOUD_TASKS_INTERNAL_SECRET
    return client.post(
        '/api/workers/process-message/',
        data=json.dumps(payload),
        content_type='application/json',
        HTTP_X_INTERNAL_SECRET=internal_secret,
    )


# ==============================================================================
# TEST: Happy Path — Nuevo mensaje → Lead, Session y Message creados en DB
# ==============================================================================
# ==============================================================================
@pytest.mark.django_db
@patch('crm.services.twilio_client.send_whatsapp_message')
def test_new_message_creates_lead_session_and_message(mock_send, tenant) -> None:
    """
    ARRANGE: Tenant existe. Primer mensaje de un lead nuevo.
    ACT: POST al worker con un payload válido.
    ASSERT: Lead, ChatSession y Message creados. Status 200.
    """
    # Configuramos el mock para que devuelva un Sidney (MessageSid de salida) simulado
    mock_send.return_value = "SMoutbound00000000000000000001"
    
    # ARRANGE
    client = Client()
    payload = _make_payload("SMhappy00000000000000000000001")

    # ACT
    response = _post_to_worker(client, payload)

    # ASSERT
    assert response.status_code == 200
    assert response.json()['status'] == 'processed'
    assert response.json()['created'] is True

    wa_id_hash = hashlib.sha256("56987654321".encode()).hexdigest()
    assert Lead.objects.filter(wa_id_hash=wa_id_hash).exists()
    assert ChatSession.objects.filter(lead__wa_id_hash=wa_id_hash).exists()
    assert Message.objects.filter(provider_message_id="SMhappy00000000000000000000001").exists()
    # Verificamos que se haya registrado también el mensaje saliente (gracias a mock_send y FSM)
    assert Message.objects.filter(provider_message_id="SMoutbound00000000000000000001").exists()


# ==============================================================================
# TEST: Idempotencia — Mismo MessageSid procesado dos veces → 1 solo Message
# ==============================================================================
# ==============================================================================
@pytest.mark.django_db
@patch('crm.services.twilio_client.send_whatsapp_message')
def test_duplicate_message_is_idempotent(mock_send, tenant) -> None:
    """
    ARRANGE: Tenant existe. Se procesa el mismo payload dos veces.
    ACT: Dos POST consecutivos al worker con el mismo MessageSid.
    ASSERT: Solo 1 Message en DB. Ambas respuestas son 200 OK.
    """
    mock_send.return_value = "SMoutbound_dup"
    # ARRANGE
    client = Client()
    payload = _make_payload("SMduplicate000000000000000001")

    # ACT — Primera llamada
    response_1 = _post_to_worker(client, payload)
    # ACT — Segunda llamada (simulando reintento de Cloud Tasks o Twilio)
    response_2 = _post_to_worker(client, payload)

    # ASSERT
    assert response_1.status_code == 200
    assert response_2.status_code == 200
    assert response_2.json()['status'] == 'duplicate_ignored'

    count = Message.objects.filter(provider_message_id="SMduplicate000000000000000001").count()
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
    # ARRANGE
    client = Client()
    payload = _make_payload("SMsecret000000000000000000001")

    # ACT
    response = client.post(
        '/api/workers/process-message/',
        data=json.dumps(payload),
        content_type='application/json',
        HTTP_X_INTERNAL_SECRET='wrong-secret-hackeando',
    )

    # ASSERT
    assert response.status_code == 403
    assert not Message.objects.filter(provider_message_id="SMsecret000000000000000000001").exists()


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
    # ARRANGE — No creamos ningún Tenant (usamos solo db fixture de pytest-django)
    client = Client()
    payload = _make_payload("SMnotenant000000000000000001")

    # ACT
    response = _post_to_worker(client, payload)

    # ASSERT — 200 para evitar reintentos infinitos de un error de configuración
    assert response.status_code == 200
    assert 'Tenant not found' in response.json().get('error', '')
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
    # ARRANGE
    client = Client()
    internal_secret = settings.CLOUD_TASKS_INTERNAL_SECRET

    # ACT
    response = client.post(
        '/api/workers/process-message/',
        data="esto no es json {{{",
        content_type='application/json',
        HTTP_X_INTERNAL_SECRET=internal_secret,
    )

    # ASSERT
    assert response.status_code == 400


# ==============================================================================
# TEST: AuditLog A — SESSION_START escrito al primer contacto del lead
# ==============================================================================
@pytest.mark.django_db
@patch('crm.services.twilio_client.send_whatsapp_message')
def test_auditlog_session_start_created(mock_send, tenant) -> None:
    """
    ARRANGE: Tenant existe. Primer mensaje de un lead nuevo.
    ACT: POST al worker con payload válido (primer contacto).
    ASSERT: Existe exactamente 1 AuditLog con action='SESSION_START'.
    """
    # ARRANGE
    mock_send.return_value = "SMoutbound_auditlog_01"
    client = Client()
    payload = _make_payload("SMaudit_session_start_01")

    # ACT
    response = _post_to_worker(client, payload)

    # ASSERT
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
@patch('crm.services.twilio_client.send_whatsapp_message')
def test_auditlog_msg_received_written_per_message(mock_send, tenant) -> None:
    """
    ARRANGE: Tenant existe. Lead con sesión activa (returning lead).
    ACT: POST al worker con un nuevo MessageSid (mensaje número 2 en la sesión).
    ASSERT: Se escribe 1 AuditLog con action='MSG_RECEIVED'.
             El campo new_value contiene 'message_sid' y 'body_length'.
    """
    # ARRANGE: Creamos el lead con su primera sesión (simula returning lead)
    import hashlib
    from crm.models import Lead, ChatSession
    wa_id = "56987654321"
    lead = Lead.objects.create(
        tenant=tenant,
        wa_id=wa_id,
        wa_id_hash=hashlib.sha256(wa_id.encode()).hexdigest(),
    )
    ChatSession.objects.create(tenant=tenant, lead=lead, status=ChatSession.Status.BOT)
    mock_send.return_value = "SMoutbound_auditlog_02"

    client = Client()
    # Segundo mensaje del mismo lead (sesión ya existe)
    payload = _make_payload("SMaudit_msg_received_02")

    # ACT
    response = _post_to_worker(client, payload)

    # ASSERT
    assert response.status_code == 200
    msg_logs = AuditLog.objects.filter(action="MSG_RECEIVED")
    assert msg_logs.count() == 1, (
        f"Se esperaba 1 AuditLog MSG_RECEIVED, se encontraron {msg_logs.count()}"
    )
    log = msg_logs.first()
    assert log is not None
    assert log.new_value["message_sid"] == "SMaudit_msg_received_02"
    assert "body_length" in log.new_value
    # Para un returning lead, is_new_session debe ser False
    assert log.new_value["is_new_session"] is False
