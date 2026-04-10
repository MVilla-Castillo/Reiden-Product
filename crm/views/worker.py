"""
crm/views/worker.py — Vista delgada: delega todo al Use Case.

Responsabilidades únicas:
1. Autenticar via X-Internal-Secret
2. Parsear JSON
3. Ejecutar ProcessMessageUseCase
4. Retornar JsonResponse
5. Limpiar tenant_id_var al final
"""

from __future__ import annotations

import json
import logging
from typing import Any

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.log_utils import tenant_id_var, trace_id_var
from crm.adapters.dependency_injection import get_use_case

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def process_message_worker_view(request: HttpRequest) -> JsonResponse:
    internal_secret = request.headers.get("X-Internal-Secret", "")
    if not internal_secret or internal_secret != _get_internal_secret():
        logger.warning(
            "Worker: secreto interno inválido.",
            extra={"component_name": "process_message_worker"},
        )
        return JsonResponse({"error": "Forbidden"}, status=403)

    try:
        payload: dict[str, Any] = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Bad Request: JSON inválido"}, status=400)

    message_sid = payload.get("MessageSid", "")
    if not message_sid:
        return JsonResponse({"error": "Bad Request: MessageSid requerido"}, status=400)

    # Restaurar trace_id y tenant_id desde payload para logging estructurado
    trace_id_token = trace_id_var.set(payload.get("trace_id", "-"))
    tenant_token = tenant_id_var.set("-")
    try:
        result = get_use_case().execute(payload)
        return JsonResponse(
            {"status": result.status, "created": result.message_created},
            status=200,
        )
    except Exception as e:
        logger.exception(
            "Worker: Error no controlado.",
            extra={
                "component_name": "process_message_worker",
                "message_sid": message_sid,
            },
        )
        return JsonResponse({"error": f"internal_error: {repr(e)}"}, status=500)
    finally:
        trace_id_var.reset(trace_id_token)
        tenant_id_var.reset(tenant_token)


def _get_internal_secret() -> str:
    from django.conf import settings

    return getattr(settings, "CLOUD_TASKS_INTERNAL_SECRET", "")
