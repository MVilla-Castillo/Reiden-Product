"""
crm/tests/test_adapters.py — Infraestructure Adapter Tests.
Garantiza que los adaptadores traduzcan correctamente errores de bajo nivel (SDKs)
a excepciones de dominio y que cumplan con los contratos de los Ports.
"""

import pytest
from unittest.mock import MagicMock, patch
from twilio.base.exceptions import TwilioRestException
import requests
from django.test import override_settings

from crm.adapters.messaging.twilio_adapter import (
    TwilioMessageProvider,
    MessagingError,
    InMemoryMessageProvider,
)
from crm.adapters.task_queue.gcp_tasks_adapter import (
    GcpCloudTasksQueue,
    HttpDispatchQueue,
    TaskQueueError,
)
from crm.domain.ports import (
    SendMessageRequest,
    EnqueueRequest,
    SignatureValidationRequest,
)

# ─────────────────────────────────────────────────────────
# Messaging Adapters (Twilio & In-Memory)
# ─────────────────────────────────────────────────────────


@pytest.fixture
def twilio_provider():
    return TwilioMessageProvider()


@pytest.mark.django_db
@override_settings(TWILIO_ACCOUNT_SID="AC_mock", TWILIO_AUTH_TOKEN="token_mock")
def test_twilio_send_message_success(twilio_provider):
    with patch("crm.adapters.messaging.twilio_adapter.Client") as mock_client:
        # Mock de la respuesta exitosa del SDK de Twilio
        mock_messages = mock_client.return_value.messages
        mock_messages.create.return_value = MagicMock(sid="SM_test_123")

        req = SendMessageRequest(
            to_number="+56911111111", from_number="+56922222222", text="Elite Dev"
        )
        result = twilio_provider.send_message(req)

        assert result.success is True
        assert result.provider_message_id == "SM_test_123"


@pytest.mark.django_db
@override_settings(TWILIO_ACCOUNT_SID="AC_mock", TWILIO_AUTH_TOKEN="token_mock")
def test_twilio_send_message_exception_mapping(twilio_provider):
    """
    Regla de Oro: El adaptador DEBE mapear excepciones del SDK a excepciones de Dominio.
    """
    with patch("crm.adapters.messaging.twilio_adapter.Client") as mock_client:
        mock_client.return_value.messages.create.side_effect = TwilioRestException(
            status=400, msg="Invalid Number", code=21211, uri=""
        )

        req = SendMessageRequest(to_number="invalid", from_number="+123", text="Fail")

        with pytest.raises(MessagingError) as exc_info:
            twilio_provider.send_message(req)

        assert exc_info.value.provider_code == "21211"


def test_in_memory_provider_simulation():
    provider = InMemoryMessageProvider()
    req = SendMessageRequest(to_number="123", from_number="456", text="Ghost")

    result = provider.send_message(req)

    assert result.success is True
    assert len(provider.sent_messages) == 1
    assert provider.sent_messages[0].text == "Ghost"


# ─────────────────────────────────────────────────────────
# Task Queue Adapters (GCP & HTTP)
# ─────────────────────────────────────────────────────────


def test_gcp_cloud_tasks_enqueue_success():
    # El patch debe apuntar a la importación dentro del módulo o al path absoluto del SDK
    with patch("google.cloud.tasks_v2.CloudTasksClient") as mock_client_cls:
        mock_instance = mock_client_cls.return_value
        mock_instance.create_task.return_value = MagicMock(name="task_path")

        adapter = GcpCloudTasksQueue()
        req = EnqueueRequest(payload={"id": 1})

        adapter.enqueue(req)

        assert mock_instance.create_task.called


def test_http_dispatch_queue_connection_error():
    """
    Validamos resiliencia: Si el despachador HTTP falla por red,
    el sistema debe saber que es un error de infraestructura.
    """
    adapter = HttpDispatchQueue()
    req = EnqueueRequest(payload={})

    with patch("requests.post") as mock_post:
        mock_post.side_effect = requests.ConnectionError("Network down")

        with pytest.raises(TaskQueueError):
            adapter.enqueue(req)


# ─────────────────────────────────────────────────────────
# Twilio Signature Validation (Mocks Correctos)
# ─────────────────────────────────────────────────────────


@override_settings(TWILIO_AUTH_TOKEN="test_token")
def test_twilio_validate_signature_mocked(twilio_provider):
    with patch(
        "crm.adapters.messaging.twilio_adapter.RequestValidator"
    ) as mock_val_cls:
        mock_val = mock_val_cls.return_value
        mock_val.validate.return_value = True

        req = SignatureValidationRequest(
            url="https://webhook.com", post_data={"Body": "Hi"}, signature="valid_sig"
        )

        result = twilio_provider.validate_signature(req)

        assert result.is_valid is True


def test_http_dispatch_queue_success():
    """Happy path: HttpDispatchQueue envía POST y retorna éxito."""
    adapter = HttpDispatchQueue()
    req = EnqueueRequest(payload={"MessageSid": "SM_test"})

    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = adapter.enqueue(req)

        assert result.success is True
        assert mock_post.called


def test_inmemory_validate_signature_always_valid():
    """InMemoryMessageProvider acepta todas las firmas."""
    provider = InMemoryMessageProvider()
    req = SignatureValidationRequest(
        url="https://example.com", post_data={}, signature="fake"
    )

    result = provider.validate_signature(req)

    assert result.is_valid is True
