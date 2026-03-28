"""
crm/services/twilio_client.py — Cliente para envío de mensajes por WhatsApp vía Twilio.

Actúa como una capa de abstracción sobre el SDK de Twilio.
Permite mockear fácilmente en los tests (Clean Architecture).
"""
import logging
from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from twilio.http.http_client import TwilioHttpClient

logger = logging.getLogger(__name__)


def send_whatsapp_message(
    to_number: str, 
    text: str, 
    from_number: str = None, 
    interactive_payload: dict = None,
    content_sid: str = None,
    content_variables: str = None
) -> str:
    """
    Envía un mensaje de texto o interactivo vía Twilio WhatsApp.
    Soporta Content API para botones reales.
    """
    import uuid
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.error("Twilio credentials missing. Returning simulated SID.")
        return f"SIM_{uuid.uuid4().hex[:8]}"

    # SRE Grade: 5s rule to avoid Connection Pool Exhaustion on Twilio slowdowns
    http_client = TwilioHttpClient(timeout=5.0)
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, http_client=http_client)
    
    # Twilio requiere el prefijo whatsapp:
    to_whatsapp = f"whatsapp:+{to_number}" if not to_number.startswith("whatsapp:") else to_number
    
    from_whatsapp = f"whatsapp:+{from_number}" if from_number and not from_number.startswith("whatsapp:") else (f"whatsapp:+{from_number}" if from_number else "whatsapp:+14155238886")

    # Lógica de construcción del mensaje
    params = {
        "from_": from_whatsapp,
        "to": to_whatsapp,
    }

    if content_sid:
        # Modo Content API (Botones Reales)
        params["content_sid"] = content_sid
        if content_variables:
            params["content_variables"] = content_variables
    else:
        # Modo Legacy / Texto Plano
        body_text = text
        if interactive_payload:
            options = [btn["title"] for btn in interactive_payload.get("buttons", [])]
            if options:
                body_text += "\n\nOpciones:\n- " + "\n- ".join(options)
        params["body"] = body_text

    try:
        message = client.messages.create(**params)
        logger.info(
            f"Mensaje enviado correctamente (ContentSid: {content_sid}) a {to_whatsapp}",
            extra={"message_sid": message.sid, "component_name": "twilio_client"}
        )
        return message.sid
    except TwilioRestException as e:
        logger.error(
            f"Error Twilio: [Status: {e.status}] [Código: {e.code}] [Mensaje: {e.msg}]",
            extra={ "to": to_whatsapp, "component_name": "twilio_client" }
        )
        return None
