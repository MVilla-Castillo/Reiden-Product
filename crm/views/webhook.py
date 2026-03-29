"""
crm/views/webhook.py

Vista pública: POST /api/webhooks/twilio/
Responsabilidad: validar firma y encolar payload en Cloud Tasks en <100ms.

REGLAS CLAVE (SKILL: api_security + high_concurrency):
- NO toca la base de datos. Eso es responsabilidad del Worker.
- Responde 200 OK tan rápido como sea posible.
"""
import logging
from typing import Any

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from crm.services.cloud_tasks import enqueue_webhook_payload
from crm.services.twilio_validator import validate_twilio_signature

logger = logging.getLogger(__name__)


@csrf_exempt  # Twilio no envía CSRF tokens; la seguridad viene de validate_twilio_signature
@require_POST
def twilio_webhook_view(request: HttpRequest) -> JsonResponse:

    # PASO 1: Validación Criptográfica (Regla #1 - SKILL api_security §1)
    if not validate_twilio_signature(request):
        logger.warning(
            "Webhook rechazado: firma inválida.",
            extra={"component_name": "twilio_webhook_view"},
        )
        return JsonResponse({"error": "Forbidden"}, status=403)

    # PASO 2: Extracción Defensiva del Payload (RNF-10, SKILL api_security §2)
    # Prohibido usar request.POST['key'] → usar .get() para evitar KeyError
    message_sid: str = request.POST.get('MessageSid', '')
    if not message_sid:
        logger.warning(
            "Webhook sin MessageSid. Payload malformado.",
            extra={"component_name": "twilio_webhook_view"},
        )
        return JsonResponse({"error": "Bad Request: MessageSid requerido"}, status=400)

    # Construir el payload limpio con solo lo que necesitamos
    payload: dict[str, Any] = {
        # Identificadores de idempotencia
        "MessageSid": message_sid,
        "AccountSid": request.POST.get('AccountSid', ''),
        # Identidad del lead
        "From": request.POST.get('From', ''),
        "To": request.POST.get('To', ''),
        "WaId": request.POST.get('WaId', ''),
        # Contenido del mensaje
        "Body": request.POST.get('Body', ''),
        "ButtonText": request.POST.get('ButtonText', ''),
        "ButtonPayload": request.POST.get('ButtonPayload', ''),
        # Tipo de mensaje
        "MessageType": request.POST.get('MessageType', 'text'),
        "NumMedia": request.POST.get('NumMedia', '0'),
        "MediaUrl0": request.POST.get('MediaUrl0', ''),
        "MediaContentType0": request.POST.get('MediaContentType0', ''),
        # Atribución publicitaria (RF-02, solo para poblar en segundo plano)
        "ReferralNumMedia": request.POST.get('ReferralNumMedia', '0'),
        "ReferralSourceType": request.POST.get('ReferralSourceType', ''),
        "ReferralSourceUrl": request.POST.get('ReferralSourceUrl', ''),
        # Respuestas a listas interactivas (RF-26)
        "ListId": request.POST.get('ListId', ''),
        "ListTitle": request.POST.get('ListTitle', ''),
        # Timestamp nativo de Twilio para idempotencia de la FSM (RF-03)
        "Timestamp": request.POST.get('Timestamp', ''),
    }

    # PASO 3: Encolamiento Asíncrono en Cloud Tasks (SKILL high_concurrency §1)
    # Esta llamada HTTP a GCP es la única operación externa. No hay DB aquí.
    try:
        task_name = enqueue_webhook_payload(payload)
        logger.info(
            "Webhook encolado exitosamente.",
            extra={
                "component_name": "twilio_webhook_view",
                "message_sid": message_sid,
                "task_name": task_name,
            },
        )
    except Exception:
        logger.exception(
            "Fallo crítico al encolar en Cloud Tasks.",
            extra={
                "component_name": "twilio_webhook_view",
                "message_sid": message_sid,
            },
        )
        # Retornamos 500 para que Twilio reintente el webhook automáticamente
        return JsonResponse({"error": "internal_error"}, status=500)

    # PASO 4: Respuesta inmediata a Twilio
    return JsonResponse({"status": "queued"}, status=200)
