"""
crm/views/dashboard.py — API GET para Dashboard de Ventas.

Delega al SessionRepository port para obtener sesiones ordenadas por urgency_score.
Incluye rate limiting para proteger contra abuso (60 req/min por tenant).
"""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse

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
        "intent": s.fsm_answers.get("purchase_intent"),
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


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

    session_repo = DIContainer.instance().session_repo
    sessions = session_repo.get_dashboard_sessions(tenant, limit=50)

    data = [_serialize_session(s) for s in sessions]

    return JsonResponse({"leads": data}, status=200)


def pending_leads_api(request: HttpRequest) -> JsonResponse:
    """API para obtener la cola de leads pendientes de asignación."""
    if request.method != "GET":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    tenant = getattr(request, "tenant", None)
    if not tenant:
        return JsonResponse({"error": "Tenant no definido."}, status=403)

    session_repo = DIContainer.instance().session_repo
    sessions = session_repo.get_pending_sessions(tenant, limit=50)

    data = [_serialize_session(s) for s in sessions]

    return JsonResponse({"pending_leads": data}, status=200)
