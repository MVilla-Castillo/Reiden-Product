"""
crm/tests/test_webhook.py — Tests para el endpoint público de Twilio Webhook.

Ciclo TDD: Red → Green → Refactor (SKILL: tdd)
Patrón: AAA (Arrange → Act → Assert)

Regla: Prohibido llamadas HTTP reales. Twilio y Cloud Tasks son siempre mocks.
"""
import pytest
from unittest.mock import patch, MagicMock

from django.test import Client


# ==============================================================================
# TEST: Happy Path — Firma válida → 200 queued
# ==============================================================================
@pytest.mark.django_db
@patch('crm.views.webhook.enqueue_webhook_payload')
@patch('crm.views.webhook.validate_twilio_signature')
def test_valid_signature_returns_200_and_enqueues_task(
    mock_validate: MagicMock,
    mock_enqueue: MagicMock,
) -> None:
    """
    ARRANGE: Firma de Twilio válida, Cloud Tasks responde OK.
    ACT: POST al endpoint de webhook con un payload de Twilio mínimo.
    ASSERT: 200 OK, respuesta JSON con status "queued", Cloud Tasks llamado 1 vez.
    """
    # ARRANGE
    mock_validate.return_value = True
    mock_enqueue.return_value = "projects/ccrm/queues/webhook-tasks/tasks/task-001"

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

    # ACT
    response = client.post(
        '/api/webhooks/twilio/',
        data=twilio_payload,
    )


    # ASSERT
    assert response.status_code == 200
    assert response.json()['status'] == 'queued'
    mock_enqueue.assert_called_once()
    call_args = mock_enqueue.call_args[0][0]
    assert call_args['MessageSid'] == "SMfake12345678901234567890123456"


# ==============================================================================
# TEST: Edge Case 1 — Firma inválida → 403. Cloud Tasks NO llamado.
# ==============================================================================
@pytest.mark.django_db
@patch('crm.views.webhook.enqueue_webhook_payload')
@patch('crm.views.webhook.validate_twilio_signature')
def test_invalid_signature_returns_403(
    mock_validate: MagicMock,
    mock_enqueue: MagicMock,
) -> None:
    """
    ARRANGE: La función de validación retorna False (firma falsa/spoofing).
    ACT: POST al endpoint.
    ASSERT: 403 Forbidden. Cloud Tasks NO es llamado (no se encola basura).
    """
    # ARRANGE
    mock_validate.return_value = False

    client = Client()

    # ACT
    response = client.post(
        '/api/webhooks/twilio/',
        data={"MessageSid": "SMfake", "Body": "hack intent"},
    )


    # ASSERT
    assert response.status_code == 403
    mock_enqueue.assert_not_called()


# ==============================================================================
# TEST: Edge Case 2 — Sin header X-Twilio-Signature → 403 (vacío = inválido)
# ==============================================================================
@pytest.mark.django_db
@patch('crm.views.webhook.enqueue_webhook_payload')
@patch('crm.views.webhook.validate_twilio_signature')
def test_missing_signature_header_returns_403(
    mock_validate: MagicMock,
    mock_enqueue: MagicMock,
) -> None:
    """
    ARRANGE: validate_twilio_signature retorna False al no encontrar header.
    ACT: POST sin header de firma.
    ASSERT: 403 Forbidden.
    """
    # ARRANGE — Twilio validator falla si el header está vacío
    mock_validate.return_value = False

    client = Client()

    # ACT
    response = client.post(
        '/api/webhooks/twilio/',
        data={"MessageSid": "SMtest"},
    )


    # ASSERT
    assert response.status_code == 403
    mock_enqueue.assert_not_called()


# ==============================================================================
# TEST: Edge Case 3 — Payload sin MessageSid → 400 Bad Request
# ==============================================================================
@pytest.mark.django_db
@patch('crm.views.webhook.enqueue_webhook_payload')
@patch('crm.views.webhook.validate_twilio_signature')
def test_missing_message_sid_returns_400(
    mock_validate: MagicMock,
    mock_enqueue: MagicMock,
) -> None:
    """
    ARRANGE: Firma válida pero payload sin MessageSid (payload malformado de Twilio).
    ACT: POST al endpoint.
    ASSERT: 400 Bad Request. No se encola.
    """
    # ARRANGE
    mock_validate.return_value = True

    client = Client()

    # ACT
    response = client.post(
        '/api/webhooks/twilio/',
        data={"Body": "sin sid"},
    )


    # ASSERT
    assert response.status_code == 400
    mock_enqueue.assert_not_called()
