"""
crm/services/twilio_validator.py

Servicio de validación criptográfica de Webhooks de Twilio (SKILL: api_security §1).
Responsabilidad única: verificar que el request proviene de Twilio mediante HMAC-SHA1.
Funciones puras y sin side-effects: completamente testeables con mocks.
"""
import logging

from django.conf import settings
from django.http import HttpRequest
from twilio.request_validator import RequestValidator

logger = logging.getLogger(__name__)


def validate_twilio_signature(request: HttpRequest) -> bool:
    """
    Valida la firma criptográfica `X-Twilio-Signature` (HMAC-SHA1).

    Usa la URL absoluta del request y el cuerpo POST como inputs del hash,
    lo que garantiza que un atacante no puede replayar el request desde otro dominio.

    Args:
        request: El HttpRequest de Django con headers y datos POST.

    Returns:
        True si la firma es válida, False en cualquier otro caso.
    """
    auth_token: str = getattr(settings, 'TWILIO_AUTH_TOKEN', '')

    if not auth_token:
        # Configuración incorrecta: el sistema no puede operar sin este secreto.
        logger.error(
            "TWILIO_AUTH_TOKEN no configurado. Rechazando Webhook.",
            extra={"component_name": "twilio_validator"},
        )
        return False

    validator = RequestValidator(auth_token)
    url = request.build_absolute_uri()
    signature = request.headers.get('X-Twilio-Signature', '')

    is_valid = validator.validate(url, request.POST, signature)

    if not is_valid:
        logger.warning(
            "Firma X-Twilio-Signature inválida. Posible intento de spoofing.",
            extra={"component_name": "twilio_validator", "url": url},
        )

    return is_valid
