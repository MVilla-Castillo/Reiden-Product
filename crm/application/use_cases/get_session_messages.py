"""
crm/application/use_cases/get_session_messages.py — Caso de uso para obtener
el historial de mensajes de una sesión.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from crm.domain.ports import MessageRepository, SessionRepository

import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GetSessionMessagesResult:
    session_id: UUID
    lead_id: UUID
    status: str
    messages: list[dict[str, Any]]


class GetSessionMessagesUseCase:
    def __init__(
        self,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
    ) -> None:
        self._session_repo = session_repo
        self._message_repo = message_repo

    def execute(
        self,
        session_id: UUID,
        tenant_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> GetSessionMessagesResult | None:
        session = self._session_repo.find_by_id(session_id, tenant_id)
        if session is None:
            return None

        messages = self._message_repo.find_by_session(
            session_id, tenant_id, limit=limit, offset=offset
        )

        serialized = [
            {
                "message_id": str(m.id),
                "direction": m.direction,
                "message_type": m.message_type,
                "body": m.body,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]

        return GetSessionMessagesResult(
            session_id=session.id,
            lead_id=session.lead_id,
            status=session.status,
            messages=serialized,
        )
