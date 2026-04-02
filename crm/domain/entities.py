"""
crm/domain/entities.py — Entidades de dominio puras.

Cero dependencias externas. Solo Python estándar.
Estas entidades representan el modelo conceptual del negocio,
desacoplado de Django ORM, PostgreSQL o cualquier framework.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

__all__ = ["LeadEntity", "SessionEntity", "MessageEntity"]


@dataclass(frozen=True)
class LeadEntity:
    """Prospecto con privacidad garantizada (sin PII en texto plano)."""

    id: UUID
    tenant_id: UUID
    wa_id_hash: str
    first_name: str | None = None
    last_interaction: datetime | None = None
    is_deleted: bool = False


@dataclass(frozen=True)
class SessionEntity:
    """Sesión conversacional con estado FSM y métricas."""

    id: UUID
    tenant_id: UUID
    lead_id: UUID
    status: str
    fsm_answers: dict[str, Any] = field(default_factory=dict)
    urgency_score: int = 0
    salesperson_id: UUID | None = None
    last_fsm_step: str | None = None
    last_client_message_at: datetime | None = None
    last_message_timestamp: str | None = None
    lost_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_deleted: bool = False


@dataclass(frozen=True)
class MessageEntity:
    """Mensaje inmutable de la conversación."""

    id: UUID
    tenant_id: UUID
    session_id: UUID
    provider_message_id: str
    direction: str
    message_type: str
    body: str
    created_at: datetime | None = None
