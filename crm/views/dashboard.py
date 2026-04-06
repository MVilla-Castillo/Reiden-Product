"""
crm/views/dashboard.py — API GET para Dashboard de Ventas.

Delega al SessionRepository port para obtener sesiones ordenadas por urgency_score.
Incluye rate limiting para proteger contra abuso (60 req/min por tenant).
"""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse

from core.date_utils import get_date_range_from_filter, parse_date_param
from core.rate_limit import check_rate_limit
from crm.adapters.dependency_injection import DIContainer
from crm.domain.entities import SessionEntity


def _serialize_session(s: SessionEntity) -> dict:
    return {
        "session_id": str(s.id),
        "lead_phone_hash": str(s.lead_id),
        "status": s.status,
        "urgency_score": s.urgency_score,
        "fsm_step": s.fsm_answers.get("current_step", "UNKNOWN"),
        "vehicle_type": s.fsm_answers.get("vehicle_type"),
        "payment_method": s.fsm_answers.get("payment_method"),
        "budget_range": s.fsm_answers.get("budget_range"),
        "purchase_intent": s.fsm_answers.get("purchase_intent"),
        "salesperson_id": str(s.salesperson_id) if s.salesperson_id else None,
        "assigned_at": s.assigned_at.isoformat() if s.assigned_at else None,
        "closed_at": s.closed_at.isoformat() if s.closed_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _build_filters(request: HttpRequest) -> dict:
    """Construye diccionario de filtros desde query params."""
    from datetime import date

    filters = {}

    date_filter = request.GET.get("date_filter")
    date_from_param = request.GET.get("date_from")
    date_to_param = request.GET.get("date_to")

    if date_filter in ("today", "week", "month", "year", "all"):
        date_range = get_date_range_from_filter(date_filter)
        if date_range:
            filters["date_from"], filters["date_to"] = date_range
    elif date_from_param or date_to_param:
        filters["date_from"] = parse_date_param(date_from_param)
        filters["date_to"] = parse_date_param(date_to_param, date.today())

    status = request.GET.get("status")
    if status:
        filters["status"] = status

    vehicle_type = request.GET.get("vehicle_type")
    if vehicle_type:
        filters["vehicle_type"] = vehicle_type

    payment_method = request.GET.get("payment_method")
    if payment_method:
        filters["payment_method"] = payment_method

    budget_range = request.GET.get("budget_range")
    if budget_range:
        filters["budget_range"] = budget_range

    purchase_intent = request.GET.get("purchase_intent")
    if purchase_intent:
        filters["purchase_intent"] = purchase_intent

    salesperson_id = request.GET.get("salesperson_id")
    if salesperson_id:
        filters["salesperson_id"] = salesperson_id

    min_urgency = request.GET.get("min_urgency")
    if min_urgency:
        try:
            filters["min_urgency"] = int(min_urgency)
        except ValueError:
            pass

    max_urgency = request.GET.get("max_urgency")
    if max_urgency:
        try:
            filters["max_urgency"] = int(max_urgency)
        except ValueError:
            pass

    return filters


def leads_dashboard_api(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    tenant = getattr(request, "tenant", None)
    if not tenant:
        return JsonResponse({"error": "Tenant no definido."}, status=403)

    rate_key = f"dashboard:{tenant.id}"
    if not check_rate_limit(rate_key, max_requests=60, window=60):
        return JsonResponse(
            {"error": "Demasiadas peticiones. Intenta en 1 minuto."},
            status=429,
        )

    limit_raw = request.GET.get("limit", "50")
    try:
        limit = min(int(limit_raw), 100)
    except ValueError:
        limit = 50

    filters = _build_filters(request)

    session_repo = DIContainer.instance().session_repo
    sessions = session_repo.get_dashboard_sessions(
        tenant.id, limit=limit, filters=filters
    )

    data = [_serialize_session(s) for s in sessions]

    return JsonResponse({"leads": data, "count": len(data)}, status=200)


def pending_leads_api(request: HttpRequest) -> JsonResponse:
    """API para obtener la cola de leads pendientes de asignación."""
    if request.method != "GET":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    tenant = getattr(request, "tenant", None)
    if not tenant:
        return JsonResponse({"error": "Tenant no definido."}, status=403)

    session_repo = DIContainer.instance().session_repo
    sessions = session_repo.get_pending_sessions(tenant.id, limit=50)

    data = [_serialize_session(s) for s in sessions]

    return JsonResponse({"pending_leads": data}, status=200)


def tenant_settings_api(request: HttpRequest) -> JsonResponse:
    """
    API para obtener y actualizar configuración del tenant.
    GET: Retorna configuración actual (incluyendo routing_mode).
    PATCH: Actualiza el modo de asignación (MANUAL/AUTO).
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return JsonResponse({"error": "Tenant no definido."}, status=403)

    tenant_repo = DIContainer.instance().tenant_repo

    if request.method == "GET":
        tenant_data = tenant_repo.find_by_id(tenant.id)
        if not tenant_data:
            return JsonResponse({"error": "Tenant no encontrado."}, status=404)

        return JsonResponse(
            {
                "tenant_id": str(tenant_data["id"]),
                "nombre_legal": tenant_data["nombre_legal"],
                "routing_mode": tenant_data["routing_mode"],
                "is_verified": tenant_data["is_verified"],
            },
            status=200,
        )

    if request.method == "PATCH":
        from crm.models import AppUser

        user = getattr(request, "user", None)
        if not user:
            return JsonResponse({"error": "Usuario no autenticado."}, status=401)

        if user.role != AppUser.Role.MANAGER:
            return JsonResponse(
                {"error": "Solo administradores pueden cambiar la configuración."},
                status=403,
            )

        import json

        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON inválido."}, status=400)

        new_routing_mode = body.get("routing_mode")
        if new_routing_mode is None:
            return JsonResponse(
                {"error": "routing_mode es requerido."},
                status=400,
            )

        if new_routing_mode not in ("MANUAL", "AUTO"):
            return JsonResponse(
                {"error": "routing_mode debe ser MANUAL o AUTO."},
                status=400,
            )

        success = tenant_repo.update_routing_mode(tenant.id, new_routing_mode)
        if not success:
            return JsonResponse(
                {"error": "Error al actualizar routing_mode."},
                status=500,
            )

        return JsonResponse(
            {
                "message": f"Modo de asignación cambiado a {new_routing_mode}",
                "routing_mode": new_routing_mode,
            },
            status=200,
        )

    return JsonResponse({"error": "Method Not Allowed"}, status=405)
