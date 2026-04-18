"""
crm/adapters/sse/broadcaster.py — In-memory SSE pub/sub broadcaster.

Limitación: funciona solo con --workers 1 (proceso único).
Si Railway escala a múltiples workers, se necesitará Redis pub/sub.

Thread-safety: asyncio.Queue.put_nowait() es seguro desde threads síncronos
(el GIL protege el deque interno y _wakeup_next usa call_soon_threadsafe).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SSEBroadcaster:
    def __init__(self) -> None:
        # tenant_id (str) → set de asyncio.Queue activas (dashboard stream)
        self._dashboard: dict[str, set[asyncio.Queue]] = defaultdict(set)
        # tenant_id → session_id → set de asyncio.Queue activas (messages stream)
        self._messages: dict[str, dict[str, set[asyncio.Queue]]] = defaultdict(
            lambda: defaultdict(set)
        )

    # ── Suscripción / desuscripción ──────────────────────────────────────

    def subscribe_dashboard(self, tenant_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._dashboard[tenant_id].add(q)
        return q

    def unsubscribe_dashboard(self, tenant_id: str, q: asyncio.Queue) -> None:
        self._dashboard[tenant_id].discard(q)

    def subscribe_messages(self, tenant_id: str, session_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._messages[tenant_id][session_id].add(q)
        return q

    def unsubscribe_messages(
        self, tenant_id: str, session_id: str, q: asyncio.Queue
    ) -> None:
        self._messages[tenant_id][session_id].discard(q)

    # ── Publicación ──────────────────────────────────────────────────────

    def publish_dashboard(self, tenant_id: str, event: str, payload: dict) -> None:
        msg = _encode_sse(event, payload)
        dead: set[asyncio.Queue] = set()
        for q in set(self._dashboard.get(tenant_id, set())):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                dead.add(q)
        if dead:
            self._dashboard[tenant_id] -= dead
            logger.debug(
                "SSE: %d conexiones dashboard lentas descartadas (tenant=%s)",
                len(dead),
                tenant_id,
            )

    def publish_message(
        self, tenant_id: str, session_id: str, event: str, payload: dict
    ) -> None:
        msg = _encode_sse(event, payload)
        dead: set[asyncio.Queue] = set()
        for q in set(self._messages.get(tenant_id, {}).get(session_id, set())):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                dead.add(q)
        if dead:
            self._messages[tenant_id][session_id] -= dead

    # ── Diagnóstico ──────────────────────────────────────────────────────

    def connection_count(self) -> dict[str, int]:
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
