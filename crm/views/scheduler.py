"""
crm/views/scheduler.py — Endpoints para Cloud Scheduler.

Reglas de limpieza de pipeline:
- BOT: 4h sin interacción → ABANDONO_BOT (sondeo cada 2h)
- PENDING_ASSIGNMENT: nunca se elimina
- CON_VENDEDOR: 7 días sin interacción → PERDIDO (sondeo cada 12h)

Autenticación: X-Internal-Secret (mismo secreto que el worker).
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from crm.adapters.dependency_injection import DIContainer
from crm.domain.ports import AuditEntry

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def scheduler_cleanup_bot_view(request: HttpRequest) -> JsonResponse:
    """
    Limpieza de sesiones BOT inactivas.
    Ejecutado por Cloud Scheduler cada 2 horas.

    - BOT > 4h sin actividad → ABANDONO_BOT
    - PENDING_ASSIGNMENT: se omite (nunca expira)
    """
    if not _authenticate(request):
        return JsonResponse({"error": "Forbidden"}, status=403)

    session_repo = DIContainer.instance().session_repo
    audit_logger = DIContainer.instance().audit_logger

    cleaned = 0
    tenants = _get_verified_tenants()

    for tenant in tenants:
        sessions = session_repo.get_expired_sessions(
            tenant.id, hours=4, status_filter="BOT"
        )
        for session_data in sessions:
            session_id = session_data["id"]
            old_status = session_data["status"]
            new_status = "ABANDONO_BOT"

            with transaction.atomic():
                session_repo.change_status(session_id, tenant.id, new_status)

                audit_logger.record(
                    AuditEntry(
                        session_id=session_id,
                        tenant_id=tenant.id,
                        action="SCHEDULER_CLEANUP_BOT",
                        old_value={"status": old_status},
                        new_value={
                            "status": new_status,
                            "lost_reason": "Inactividad 4h en BOT",
                        },
                        actor_id=None,
                    )
                )
            cleaned += 1

    logger.info(
        "Scheduler: Limpieza de BOT completada.",
        extra={
            "component_name": "scheduler_cleanup_bot",
            "cleaned_sessions": cleaned,
        },
    )

    return JsonResponse({"status": "ok", "cleaned": cleaned}, status=200)


@csrf_exempt
@require_POST
def scheduler_cleanup_sales_view(request: HttpRequest) -> JsonResponse:
    """
    Limpieza de sesiones CON_VENDEDOR inactivas.
    Ejecutado por Cloud Scheduler cada 12 horas.

    - CON_VENDEDOR > 7 días sin actividad → PERDIDO
    """
    if not _authenticate(request):
        return JsonResponse({"error": "Forbidden"}, status=403)

    session_repo = DIContainer.instance().session_repo
    audit_logger = DIContainer.instance().audit_logger

    cleaned = 0
    tenants = _get_verified_tenants()

    for tenant in tenants:
        sessions = session_repo.get_expired_sessions(
            tenant.id, hours=168, status_filter="CON_VENDEDOR"
        )
        for session_data in sessions:
            session_id = session_data["id"]
            old_status = session_data["status"]
            new_status = "PERDIDO"

            with transaction.atomic():
                session_repo.change_status(session_id, tenant.id, new_status)

                audit_logger.record(
                    AuditEntry(
                        session_id=session_id,
                        tenant_id=tenant.id,
                        action="SCHEDULER_CLEANUP_SALES",
                        old_value={"status": old_status},
                        new_value={
                            "status": new_status,
                            "lost_reason": "Inactividad 7 dias con vendedor",
                        },
                        actor_id=None,
                    )
                )
            cleaned += 1

    logger.info(
        "Scheduler: Limpieza de CON_VENDEDOR completada.",
        extra={
            "component_name": "scheduler_cleanup_sales",
            "cleaned_sessions": cleaned,
        },
    )

    return JsonResponse({"status": "ok", "cleaned": cleaned}, status=200)


@csrf_exempt
@require_POST
def scheduler_ttl_warning_view(request: HttpRequest) -> JsonResponse:
    """
    Notificar vendedor cuando quedan ~2h para expirar TTL de 7 días.
    Ejecutado por Cloud Scheduler cada 2 horas.

    Identifica sesiones CON_VENDEDOR donde:
    - last_client_message_at está entre ~6d 22h y 7d atrás
    - El vendedor aún no ha respondido
    """
    if not _authenticate(request):
        return JsonResponse({"error": "Forbidden"}, status=403)

    session_repo = DIContainer.instance().session_repo
    push_adapter = DIContainer.instance().push_adapter

    warnings_sent = 0
    sessions = session_repo.get_sessions_near_ttl_expiry(hours=166)

    for session_data in sessions:
        session_id = session_data["id"]
        salesperson_id = session_data.get("salesperson_id")
        tenant_id = session_data["tenant_id"]
        lead_id = session_data.get("lead_id")

        if not salesperson_id:
            continue

        try:
            push_adapter.send_ttl_warning(
                user_id=salesperson_id,
                session_id=session_id,
                tenant_id=tenant_id,
                lead_id=lead_id,
                hours_remaining=24,
            )
            warnings_sent += 1
        except Exception:
            logger.exception(
                "Scheduler: Fallo al enviar alerta TTL.",
                extra={
                    "component_name": "scheduler_ttl_warning",
                    "session_id": str(session_id),
                    "salesperson_id": str(salesperson_id),
                },
            )

    logger.info(
        "Scheduler: Alertas TTL enviadas.",
        extra={
            "component_name": "scheduler_ttl_warning",
            "warnings_sent": warnings_sent,
        },
    )

    return JsonResponse({"status": "ok", "warnings_sent": warnings_sent}, status=200)


@csrf_exempt
@require_POST
def scheduler_cleanup_rate_limits_view(request: HttpRequest) -> JsonResponse:
    """
    Limpia registros de rate limit antiguos para evitar crecimiento infinito de la tabla.
    Ejecutado por Cloud Scheduler cada 1 hora.
    """
    if not _authenticate(request):
        return JsonResponse({"error": "Forbidden"}, status=403)

    from crm.services.rate_limiter import cleanup_old_rate_limits

    deleted = cleanup_old_rate_limits(hours=1)

    logger.info(
        "Scheduler: Limpieza de rate limits completada.",
        extra={
            "component_name": "scheduler_cleanup_rate_limits",
            "deleted_records": deleted,
        },
    )

    return JsonResponse({"status": "ok", "deleted": deleted}, status=200)


def _get_verified_tenants():
    """Obtiene tenants verificados respetando multi-tenancy."""
    from crm.models import Tenant

    return Tenant.objects.filter(is_verified=True)


def _authenticate(request: HttpRequest) -> bool:
    internal_secret = request.headers.get("X-Internal-Secret", "")
    from django.conf import settings

    expected = getattr(settings, "CLOUD_TASKS_INTERNAL_SECRET", "")
    return bool(internal_secret and internal_secret == expected)
