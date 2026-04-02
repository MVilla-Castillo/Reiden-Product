"""
crm/views/webhook.py — Vista delgada: valida firma y encola via TaskQueue port.

Responsabilidades únicas:
1. Validar firma Twilio via MessageProvider port
2. Construir payload limpio
3. Encolar via TaskQueue port
4. Responder a Twilio
"""

from __future__ import annotations

import logging
from typing import Any

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from crm.adapters.dependency_injection import DIContainer, get_task_queue
from crm.adapters.messaging.twilio_adapter import SignatureValidationError
from crm.adapters.task_queue.gcp_tasks_adapter import TaskQueueError
from crm.domain.ports import EnqueueRequest, SignatureValidationRequest

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def twilio_webhook_view(request: HttpRequest) -> JsonResponse:
    provider = DIContainer.instance().message_provider
    post_data = request.POST.dict()
    validation_request = SignatureValidationRequest(
        url=request.build_absolute_uri(),
        post_data=post_data,
        signature=request.headers.get("X-Twilio-Signature", ""),
    )

    try:
        if not provider.validate_signature(validation_request).is_valid:
            logger.warning(
                "Webhook rechazado: firma inválida.",
                extra={"component_name": "twilio_webhook_view"},
            )
            return JsonResponse({"error": "Forbidden"}, status=403)
    except SignatureValidationError:
        logger.error(
            "Webhook rechazado: error de validación de firma.",
            extra={"component_name": "twilio_webhook_view"},
        )
        return JsonResponse({"error": "Forbidden"}, status=403)

    message_sid = request.POST.get("MessageSid", "")
    if not message_sid:
        logger.warning(
            "Webhook sin MessageSid.",
            extra={"component_name": "twilio_webhook_view"},
        )
        return JsonResponse({"error": "Bad Request: MessageSid requerido"}, status=400)

    payload: dict[str, Any] = {
        "MessageSid": message_sid,
        "AccountSid": request.POST.get("AccountSid", ""),
        "From": request.POST.get("From", ""),
        "To": request.POST.get("To", ""),
        "WaId": request.POST.get("WaId", ""),
        "Body": request.POST.get("Body", ""),
        "ButtonText": request.POST.get("ButtonText", ""),
        "ButtonPayload": request.POST.get("ButtonPayload", ""),
        "MessageType": request.POST.get("MessageType", "text"),
        "NumMedia": request.POST.get("NumMedia", "0"),
        "MediaUrl0": request.POST.get("MediaUrl0", ""),
        "MediaContentType0": request.POST.get("MediaContentType0", ""),
        "ReferralNumMedia": request.POST.get("ReferralNumMedia", "0"),
        "ReferralSourceType": request.POST.get("ReferralSourceType", ""),
        "ReferralSourceUrl": request.POST.get("ReferralSourceUrl", ""),
        "ListId": request.POST.get("ListId", ""),
        "ListTitle": request.POST.get("ListTitle", ""),
        "Timestamp": request.POST.get("Timestamp", ""),
    }

    try:
        queue = get_task_queue()
        result = queue.enqueue(EnqueueRequest(payload=payload))
    except TaskQueueError:
        logger.exception(
            "Fallo crítico al encolar.",
            extra={
                "component_name": "twilio_webhook_view",
                "message_sid": message_sid,
            },
        )
        return JsonResponse({"error": "internal_error"}, status=500)
    except Exception:
        logger.exception(
            "Fallo inesperado al encolar.",
            extra={
                "component_name": "twilio_webhook_view",
                "message_sid": message_sid,
            },
        )
        return JsonResponse({"error": "internal_error"}, status=500)

    logger.info(
        "Webhook encolado exitosamente.",
        extra={
            "component_name": "twilio_webhook_view",
            "message_sid": message_sid,
            "task_name": result.task_id,
        },
    )

    return JsonResponse({"status": "queued"}, status=200)
