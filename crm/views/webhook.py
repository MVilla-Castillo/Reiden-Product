"""
crm/views/webhook.py — Vista delgada: valida firma, filtra tipo y encola via TaskQueue port.

Responsabilidades únicas:
1. Validar firma Twilio via MessageProvider port
2. Rechazar multimedia temprano (solo texto soportado)
3. Construir payload limpio con limites por campo
4. Encolar via TaskQueue port
5. Responder a Twilio
"""

from __future__ import annotations

import logging
from typing import Any

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from crm.adapters.dependency_injection import DIContainer, get_task_queue
from crm.adapters.messaging.twilio_adapter import (
    MessagingError,
    SignatureValidationError,
)
from crm.adapters.task_queue.gcp_tasks_adapter import TaskQueueError
from crm.domain.ports import (
    EnqueueRequest,
    SendMessageRequest,
    SignatureValidationRequest,
)
from core.log_utils import trace_id_var

logger = logging.getLogger(__name__)

ALLOWED_MESSAGE_TYPES = {"text", "button", "list", "button_reply", "list_reply"}
REJECTION_TEXT = "Por el momento solo podemos recibir mensajes de texto. Las imagenes, audios y documentos no son soportados aun."

MAX_BODY_LENGTH = 4096
MESSAGE_SID_MAX_LENGTH = 255
FROM_MAX_LENGTH = 64
TO_MAX_LENGTH = 64
WA_ID_MAX_LENGTH = 32
BUTTON_TEXT_MAX_LENGTH = 255
BUTTON_PAYLOAD_MAX_LENGTH = 255
MEDIA_URL_MAX_LENGTH = 2048
REFERRAL_SOURCE_URL_MAX_LENGTH = 2048
LIST_TITLE_MAX_LENGTH = 255


def _truncate(value: str, max_length: int) -> str:
    if len(value) > max_length:
        return value[:max_length]
    return value


def _send_rejection(provider, from_raw: str, to_raw: str, message_sid: str) -> None:
    """Envia mensaje de rechazo por multimedia sin encolar a Cloud Tasks."""
    phone_to = from_raw.replace("whatsapp:", "").lstrip("+")
    phone_from = to_raw.replace("whatsapp:", "").lstrip("+")
    try:
        provider.send_message(
            SendMessageRequest(
                to_number=phone_to,
                from_number=phone_from,
                text=REJECTION_TEXT,
            )
        )
    except MessagingError:
        logger.exception(
            "Webhook: No se pudo enviar rechazo de multimedia.",
            extra={
                "component_name": "twilio_webhook_view",
                "message_sid": message_sid,
            },
        )


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
                "Webhook rechazado: firma invalida.",
                extra={"component_name": "twilio_webhook_view"},
            )
            return JsonResponse({"error": "Forbidden"}, status=403)
    except SignatureValidationError:
        logger.error(
            "Webhook rechazado: error de validacion de firma.",
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

    # Filtrar tipo de mensaje: solo texto permitido
    raw_type = request.POST.get("MessageType", "text").lower()
    if raw_type not in ALLOWED_MESSAGE_TYPES:
        logger.info(
            "Webhook: tipo de mensaje no soportado. Rechazando.",
            extra={
                "component_name": "twilio_webhook_view",
                "message_sid": message_sid,
                "message_type": raw_type,
            },
        )
        _send_rejection(
            provider,
            request.POST.get("From", ""),
            request.POST.get("To", ""),
            message_sid,
        )
        return JsonResponse({"status": "rejected_unsupported_type"}, status=200)

    # Validar tamaño del body
    body_raw = request.POST.get("Body", "")
    if len(body_raw) > MAX_BODY_LENGTH:
        logger.warning(
            "Webhook: Body excede limite permitido.",
            extra={
                "component_name": "twilio_webhook_view",
                "message_sid": message_sid,
                "body_length": len(body_raw),
            },
        )
        return JsonResponse({"error": "Bad Request: Message too long"}, status=413)

    payload: dict[str, Any] = {
        "trace_id": trace_id_var.get(),
        "MessageSid": _truncate(message_sid, MESSAGE_SID_MAX_LENGTH),
        "AccountSid": _truncate(
            request.POST.get("AccountSid", ""), MESSAGE_SID_MAX_LENGTH
        ),
        "From": _truncate(request.POST.get("From", ""), FROM_MAX_LENGTH),
        "To": _truncate(request.POST.get("To", ""), TO_MAX_LENGTH),
        "WaId": _truncate(request.POST.get("WaId", ""), WA_ID_MAX_LENGTH),
        "Body": body_raw,
        "ButtonText": _truncate(
            request.POST.get("ButtonText", ""), BUTTON_TEXT_MAX_LENGTH
        ),
        "ButtonPayload": _truncate(
            request.POST.get("ButtonPayload", ""), BUTTON_PAYLOAD_MAX_LENGTH
        ),
        "MessageType": _truncate(raw_type, 32),
        "NumMedia": _truncate(request.POST.get("NumMedia", "0"), 4),
        "MediaUrl0": _truncate(request.POST.get("MediaUrl0", ""), MEDIA_URL_MAX_LENGTH),
        "MediaContentType0": _truncate(request.POST.get("MediaContentType0", ""), 128),
        "ReferralNumMedia": _truncate(request.POST.get("ReferralNumMedia", "0"), 4),
        "ReferralSourceType": _truncate(
            request.POST.get("ReferralSourceType", ""), 128
        ),
        "ReferralSourceUrl": _truncate(
            request.POST.get("ReferralSourceUrl", ""), REFERRAL_SOURCE_URL_MAX_LENGTH
        ),
        "ListId": _truncate(request.POST.get("ListId", ""), 255),
        "ListTitle": _truncate(
            request.POST.get("ListTitle", ""), LIST_TITLE_MAX_LENGTH
        ),
        "Timestamp": _truncate(request.POST.get("Timestamp", ""), 64),
    }

    try:
        queue = get_task_queue()
        result = queue.enqueue(EnqueueRequest(payload=payload))
    except TaskQueueError:
        logger.exception(
            "Fallo critico al encolar.",
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
