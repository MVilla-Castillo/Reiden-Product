"""
crm/views/sse.py — Endpoints Server-Sent Events para el dashboard.

Dos streams:
  GET /api/sse/dashboard/   → snapshot inicial + eventos: pending_leads, settings, heartbeat
  GET /api/sse/messages/<session_id>/ → eventos: message, status_change, heartbeat

Nota de autenticación: EventSource del browser no puede enviar headers
Authorization. Para activar en el frontend, pasar el token como query param
?token=<jwt> y actualizar OIDCStatelessMiddleware para leerlo de request.GET.
"""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

from asgiref.sync import sync_to_async
from django.http import HttpRequest, JsonResponse, StreamingHttpResponse

from crm.adapters.sse.broadcaster import broadcaster, heartbeat_frame

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 25  # segundos


async def dashboard_sse_view(request: HttpRequest) -> StreamingHttpResponse:
    """
    SSE stream para el dashboard: emite snapshot al conectar,
    luego deltas a medida que llegan eventos del broadcaster.
    """
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        return JsonResponse({"error": "Tenant no definido."}, status=403)

    tenant_id = str(tenant.id)
    queue = broadcaster.subscribe_dashboard(tenant_id)
    logger.debug("SSE dashboard: nueva conexión (tenant=%s)", tenant_id)

    async def event_stream():
        try:
            snapshot = await _build_dashboard_snapshot(tenant)
            yield snapshot

            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)
                    yield msg
                except asyncio.TimeoutError:
                    yield heartbeat_frame()
        except GeneratorExit:
            pass
        finally:
            broadcaster.unsubscribe_dashboard(tenant_id, queue)
            logger.debug("SSE dashboard: conexión cerrada (tenant=%s)", tenant_id)

    response = StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


async def messages_sse_view(
    request: HttpRequest, session_id: UUID
) -> StreamingHttpResponse:
    """
    SSE stream para mensajes de una sesión.
    Emite eventos 'message' y 'status_change' en tiempo real.
    """
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        return JsonResponse({"error": "Tenant no definido."}, status=403)

    tenant_id = str(tenant.id)
    session_id_str = str(session_id)
    queue = broadcaster.subscribe_messages(tenant_id, session_id_str)
    logger.debug(
        "SSE messages: nueva conexión (tenant=%s, session=%s)",
        tenant_id,
        session_id_str,
    )

    async def event_stream():
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)
                    yield msg
                except asyncio.TimeoutError:
                    yield heartbeat_frame()
        except GeneratorExit:
            pass
        finally:
            broadcaster.unsubscribe_messages(tenant_id, session_id_str, queue)
            logger.debug(
                "SSE messages: conexión cerrada (tenant=%s, session=%s)",
                tenant_id,
                session_id_str,
            )

    response = StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


async def _build_dashboard_snapshot(tenant) -> str:
    """
    Consulta DB (vía sync_to_async) y arma el frame SSE 'snapshot'
    con pending_leads, salespeople y settings en una sola respuesta.
    """
    from datetime import datetime, timezone

    from crm.adapters.dependency_injection import DIContainer
    from crm.views.dashboard import _serialize_session

    container = DIContainer.instance()
    tenant_id = tenant.id

    get_pending = sync_to_async(
        lambda: container.session_repo.get_pending_sessions(tenant_id, limit=50)
    )
    get_salespeople = sync_to_async(
        lambda: container.user_repo.find_salespeople_by_tenant(tenant_id)
    )
    get_settings = sync_to_async(
        lambda: container.tenant_repo.find_by_id(tenant_id)
    )

    pending, salespeople, settings_data = await asyncio.gather(
        get_pending(), get_salespeople(), get_settings()
    )

    payload = {
        "pending_leads": [_serialize_session(s) for s in pending],
        "salespeople": salespeople,
        "settings": {
            "routing_mode": settings_data.get("routing_mode") if settings_data else None,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    data = json.dumps(payload, separators=(",", ":"), default=str)
    return f"event: snapshot\ndata: {data}\n\n"
