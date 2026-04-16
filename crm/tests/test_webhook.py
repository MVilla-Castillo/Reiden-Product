"""
crm/tests/test_webhook.py — Tests para el endpoint público de Twilio Webhook.

Ciclo TDD: Red → Green → Refactor (SKILL: tdd)
Patrón: AAA (Arrange → Act → Assert)

Regla: Prohibido llamadas HTTP reales. Twilio y Cloud Tasks son siempre mocks.
"""

import pytest
from unittest.mock import patch, MagicMock

from django.test import Client

from crm.adapters.dependency_injection import DIContainer


@pytest.fixture(autouse=True)
def _reset_di():
    DIContainer.reset()
    yield
    DIContainer.reset()


# ==============================================================================
# TEST: Happy Path — Firma válida → 200 queued
# ==============================================================================
@pytest.mark.django_db
@patch("crm.adapters.task_queue.railway_task_queue.RailwayTaskQueue.enqueue")
@patch("crm.adapters.messaging.twilio_adapter.TwilioMessageProvider.validate_signature")
def test_valid_signature_returns_200_and_enqueues_task(
    mock_validate: MagicMock,
    mock_enqueue: MagicMock,
) -> None:
    """
    ARRANGE: Firma de Twilio válida, Cloud Tasks responde OK.
    ACT: POST al endpoint de webhook con un payload de Twilio mínimo.
    ASSERT: 200 OK, respuesta JSON con status "queued", Cloud Tasks llamado 1 vez.
    """
    mock_validate.return_value = MagicMock(is_valid=True)
    mock_enqueue.return_value = MagicMock(task_id="tasks/task-001", success=True)

    client = Client()
    twilio_payload = {
        "MessageSid": "SMfake12345678901234567890123456",
        "AccountSid": "ACfake12345678901234567890123456",
        "From": "whatsapp:+56987654321",
        "To": "whatsapp:+56912345678",
        "WaId": "56987654321",
        "Body": "Hola, me interesa un auto",
        "MessageType": "text",
        "NumMedia": "0",
    }

    response = client.post(
        "/api/webhooks/twilio/",
        data=twilio_payload,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    mock_enqueue.assert_called_once()


# ==============================================================================
# TEST: Edge Case 1 — Firma inválida → 403. Cloud Tasks NO llamado.
# ==============================================================================
@pytest.mark.django_db
@patch("crm.adapters.messaging.twilio_adapter.TwilioMessageProvider.validate_signature")
def test_invalid_signature_returns_403(
    mock_validate: MagicMock,
) -> None:
    mock_validate.return_value = MagicMock(is_valid=False)

    client = Client()

    response = client.post(
        "/api/webhooks/twilio/",
        data={"MessageSid": "SMfake", "Body": "hack intent"},
    )

    assert response.status_code == 403


# ==============================================================================
# TEST: Edge Case 2 — Sin header X-Twilio-Signature → 403 (vacío = inválido)
# ==============================================================================
@pytest.mark.django_db
@patch("crm.adapters.messaging.twilio_adapter.TwilioMessageProvider.validate_signature")
def test_missing_signature_header_returns_403(
    mock_validate: MagicMock,
) -> None:
    mock_validate.return_value = MagicMock(is_valid=False)

    client = Client()

    response = client.post(
        "/api/webhooks/twilio/",
        data={"MessageSid": "SMtest"},
    )

    assert response.status_code == 403


# ==============================================================================
# TEST: Edge Case 3 — Payload sin MessageSid → 400 Bad Request
# ==============================================================================
@pytest.mark.django_db
@patch("crm.adapters.messaging.twilio_adapter.TwilioMessageProvider.validate_signature")
def test_missing_message_sid_returns_400(
    mock_validate: MagicMock,
) -> None:
    mock_validate.return_value = MagicMock(is_valid=True)

    client = Client()

    response = client.post(
        "/api/webhooks/twilio/",
        data={"Body": "sin sid"},
    )

    assert response.status_code == 400


# ==============================================================================
# TEST: Multimedia image → 200 con rechazo, Cloud Tasks NO llamado
# ==============================================================================
@pytest.mark.django_db
@patch("crm.adapters.messaging.twilio_adapter.TwilioMessageProvider.validate_signature")
@patch("crm.adapters.messaging.twilio_adapter.TwilioMessageProvider.send_message")
def test_image_message_rejected_without_enqueue(
    mock_send: MagicMock,
    mock_validate: MagicMock,
) -> None:
    mock_validate.return_value = MagicMock(is_valid=True)
    mock_send.return_value = MagicMock(provider_message_id="SM_reject", success=True)

    client = Client()
    response = client.post(
        "/api/webhooks/twilio/",
        data={
            "MessageSid": "SMimage123",
            "From": "whatsapp:+56987654321",
            "To": "whatsapp:+56912345678",
            "MessageType": "image",
            "MediaUrl0": "https://api.twilio.com/media",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected_unsupported_type"
    mock_send.assert_called_once()


# ==============================================================================
# TEST: Multimedia audio → 200 con rechazo, Cloud Tasks NO llamado
# ==============================================================================
@pytest.mark.django_db
@patch("crm.adapters.messaging.twilio_adapter.TwilioMessageProvider.validate_signature")
@patch("crm.adapters.messaging.twilio_adapter.TwilioMessageProvider.send_message")
def test_audio_message_rejected_without_enqueue(
    mock_send: MagicMock,
    mock_validate: MagicMock,
) -> None:
    mock_validate.return_value = MagicMock(is_valid=True)
    mock_send.return_value = MagicMock(provider_message_id="SM_reject", success=True)

    client = Client()
    response = client.post(
        "/api/webhooks/twilio/",
        data={
            "MessageSid": "SMaudio123",
            "From": "whatsapp:+56987654321",
            "To": "whatsapp:+56912345678",
            "MessageType": "audio",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected_unsupported_type"
    mock_send.assert_called_once()


# ==============================================================================
# TEST: Body > 4096 chars → 413, Cloud Tasks NO llamado
# ==============================================================================
@pytest.mark.django_db
@patch("crm.adapters.messaging.twilio_adapter.TwilioMessageProvider.validate_signature")
def test_oversized_body_returns_413(
    mock_validate: MagicMock,
) -> None:
    mock_validate.return_value = MagicMock(is_valid=True)

    client = Client()
    response = client.post(
        "/api/webhooks/twilio/",
        data={
            "MessageSid": "SMlong123",
            "From": "whatsapp:+56987654321",
            "To": "whatsapp:+56912345678",
            "MessageType": "text",
            "Body": "A" * 5000,
        },
    )

    assert response.status_code == 413


# ==============================================================================
# TEST: Button y list_reply → aceptados (son interacciones de texto validas)
# ==============================================================================
@pytest.mark.django_db
@patch("crm.adapters.task_queue.railway_task_queue.RailwayTaskQueue.enqueue")
@patch("crm.adapters.messaging.twilio_adapter.TwilioMessageProvider.validate_signature")
def test_button_message_accepted(
    mock_validate: MagicMock,
    mock_enqueue: MagicMock,
) -> None:
    mock_validate.return_value = MagicMock(is_valid=True)
    mock_enqueue.return_value = MagicMock(task_id="tasks/task-002", success=True)

    client = Client()
    response = client.post(
        "/api/webhooks/twilio/",
        data={
            "MessageSid": "SMbutton123",
            "From": "whatsapp:+56987654321",
            "To": "whatsapp:+56912345678",
            "MessageType": "button",
            "ButtonText": "Ver precios",
            "ButtonPayload": "precios",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    mock_enqueue.assert_called_once()


@pytest.mark.django_db
@patch("crm.adapters.task_queue.railway_task_queue.RailwayTaskQueue.enqueue")
@patch("crm.adapters.messaging.twilio_adapter.TwilioMessageProvider.validate_signature")
def test_list_reply_message_accepted(
    mock_validate: MagicMock,
    mock_enqueue: MagicMock,
) -> None:
    mock_validate.return_value = MagicMock(is_valid=True)
    mock_enqueue.return_value = MagicMock(task_id="tasks/task-003", success=True)

    client = Client()
    response = client.post(
        "/api/webhooks/twilio/",
        data={
            "MessageSid": "SMlistreply123",
            "From": "whatsapp:+56987654321",
            "To": "whatsapp:+56912345678",
            "MessageType": "list_reply",
            "ButtonText": "Sedan",
            "ButtonPayload": "sedan",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    mock_enqueue.assert_called_once()
