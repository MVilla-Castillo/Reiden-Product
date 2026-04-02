"""
crm/views/dashboard_messages.py — Vistas delgadas para el dashboard de ventas.
Endpoints: mensajes, asignación, estado, vendedores.

Nota: Django's <uuid:session_id> URL converter ya pasa un objeto UUID,
no un string. No se necesita conversión adicional.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from crm.adapters.dependency_injection import DIContainer
from crm.application.use_cases.send_outbound_message import MessageDeliveryError
from crm.application.use_cases.send_outbound_message import MessageDeliveryError

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def session_messages_api(request: HttpRequest, session_id: UUID) -> JsonResponse:
    if request.tenant is None:
        return JsonResponse({"error": "Tenant no definido."}, status=403)

    use_case = DIContainer.instance().get_session_messages_use_case
    result = use_case.execute(session_id, request.tenant.id)

    if result is None:
        return JsonResponse({"error": "Sesión no encontrada"}, status=404)

    return JsonResponse(
        {
            "session_id": str(result.session_id),
            "lead_id": str(result.lead_id),
            "status": result.status,
            "messages": result.messages,
        },
        status=200,
    )


@csrf_exempt
@require_http_methods(["POST"])
def send_message_api(request: HttpRequest, session_id: UUID) -> JsonResponse:
    if request.tenant is None:
        return JsonResponse({"error": "Tenant no definido."}, status=403)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "JSON inválido"}, status=400)

    message_body = body.get("body", "").strip()
    if not message_body:
        return JsonResponse(
            {"error": "body es requerido y no puede estar vacío"}, status=400
        )

    use_case = DIContainer.instance().send_outbound_message_use_case

    try:
        result = use_case.execute(session_id, request.tenant.id, message_body)
    except PermissionError:
        return JsonResponse(
            {
                "error": "Solo puedes enviar mensajes en sesiones asignadas (CON_VENDEDOR)"
            },
            status=403,
        )
    except MessageDeliveryError:
        return JsonResponse({"error": "Fallo al enviar mensaje por Twilio"}, status=500)

    if result is None:
        return JsonResponse({"error": "Sesión no encontrada"}, status=404)

    return JsonResponse(
        {
            "message_id": result.message_id,
            "direction": result.direction,
            "body": result.body,
            "created_at": result.created_at,
            "provider_message_sid": result.provider_message_sid,
        },
        status=200,
    )


@csrf_exempt
@require_http_methods(["POST"])
def assign_lead_api(request: HttpRequest, session_id: UUID) -> JsonResponse:
    if request.tenant is None:
        return JsonResponse({"error": "Tenant no definido."}, status=403)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "JSON inválido"}, status=400)

    sp_raw = body.get("salesperson_id")
    if sp_raw is not None:
        try:
            sp_id = UUID(sp_raw)
        except ValueError:
            return JsonResponse({"error": "salesperson_id inválido"}, status=400)
    else:
        sp_id = None

    use_case = DIContainer.instance().assign_lead_use_case

    try:
        result = use_case.execute(session_id, request.tenant.id, sp_id)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=404)

    if result is None:
        return JsonResponse({"error": "Sesión no encontrada"}, status=404)

    return JsonResponse(
        {
            "session_id": str(result.session_id),
            "status": result.status,
            "salesperson_id": str(result.salesperson_id)
            if result.salesperson_id
            else None,
            "salesperson_name": result.salesperson_name,
            "assigned_at": result.assigned_at,
        },
        status=200,
    )


@csrf_exempt
@require_http_methods(["PATCH"])
def reassign_lead_api(request: HttpRequest, session_id: UUID) -> JsonResponse:
    if request.tenant is None:
        return JsonResponse({"error": "Tenant no definido."}, status=403)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "JSON inválido"}, status=400)

    sp_raw = body.get("salesperson_id")
    if sp_raw is None and "salesperson_id" not in body:
        return JsonResponse(
            {"error": "salesperson_id es requerido (envía null para desasignar)"},
            status=400,
        )

    if sp_raw is not None:
        try:
            sp_id = UUID(sp_raw)
        except ValueError:
            return JsonResponse({"error": "salesperson_id inválido"}, status=400)
    else:
        sp_id = None

    use_case = DIContainer.instance().assign_lead_use_case

    try:
        result = use_case.execute(session_id, request.tenant.id, sp_id)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=404)

    if result is None:
        return JsonResponse({"error": "Sesión no encontrada"}, status=404)

    return JsonResponse(
        {
            "session_id": str(result.session_id),
            "status": result.status,
            "salesperson_id": str(result.salesperson_id)
            if result.salesperson_id
            else None,
            "salesperson_name": result.salesperson_name,
            "assigned_at": result.assigned_at,
        },
        status=200,
    )


@csrf_exempt
@require_http_methods(["PATCH"])
def change_session_status_api(request: HttpRequest, session_id: UUID) -> JsonResponse:
    if request.tenant is None:
        return JsonResponse({"error": "Tenant no definido."}, status=403)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "JSON inválido"}, status=400)

    new_status = body.get("status", "").strip()
    if not new_status:
        return JsonResponse({"error": "status es requerido"}, status=400)

    use_case = DIContainer.instance().change_session_status_use_case

    try:
        result = use_case.execute(session_id, request.tenant.id, new_status)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    if result is None:
        return JsonResponse({"error": "Sesión no encontrada"}, status=404)

    return JsonResponse(
        {
            "session_id": str(result.session_id),
            "status": result.status,
            "updated_at": result.updated_at,
        },
        status=200,
    )


@require_http_methods(["GET"])
def salespeople_api(request: HttpRequest) -> JsonResponse:
    if request.tenant is None:
        return JsonResponse({"error": "Tenant no definido."}, status=403)

    user_repo = DIContainer.instance().user_repo
    salespeople = user_repo.find_salespeople_by_tenant(request.tenant.id)

    return JsonResponse({"salespeople": salespeople}, status=200)
