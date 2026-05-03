"""
crm/application/use_cases/change_session_status.py — Caso de uso para cerrar
una sesión (GANADO, PERDIDO, ABANDONO_BOT).

Regla Event Sourcing: Todo cambio de estado DEBE registrar un AuditLog
dentro de la misma transacción atómica.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from django.db import transaction

from crm.domain.ports import AuditEntry, AuditLogger, SessionRepository

logger = logging.getLogger(__name__)

VALID_CLOSE_STATUSES = {"GANADO", "PERDIDO", "ABANDONO_BOT"}
_MAX_LOST_REASON_LENGTH = 500


@dataclass(frozen=True)
class ChangeSessionStatusResult:
    session_id: UUID
    status: str
    updated_at: str


class ChangeSessionStatusUseCase:
    def __init__(
        self,
        session_repo: SessionRepository,
        audit_logger: AuditLogger,
    ) -> None:
        self._session_repo = session_repo
        self._audit_logger = audit_logger

    def execute(
        self,
        session_id: UUID,
        tenant_id: UUID,
        new_status: str,
        lost_reason: str | None = None,
    ) -> ChangeSessionStatusResult | None:
        if new_status not in VALID_CLOSE_STATUSES:
            raise ValueError(
                f"Estado no válido: '{new_status}'. Solo se permiten: {VALID_CLOSE_STATUSES}"
            )

        if new_status == "PERDIDO" and not lost_reason:
            raise ValueError("lost_reason es obligatorio para estado PERDIDO")

        if lost_reason and len(lost_reason) > _MAX_LOST_REASON_LENGTH:
            raise ValueError(
                f"lost_reason no puede superar {_MAX_LOST_REASON_LENGTH} caracteres"
            )

        old_session = self._session_repo.find_by_id(session_id, tenant_id)
        if old_session is None:
            return None

        old_status = old_session.status

        with transaction.atomic():
            result = self._session_repo.change_status(
                session_id, tenant_id, new_status, lost_reason=lost_reason
            )
            if result is None:
                return None

            self._audit_logger.record(
                AuditEntry(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    action="STATUS_CHANGED",
                    old_value={"status": old_status},
                    new_value={
                        "status": new_status,
                        "lost_reason": lost_reason,
                    },
                )
            )

        return ChangeSessionStatusResult(
            session_id=result.id,
            status=result.status,
            updated_at=result.updated_at.isoformat() if result.updated_at else "",
        )
