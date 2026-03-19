"""
crm/services/twilio_client.py — Cliente para envío de mensajes por WhatsApp vía Twilio.

Actúa como una capa de abstracción sobre el SDK de Twilio.
Permite mockear fácilmente en los tests (Clean Architecture).
"""
import logging
from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)


def send_whatsapp_message(to_number: str, text: str, interactive_payload: dict = None) -> str:
    """
    Envía un mensaje de texto o interactivo vía Twilio WhatsApp.

    Args:
        to_number: Número destino (ej. "56912345678").
        text: Texto principal del mensaje.
        interactive_payload: Opcional, para botones interactivos o listas.

    Returns:
        str: El MessageSid generado por Twilio.
    """
    import uuid
    # Defensive check
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.error("Twilio credentials not configured in settings. Returning simulated unique SID.")
        return f"SIM_MISSING_CRED_{uuid.uuid4().hex[:8]}"

    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    # Twilio requiere el prefijo whatsapp:
    to_whatsapp = f"whatsapp:+{to_number}" if not to_number.startswith("whatsapp:") else to_number
    # Para la V1 asumimos que el "From" es el mismo número del tenant, aquí hardcodeado por simplicidad,
    # pero en un multi-tenant real debería venir de config de base de datos o environment.
    from_whatsapp = "whatsapp:+14155238886"  # Sandbox default o env var

    # TODO: Implementar el paso de payload interactivo cuando Twilio Content API o Whatsapp Template lo exija.
    # Por ahora en V1 enviamos texto plano estructurado
    body_text = text
    if interactive_payload:
        options = [btn["title"] for btn in interactive_payload.get("buttons", [])]
        if options:
            body_text += "\n\nOpciones:\n- " + "\n- ".join(options)

    try:
        message = client.messages.create(
            from_=from_whatsapp,
            body=body_text,
            to=to_whatsapp
        )
        logger.info(
            f"Mensaje enviado correctamente vía Twilio a {to_whatsapp}",
            extra={"message_sid": message.sid, "component_name": "twilio_client"}
        )
        return message.sid

    except TwilioRestException as e:
        logger.error(
            f"Error enviando mensaje Twilio a {to_whatsapp}",
            exc_info=True,
            extra={"component_name": "twilio_client"}
        )
        # We don't raise it to prevent crashing the worker, we just log and return None,
        # but depending on business logic we might want to Queue for retry.
        return None
