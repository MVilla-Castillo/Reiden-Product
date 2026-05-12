"""
crm/views/dashboard_messages.py — Vistas delgadas para el dashboard de ventas.
Endpoints: mensajes, asignación, estado, vendedores.

Nota: Django's <uuid:session_id> URL converter ya pasa un objeto UUID,
no un string. No se necesita conversión adicional.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from core.rate_limit import check_rate_limit
from crm.adapters.dependency_injection import DIContainer
from crm.adapters.sse.broadcaster import broadcaster
from crm.application.use_cases.send_outbound_message import MessageDeliveryError
from crm.domain.exceptions import (
    DomainNotFoundError,
    DomainValidationError,
)
from crm.models import AppUser, Lead, LeadNameHistory
from crm.views._decorators import require_tenant
from crm.views._validation import (
    optional_str_field,
    parse_json_body,
    require_str_field,
)

logger = logging.getLogger(__name__)

_CLOSED_STATUSES = {"GANADO", "PERDIDO", "ABANDONO_BOT"}


@require_http_methods(["GET"])
@require_tenant
def session_messages_api(request: HttpRequest, session_id: UUID) -> JsonResponse:
    limit_raw = request.GET.get("limit")
    if limit_raw is None:
        return JsonResponse(
            {"error": "El parámetro 'limit' es requerido"},
            status=400,
        )

    try:
        limit = int(limit_raw)
    except (ValueError, TypeError):
        return JsonResponse(
            {"error": "El parámetro 'limit' debe ser un entero válido"},
            status=400,
        )

    if limit <= 0 or limit > 100:
        return JsonResponse(
            {"error": "El parámetro 'limit' debe estar entre 1 y 100"},
            status=400,
        )

    offset_raw = request.GET.get("offset")
    if offset_raw is None:
        offset = 0
    else:
        try:
            offset = int(offset_raw)
        except (ValueError, TypeError):
            return JsonResponse(
                {"error": "El parámetro 'offset' debe ser un entero válido"},
                status=400,
            )

    use_case = DIContainer.instance().get_session_messages_use_case
    result = use_case.execute(session_id, request.tenant.id, limit=limit, offset=offset)

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
@require_tenant
def send_message_api(request: HttpRequest, session_id: UUID) -> JsonResponse:
    rate_key = f"write:send:{request.user.id}"
    if not check_rate_limit(rate_key, max_requests=20, window=60):
        return JsonResponse(
            {"error": "Demasiadas peticiones. Intenta en 1 minuto."}, status=429
        )

    _session = DIContainer.instance().session_repo.find_by_id(
        session_id, request.tenant.id
    )
    if _session is None:
        return JsonResponse({"error": "Sesión no encontrada"}, status=404)

    if (
        request.user.role != AppUser.Role.MANAGER
        and _session.salesperson_id != request.user.id
    ):
        return JsonResponse(
            {"error": "Solo el vendedor asignado o el manager puede enviar mensajes."},
            status=403,
        )

    body, err = parse_json_body(request)
    if err is not None:
        return err
    message_body, err = require_str_field(body, "body", max_length=4096)
    if err is not None:
        return err

    use_case = DIContainer.instance().send_outbound_message_use_case

    with transaction.atomic():
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
            return JsonResponse(
                {"error": "Fallo al enviar mensaje por Twilio"}, status=500
            )

        if result is None:
            return JsonResponse({"error": "Sesión no encontrada"}, status=404)

        tenant_id_str = str(request.tenant.id)
        session_id_str = str(session_id)
        payload = {
            "message_id": result.message_id,
            "direction": result.direction,
            "body": result.body,
            "session_id": session_id_str,
            "created_at": result.created_at,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        transaction.on_commit(
            lambda: broadcaster.publish_message(
                tenant_id_str, session_id_str, "message", payload
            )
        )

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
@require_tenant
def assign_lead_api(request: HttpRequest, session_id: UUID) -> JsonResponse:
    rate_key = f"write:action:{request.user.id}"
    if not check_rate_limit(rate_key, max_requests=30, window=60):
        return JsonResponse(
            {"error": "Demasiadas peticiones. Intenta en 1 minuto."}, status=429
        )

    if request.user.role != AppUser.Role.MANAGER:
        return JsonResponse(
            {"error": "Solo el manager puede asignar leads manualmente."},
            status=403,
        )

    body, err = parse_json_body(request)
    if err is not None:
        return err

    sp_raw = body.get("salesperson_id")
    if sp_raw is None:
        sp_id = None
    elif sp_raw == "AUTO":
        sp_id = "AUTO"
    elif isinstance(sp_raw, str):
        try:
            sp_id = UUID(sp_raw)
        except ValueError:
            return JsonResponse({"error": "salesperson_id inválido"}, status=400)
    else:
        return JsonResponse({"error": "salesperson_id inválido"}, status=400)

    use_case = DIContainer.instance().assign_lead_use_case

    with transaction.atomic():
        try:
            result = use_case.execute(session_id, request.tenant.id, sp_id)
        except DomainNotFoundError as e:
            return JsonResponse({"error": str(e)}, status=404)
        except DomainValidationError as e:
            return JsonResponse({"error": str(e)}, status=400)

        if result is None:
            return JsonResponse({"error": "Sesión no encontrada"}, status=404)

        tenant_id_str = str(request.tenant.id)
        payload = {
            "session_id": str(result.session_id),
            "status": result.status,
            "salesperson_id": str(result.salesperson_id)
            if result.salesperson_id
            else None,
            "action": "assigned",
            "assigned_delta": 1,
            "pending_delta": -1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        transaction.on_commit(
            lambda: broadcaster.publish_dashboard(
                tenant_id_str, "pending_leads", payload
            )
        )

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
@require_tenant
def reassign_lead_api(request: HttpRequest, session_id: UUID) -> JsonResponse:
    rate_key = f"write:action:{request.user.id}"
    if not check_rate_limit(rate_key, max_requests=30, window=60):
        return JsonResponse(
            {"error": "Demasiadas peticiones. Intenta en 1 minuto."}, status=429
        )

    if request.user.role != AppUser.Role.MANAGER:
        return JsonResponse(
            {"error": "Solo el manager puede reasignar leads."},
            status=403,
        )

    body, err = parse_json_body(request)
    if err is not None:
        return err
    assert body is not None

    if "salesperson_id" not in body:
        return JsonResponse(
            {"error": "salesperson_id es requerido (envía null para desasignar)"},
            status=400,
        )

    sp_raw = body["salesperson_id"]
    if sp_raw is None:
        sp_id = None
    elif isinstance(sp_raw, str):
        try:
            sp_id = UUID(sp_raw)
        except ValueError:
            return JsonResponse({"error": "salesperson_id inválido"}, status=400)
    else:
        return JsonResponse({"error": "salesperson_id inválido"}, status=400)

    use_case = DIContainer.instance().assign_lead_use_case

    with transaction.atomic():
        try:
            result = use_case.execute(session_id, request.tenant.id, sp_id)
        except DomainNotFoundError as e:
            return JsonResponse({"error": str(e)}, status=404)
        except DomainValidationError as e:
            return JsonResponse({"error": str(e)}, status=400)

        if result is None:
            return JsonResponse({"error": "Sesión no encontrada"}, status=404)

        tenant_id_str = str(request.tenant.id)
        payload = {
            "session_id": str(result.session_id),
            "status": result.status,
            "salesperson_id": str(result.salesperson_id)
            if result.salesperson_id
            else None,
            "action": "reassigned",
            "assigned_delta": 1,
            "pending_delta": -1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        transaction.on_commit(
            lambda: broadcaster.publish_dashboard(
                tenant_id_str, "pending_leads", payload
            )
        )

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
@require_tenant
def change_session_status_api(request: HttpRequest, session_id: UUID) -> JsonResponse:
    rate_key = f"write:action:{request.user.id}"
    if not check_rate_limit(rate_key, max_requests=30, window=60):
        return JsonResponse(
            {"error": "Demasiadas peticiones. Intenta en 1 minuto."}, status=429
        )

    _session = DIContainer.instance().session_repo.find_by_id(
        session_id, request.tenant.id
    )
    if _session is None:
        return JsonResponse({"error": "Sesión no encontrada"}, status=404)

    if (
        _session.status in _CLOSED_STATUSES
        and request.user.role != AppUser.Role.MANAGER
    ):
        return JsonResponse(
            {"error": "Solo el manager puede modificar una sesión ya cerrada."},
            status=403,
        )

    body, err = parse_json_body(request)
    if err is not None:
        return err
    new_status, err = require_str_field(body, "status")
    if err is not None:
        return err
    lost_reason, err = optional_str_field(body, "lost_reason", max_length=255)
    if err is not None:
        return err
    if new_status == "PERDIDO" and not lost_reason:
        return JsonResponse(
            {"error": "lost_reason es obligatorio para estado PERDIDO"}, status=400
        )

    use_case = DIContainer.instance().change_session_status_use_case

    with transaction.atomic():
        try:
            result = use_case.execute(
                session_id, request.tenant.id, new_status, lost_reason=lost_reason
            )
        except DomainValidationError as e:
            return JsonResponse({"error": str(e)}, status=400)

        if result is None:
            return JsonResponse({"error": "Sesión no encontrada"}, status=404)

        ts = datetime.now(timezone.utc).isoformat()
        status_delta: dict = {}
        if result.status == "GANADO":
            status_delta["won_delta"] = 1
        elif result.status == "PERDIDO":
            status_delta["lost_delta"] = 1

        tenant_id_str = str(request.tenant.id)
        session_id_str = str(session_id)
        dashboard_payload = {
            "session_id": str(result.session_id),
            "status": result.status,
            "action": "status_changed",
            **status_delta,
            "timestamp": ts,
        }
        message_payload = {
            "session_id": str(result.session_id),
            "status": result.status,
            "updated_at": result.updated_at,
            "timestamp": ts,
        }
        transaction.on_commit(
            lambda: broadcaster.publish_dashboard(
                tenant_id_str, "pending_leads", dashboard_payload
            )
        )
        transaction.on_commit(
            lambda: broadcaster.publish_message(
                tenant_id_str, session_id_str, "status_change", message_payload
            )
        )

    return JsonResponse(
        {
            "session_id": str(result.session_id),
            "status": result.status,
            "updated_at": result.updated_at,
        },
        status=200,
    )


@require_http_methods(["GET"])
@require_tenant
def salespeople_api(request: HttpRequest) -> JsonResponse:
    user_repo = DIContainer.instance().user_repo
    salespeople = user_repo.find_salespeople_by_tenant(request.tenant.id)

    return JsonResponse({"salespeople": salespeople}, status=200)


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
@require_tenant
def update_lead_api(request: HttpRequest, session_id: UUID) -> JsonResponse:
    if request.method == "PATCH":
        rate_key = f"write:action:{request.user.id}"
        if not check_rate_limit(rate_key, max_requests=30, window=60):
            return JsonResponse(
                {"error": "Demasiadas peticiones. Intenta en 1 minuto."}, status=429
            )

    session_repo = DIContainer.instance().session_repo
    session = session_repo.find_by_id(session_id, request.tenant.id)
    if session is None:
        return JsonResponse({"error": "Sesión no encontrada"}, status=404)

    lead_id = session.lead_id

    lead = Lead.objects.filter(
        id=lead_id, tenant_id=request.tenant.id, is_deleted=False
    ).first()
    if lead is None:
        return JsonResponse({"error": "Lead no encontrado"}, status=404)

    if request.method == "PATCH":
        body, err = parse_json_body(request)
        if err is not None:
            return err
        new_name, err = optional_str_field(body, "lead_profile_name", max_length=255)
        if err is not None:
            return err

        if new_name is not None and new_name != lead.profile_name:
            old_name = lead.profile_name
            with transaction.atomic():
                LeadNameHistory.objects.create(
                    lead=lead,
                    old_name=old_name,
                    new_name=new_name,
                    changed_by=request.user if request.user.is_authenticated else None,
                )
                lead.profile_name = new_name
                lead.save(update_fields=["profile_name"])

                tenant_id_str = str(request.tenant.id)
                session_id_str = str(session_id)
                lead_id_str = str(lead.id)
                new_profile = lead.profile_name
                payload = {
                    "session_id": session_id_str,
                    "lead_id": lead_id_str,
                    "lead_profile_name": new_profile,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                transaction.on_commit(
                    lambda: broadcaster.publish_dashboard(
                        tenant_id_str, "lead_updated", payload
                    )
                )

    name_history = list(
        LeadNameHistory.objects.filter(lead=lead)
        .select_related("changed_by")
        .order_by("-changed_at")
        .values("old_name", "new_name", "changed_by_id", "changed_at")
    )

    return JsonResponse(
        {
            "lead_profile_name": lead.profile_name,
            "name_history": [
                {
                    "old_name": h["old_name"],
                    "new_name": h["new_name"],
                    "changed_by": str(h["changed_by_id"])
                    if h["changed_by_id"]
                    else None,
                    "changed_at": h["changed_at"].isoformat()
                    if h["changed_at"]
                    else None,
                }
                for h in name_history
            ],
        },
        status=200,
    )
