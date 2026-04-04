"""
crm/views/metrics.py — Endpoint de Métricas para Dashboard Gerencial.

Expone datos agregados para análisis de embudo, distribución FSM,
métricas de tiempo y performance por vendedor.
"""

from datetime import date

from django.http import HttpRequest, JsonResponse

from core.date_utils import get_date_range_from_filter, parse_date_param
from crm.adapters.dependency_injection import DIContainer


def metrics_api(request: HttpRequest) -> JsonResponse:
    """Retorna métricas agregadas para el dashboard gerencial."""
    if request.method != "GET":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    tenant = getattr(request, "tenant", None)
    if not tenant:
        return JsonResponse({"error": "Tenant no definido."}, status=403)

    date_filter = request.GET.get("date_filter")
    date_from_param = request.GET.get("date_from")
    date_to_param = request.GET.get("date_to")

    if date_filter in ("today", "week", "month", "year", "all"):
        date_range = get_date_range_from_filter(date_filter)
        if date_range:
            date_from, date_to = date_range
        elif date_filter == "all":
            date_from, date_to = None, None
        else:
            date_from, date_to = date.today(), date.today()
    elif date_from_param or date_to_param:
        date_from = parse_date_param(date_from_param, date.today())
        date_to = parse_date_param(date_to_param, date.today())
    else:
        date_from, date_to = date.today(), date.today()

    if not date_from or not date_to:
        return JsonResponse(
            {"error": "Parámetros date_from y date_to requeridos (ISO 8601)."},
            status=400,
        )

    if date_from > date_to:
        return JsonResponse(
            {"error": "date_from no puede ser mayor a date_to."},
            status=400,
        )

    session_repo = DIContainer.instance().session_repo

    funnel = session_repo.get_funnel_metrics(tenant.id, date_from, date_to)
    fsm_distribution = session_repo.get_fsm_distribution(tenant.id, date_from, date_to)
    urgency_distribution = session_repo.get_urgency_distribution(
        tenant.id, date_from, date_to
    )
    time_metrics = session_repo.get_time_metrics(tenant.id, date_from, date_to)
    salesperson_performance = session_repo.get_salesperson_performance(
        tenant.id, date_from, date_to
    )

    return JsonResponse(
        {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "date_filter": date_filter,
            "funnel": funnel,
            "fsm_distribution": fsm_distribution,
            "urgency_distribution": urgency_distribution,
            "time_metrics": time_metrics,
            "salesperson_performance": salesperson_performance,
        },
        status=200,
    )
