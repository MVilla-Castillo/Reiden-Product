"""
crm/views/sse.py — Endpoints Server-Sent Events para el dashboard.

Dos streams:
  GET /api/sse/dashboard/   → snapshot inicial + eventos: pending_leads, settings, heartbeat
  GET /api/sse/messages/<session_id>/ → eventos: message, status_change, heartbeat

Diseño 100% síncrono — compatible con WSGI (runserver local) y ASGI (uvicorn Docker).
  - Views y generadores son funciones síncronas normales (def, no async def).
  - StreamingHttpResponse recibe un generador síncrono: no hay conflicto con WSGI.
  - threading.Queue.get(block=True, timeout=N) bloquea el thread WSGI del request
    durante N segundos a lo sumo. Cada conexión SSE ocupa un thread — comportamiento
    esperado y equivalente a lo que hacía antes el polling, pero sin repetir requests.
  - En uvicorn (Docker), las sync views se despachan al thread pool de Django/asgiref,
    mismo comportamiento.

Error que se corrige:
  "StreamingHttpResponse must consume asynchronous iterators in order to serve them
   synchronously. Use a synchronous iterator instead."
"""

from __future__ import annotations

import json
import logging
import queue as _queue
from datetime import datetime, timezone
from uuid import UUID

from django.http import HttpRequest, JsonResponse, StreamingHttpResponse

from crm.adapters.sse.broadcaster import broadcaster, heartbeat_frame
from crm.views._decorators import require_tenant

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 25  # segundos — tiempo máximo entre heartbeats


@require_tenant
def dashboard_sse_view(request: HttpRequest) -> StreamingHttpResponse:
    """
    SSE stream para el dashboard.
    Emite snapshot al conectar, luego deltas a medida que el broadcaster
    publica eventos (pending_leads, settings).

    Autorización por rol:
    - MANAGER/ADMIN: reciben snapshot completo y todos los eventos delta.
    - SALESPERSON: snapshot filtrado a sus propias sesiones; solo reciben
      eventos delta de pending_leads donde salesperson_id == su propio id.
    """
    from crm.models import AppUser

    tenant = request.tenant
    user = getattr(request, "user", None)
    if user is None:
        return JsonResponse({"error": "Usuario no definido."}, status=403)

    is_manager = user.role in (AppUser.Role.MANAGER, AppUser.Role.ADMIN)
    user_id_str = str(user.id)
    tenant_id = str(tenant.id)
    q = broadcaster.subscribe_dashboard(tenant_id)
    logger.debug(
        "SSE dashboard: nueva conexión (tenant=%s, user=%s)", tenant_id, user_id_str
    )

    def event_stream():
        try:
            yield _build_dashboard_snapshot(tenant, user)

            while True:
                try:
                    # Bloquea el thread hasta HEARTBEAT_INTERVAL seg o hasta recibir un evento.
                    # threading.Queue.get() es thread-safe: cualquier thread WSGI puede
                    # publicar con put_nowait() y este get() lo recibe inmediatamente.
                    msg = q.get(block=True, timeout=HEARTBEAT_INTERVAL)
                    if is_manager or _should_forward_to_salesperson(msg, user_id_str):
                        yield msg
                except _queue.Empty:
                    # Timeout sin mensajes → envía comentario SSE para mantener la conexión
                    yield heartbeat_frame()
        except GeneratorExit:
            pass
        finally:
            broadcaster.unsubscribe_dashboard(tenant_id, q)
            logger.debug("SSE dashboard: conexión cerrada (tenant=%s)", tenant_id)

    response = StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@require_tenant
