"""
crm/tests/test_twilio_client.py — Tests del cliente Twilio.

Validamos que el wrapper de Twilio funcione correctamente llamando
al SDK con los parámetros adecuados, utilizando Mocks.
"""
from unittest.mock import patch, MagicMock
from django.test import override_settings
from crm.services.twilio_client import send_whatsapp_message


@override_settings(TWILIO_ACCOUNT_SID='ACfake', TWILIO_AUTH_TOKEN='fake_token')
@patch('crm.services.twilio_client.Client')
def test_send_whatsapp_message_success(mock_client_class: MagicMock) -> None:
    """Verifica que se llama al cliente Twilio internamente con `whatsapp:` prefix."""
    # ARRANGE
    mock_instance = mock_client_class.return_value
    mock_create = mock_instance.messages.create
    mock_message = MagicMock()
    mock_message.sid = "SM12345"
    mock_create.return_value = mock_message

    # ACT
    sid = send_whatsapp_message("56912345678", "Respuesta de prueba")

    # ASSERT
    assert sid == "SM12345"
    mock_create.assert_called_once()
    kwargs = mock_create.call_args[1]
    assert kwargs['to'] == "whatsapp:+56912345678"
    assert kwargs['body'] == "Respuesta de prueba"


@override_settings(TWILIO_ACCOUNT_SID='ACfake', TWILIO_AUTH_TOKEN='fake_token')
@patch('crm.services.twilio_client.Client')
def test_send_whatsapp_message_with_interactive_payload(mock_client_class: MagicMock) -> None:

    """Verifica el fallback de texto para payload interactivo en V1."""
    # ARRANGE
    mock_instance = mock_client_class.return_value
    mock_create = mock_instance.messages.create

    interactive = {
        "buttons": [
            {"title": "Opcion A"},
            {"title": "Opcion B"}
        ]
    }

    # ACT
    send_whatsapp_message("56912345678", "Elige", interactive_payload=interactive)

    # ASSERT
    mock_create.assert_called_once()
    kwargs = mock_create.call_args[1]
    assert "Elige" in kwargs['body']
    assert "Opcion A" in kwargs['body']
    assert "Opcion B" in kwargs['body']

@override_settings(TWILIO_ACCOUNT_SID='ACfake', TWILIO_AUTH_TOKEN='fake_token')
@patch('crm.services.twilio_client.Client')
def test_send_whatsapp_message_with_content_sid(mock_client_class: MagicMock) -> None:
    """Verifica que se usa content_sid (Botones Reales) si se provee."""
    # ARRANGE
    mock_instance = mock_client_class.return_value
    mock_create = mock_instance.messages.create

    # ACT
    send_whatsapp_message("56912345678", "Texto ignorado", content_sid="HX123", content_variables='{"name": "foo"}')

    # ASSERT
    mock_create.assert_called_once()
    kwargs = mock_create.call_args[1]
    assert kwargs['content_sid'] == "HX123"
    assert kwargs['content_variables'] == '{"name": "foo"}'
    assert 'body' not in kwargs
