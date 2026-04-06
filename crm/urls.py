"""
crm/urls.py — URL routing del módulo CRM.

Contiene:
  - /api/webhooks/twilio/ → Endpoint PÚBLICO para recibir mensajes de Twilio.
  - /api/workers/process-message/ → Endpoint PRIVADO para Cloud Tasks worker.
  - /api/dashboard/leads/ → Dashboard de leads (requiere OIDC).
  - /api/dashboard/leads/<id>/messages/ → Historial de mensajes (GET) y envío (POST).
  - /api/dashboard/leads/<id>/assign/ → Asignar (POST) y reasignar (PATCH).
  - /api/dashboard/leads/<id>/status/ → Cambiar estado (PATCH).
  - /api/dashboard/salespeople/ → Listar vendedores (GET).

Nota: El OIDCStatelessMiddleware tiene un bypass explícito para webhooks y workers.
"""

from django.urls import path

from crm.views.webhook import twilio_webhook_view
from crm.views.worker import process_message_worker_view
from crm.views.dashboard import (
    leads_dashboard_api,
    pending_leads_api,
    tenant_settings_api,
)
from crm.views.dashboard_messages import (
    assign_lead_api,
    change_session_status_api,
    reassign_lead_api,
    salespeople_api,
    send_message_api,
    session_messages_api,
)
from crm.views.metrics import metrics_api
from crm.views.scheduler import (
    scheduler_cleanup_bot_view,
    scheduler_cleanup_sales_view,
    scheduler_cleanup_rate_limits_view,
    scheduler_ttl_warning_view,
)

urlpatterns = [
    # Sprint 3: Endpoint de Ingesta de Webhooks Twilio (público, validado por firma HMAC)
    path("api/webhooks/twilio/", twilio_webhook_view, name="twilio_webhook"),
    # Sprint 3: Worker de Procesamiento (privado, validado por X-Internal-Secret)
    path(
        "api/workers/process-message/",
        process_message_worker_view,
        name="process_message_worker",
    ),
    # Scheduler: Limpieza de sesiones BOT > 4h (sondeo cada 2h)
    path(
        "api/schedulers/cleanup-bot/",
        scheduler_cleanup_bot_view,
        name="scheduler_cleanup_bot",
    ),
    # Scheduler: Limpieza de sesiones CON_VENDEDOR > 7d (sondeo cada 12h)
    path(
        "api/schedulers/cleanup-sales/",
        scheduler_cleanup_sales_view,
        name="scheduler_cleanup_sales",
    ),
    # Scheduler: Limpieza de rate limits antiguos (sondeo cada 1h)
    path(
        "api/schedulers/cleanup-rate-limits/",
        scheduler_cleanup_rate_limits_view,
        name="scheduler_cleanup_rate_limits",
    ),
    # Scheduler: Alerta TTL para sesiones CON_VENDEDOR cerca de expirar (cada 2h)
    path(
        "api/schedulers/ttl-warning/",
        scheduler_ttl_warning_view,
        name="scheduler_ttl_warning",
    ),
    # Sprint 5: Dashboard API (privado, requiere sesión OIDC)
    path("api/dashboard/leads/", leads_dashboard_api, name="dashboard_leads"),
    # Configuración del tenant (routing_mode)
    path(
        "api/dashboard/settings/",
        tenant_settings_api,
        name="tenant_settings",
    ),
    # Cola de leads pendientes de asignación
    path(
        "api/dashboard/leads/pending/",
        pending_leads_api,
        name="pending_leads",
    ),
    # Sprint 6: Detalle de mensajes de una sesión
    path(
        "api/dashboard/leads/<uuid:session_id>/messages/",
        session_messages_api,
        name="session_messages",
    ),
    # Sprint 6: Enviar mensaje como vendedor
    path(
        "api/dashboard/leads/<uuid:session_id>/messages/send/",
        send_message_api,
        name="send_message",
    ),
    # Sprint 6: Asignar lead a vendedor
    path(
        "api/dashboard/leads/<uuid:session_id>/assign/",
        assign_lead_api,
        name="assign_lead",
    ),
    # Sprint 6: Reasignar o desasignar lead
    path(
        "api/dashboard/leads/<uuid:session_id>/reassign/",
        reassign_lead_api,
        name="reassign_lead",
    ),
    # Sprint 6: Cambiar estado de sesión (GANADO/PERDIDO)
    path(
        "api/dashboard/leads/<uuid:session_id>/status/",
        change_session_status_api,
        name="change_session_status",
    ),
    # Sprint 6: Listar vendedores disponibles
    path(
        "api/dashboard/salespeople/",
        salespeople_api,
        name="salespeople",
    ),
    # Métricas de negocio
    path(
        "api/dashboard/metrics/",
        metrics_api,
        name="metrics",
    ),
]
