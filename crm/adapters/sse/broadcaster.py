"""
crm/adapters/sse/broadcaster.py — In-memory SSE pub/sub broadcaster.

Diseñado para WSGI (Django runserver / gunicorn sync workers).
Usa threading.Queue en lugar de asyncio.Queue porque:
  - El publisher (worker.py, dashboard_messages.py) corre en threads WSGI síncronos.
  - asyncio.Queue.put_nowait() desde un thread externo NO despierta
    el await queue.get() de otro event loop (cada request WSGI crea el suyo
    vía asgiref.async_to_sync). threading.Queue sí es thread-safe de verdad.

El consumer (sse.py) usa asyncio.to_thread(q.get, True, timeout) para esperar
sin bloquear el event loop del SSE view.

Limitación: in-memory → solo funciona con --workers 1 (proceso único).
Para escalar a múltiples workers en Railway se necesitará Redis pub/sub.
"""

from __future__ import annotations

import json
import logging
import queue as _queue
import threading
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SSEBroadcaster:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        # tenant_id (str) → set[threading.Queue]
        self._dashboard: dict[str, set[_queue.Queue]] = defaultdict(set)
        # tenant_id → session_id → set[threading.Queue]
        self._messages: dict[str, dict[str, set[_queue.Queue]]] = defaultdict(
            lambda: defaultdict(set)
        )

    # ── Suscripción / desuscripción ──────────────────────────────────────

    def subscribe_dashboard(self, tenant_id: str) -> _queue.Queue:
        q: _queue.Queue = _queue.Queue(maxsize=50)
        with self._lock:
            self._dashboard[tenant_id].add(q)
        return q

    def unsubscribe_dashboard(self, tenant_id: str, q: _queue.Queue) -> None:
        with self._lock:
            self._dashboard[tenant_id].discard(q)

    def subscribe_messages(self, tenant_id: str, session_id: str) -> _queue.Queue:
        q: _queue.Queue = _queue.Queue(maxsize=100)
        with self._lock:
            self._messages[tenant_id][session_id].add(q)
        return q

    def unsubscribe_messages(
        self, tenant_id: str, session_id: str, q: _queue.Queue
    ) -> None:
        with self._lock:
            self._messages[tenant_id][session_id].discard(q)

    # ── Publicación ──────────────────────────────────────────────────────

    def publish_dashboard(self, tenant_id: str, event: str, payload: dict) -> None:
        """Thread-safe: puede llamarse desde cualquier thread WSGI."""
        msg = _encode_sse(event, payload)
        with self._lock:
            subs = set(self._dashboard.get(tenant_id, set()))
        dead: set[_queue.Queue] = set()
        for q in subs:
            try:
                q.put_nowait(msg)
            except _queue.Full:
                dead.add(q)
        if dead:
            with self._lock:
                self._dashboard[tenant_id] -= dead
            logger.debug(
                "SSE: %d conexiones dashboard lentas descartadas (tenant=%s)",
                len(dead),
                tenant_id,
            )

    def publish_message(
        self, tenant_id: str, session_id: str, event: str, payload: dict
    ) -> None:
        """Thread-safe: puede llamarse desde cualquier thread WSGI."""
        msg = _encode_sse(event, payload)
        with self._lock:
            subs = set(self._messages.get(tenant_id, {}).get(session_id, set()))
        dead: set[_queue.Queue] = set()
        for q in subs:
            try:
                q.put_nowait(msg)
            except _queue.Full:
                dead.add(q)
        if dead:
            with self._lock:
                self._messages[tenant_id][session_id] -= dead

    # ── Diagnóstico ──────────────────────────────────────────────────────

    def connection_count(self) -> dict[str, int]:
        with self._lock:
            return {
                "dashboard": sum(len(qs) for qs in self._dashboard.values()),
                "messages": sum(
                    len(qs)
                    for sessions in self._messages.values()
                    for qs in sessions.values()
                ),
            }


def _encode_sse(event: str, payload: dict) -> str:
    data = json.dumps(payload, separators=(",", ":"), default=str)
    return f"event: {event}\ndata: {data}\n\n"


def heartbeat_frame() -> str:
    ts = datetime.now(timezone.utc).isoformat()
    return f": heartbeat {ts}\n\n"


# Singleton de módulo — se crea una vez al importar
broadcaster = SSEBroadcaster()