def messages_sse_view(request: HttpRequest, session_id: UUID) -> StreamingHttpResponse:
    """
    SSE stream para mensajes de una sesión.
    Emite eventos 'message' y 'status_change' en tiempo real.

    Autorización: MANAGER/ADMIN acceden a cualquier sesión del tenant.
    SALESPERSON solo puede suscribirse a la sesión que tiene asignada.
    """
    from crm.adapters.dependency_injection import DIContainer
    from crm.models import AppUser

    tenant = request.tenant
    user = getattr(request, "user", None)
    if user is None:
        return JsonResponse({"error": "Usuario no definido."}, status=403)

    is_manager = user.role in (AppUser.Role.MANAGER, AppUser.Role.ADMIN)
    if not is_manager:
        container = DIContainer.instance()
        session = container.session_repo.find_by_id(session_id, tenant.id)
        if session is None:
            return JsonResponse({"error": "Sesión no encontrada."}, status=404)
        if session.salesperson_id != user.id:
            return JsonResponse(
                {
                    "error": "Solo el vendedor asignado o un manager puede ver estos mensajes."
                },
                status=403,
            )

    tenant_id = str(tenant.id)
    session_id_str = str(session_id)
    q = broadcaster.subscribe_messages(tenant_id, session_id_str)
    logger.debug(
        "SSE messages: nueva conexión (tenant=%s, session=%s)",
        tenant_id,
        session_id_str,
    )

    def event_stream():
        try:
            while True:
                try:
                    msg = q.get(block=True, timeout=HEARTBEAT_INTERVAL)
                    yield msg
                except _queue.Empty:
                    yield heartbeat_frame()
        except GeneratorExit:
            pass
        finally:
            broadcaster.unsubscribe_messages(tenant_id, session_id_str, q)
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


def _should_forward_to_salesperson(msg: str, user_id: str) -> bool:
    """
    Decide si un evento delta del broadcaster debe enviarse a un SALESPERSON.

    - pending_leads: solo si el payload contiene salesperson_id == user_id.
    - settings: nunca (los vendedores no gestionan configuración del tenant).
    - Cualquier otro evento no reconocido: no se reenvía.
    """
    try:
        event_name = ""
        data_json = ""
        for line in msg.split("\n"):
            if line.startswith("event: "):
                event_name = line[7:]
            elif line.startswith("data: "):
                data_json = line[6:]
        if event_name == "pending_leads" and data_json:
            return json.loads(data_json).get("salesperson_id") == user_id
        return False
    except Exception:
        return False


def _build_dashboard_snapshot(tenant, user=None) -> str:
    """
    Consulta DB de forma síncrona y construye el frame SSE 'snapshot'
    con pending_leads, salespeople y settings en una sola respuesta.
    Se llama desde el generador síncrono — no necesita sync_to_async.

    El contenido se filtra según el rol del usuario:
    - MANAGER/ADMIN: snapshot completo (todos los leads, pending, vendedores, settings).
    - SALESPERSON: solo sus propias sesiones asignadas; sin pending, sin lista de vendedores,
      sin settings (consistente con lo que retorna el REST API leads_dashboard_api).
    """
    from crm.adapters.dependency_injection import DIContainer
    from crm.models import AppUser
    from crm.views.dashboard import _serialize_session

    container = DIContainer.instance()
    tenant_id = tenant.id

    is_manager = user is None or user.role in (AppUser.Role.MANAGER, AppUser.Role.ADMIN)

    pending = (
        list(container.session_repo.get_pending_sessions(tenant_id, limit=50))
        if is_manager
        else []
    )

    session_filters = None if is_manager else {"salesperson_id": str(user.id)}
    all_leads = container.session_repo.get_dashboard_sessions(
        tenant_id, limit=100, filters=session_filters
    )

    salespeople = (
        container.user_repo.find_salespeople_by_tenant(tenant_id) if is_manager else []
    )
    settings_data = container.tenant_repo.find_by_id(tenant_id) if is_manager else None

    all_sessions = list(pending) + list(all_leads)
    salesperson_ids = {s.salesperson_id for s in all_sessions if s.salesperson_id}
    users_cache = (
        container.session_repo.get_users_email_batch(salesperson_ids)
        if salesperson_ids
        else {}
    )

    lead_ids = {s.lead_id for s in all_sessions}
    leads_cache = (
        container.lead_repo.get_profile_names_batch(lead_ids, tenant_id)
        if lead_ids
        else {}
    )

    payload = {
        "pending_leads": [
            _serialize_session(s, users_cache, leads_cache) for s in pending
        ],
        "leads": [_serialize_session(s, users_cache, leads_cache) for s in all_leads],
        "salespeople": salespeople,
        "settings": {
            "routing_mode": settings_data.get("routing_mode")
            if settings_data
            else None,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    data = json.dumps(payload, separators=(",", ":"), default=str)
    return f"event: snapshot\ndata: {data}\n\n"
