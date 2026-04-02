"""
crm/application/use_cases/assign_lead.py — Caso de uso para asignar un lead
a un vendedor (o desasignarlo).

Regla Event Sourcing: Todo cambio de asignación DEBE registrar un AuditLog.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from crm.domain.ports import AuditEntry, AuditLogger, SessionRepository, UserRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssignLeadResult:
    session_id: UUID
    status: str
    salesperson_id: UUID | None
    salesperson_name: str | None
    assigned_at: str | None


class AssignLeadUseCase:
    """
    Asigna o desasigna un vendedor a una sesión.
    - Si salesperson_id es un UUID: asigna y cambia status a CON_VENDEDOR.
    - Si salesperson_id es None: desasigna y cambia status a PENDING_ASSIGNMENT.
    """

    def __init__(
        self,
        session_repo: SessionRepository,
        user_repo: UserRepository,
        audit_logger: AuditLogger,
    ) -> None:
        self._session_repo = session_repo
        self._user_repo = user_repo
        self._audit_logger = audit_logger

    def execute(
        self,
        session_id: UUID,
        tenant_id: UUID,
        salesperson_id: UUID | None,
    ) -> AssignLeadResult | None:
        session = self._session_repo.find_by_id(session_id, tenant_id)
        if session is None:
            return None

        old_status = session.status
        old_salesperson_id = session.salesperson_id

        if salesperson_id is not None:
            sp = self._user_repo.find_by_id_and_tenant(
                salesperson_id, tenant_id, role="SALESPERSON"
            )
            if sp is None:
                raise ValueError("Vendedor no encontrado en este tenant")

            result = self._session_repo.assign_salesperson(
                session_id, tenant_id, salesperson_id
            )
            if result is None:
                return None

            self._audit_logger.record(
                AuditEntry(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    action="LEAD_ASSIGNED",
                    old_value={
                        "status": old_status,
                        "salesperson_id": str(old_salesperson_id)
                        if old_salesperson_id
                        else None,
                    },
                    new_value={
                        "status": result.status,
                        "salesperson_id": str(salesperson_id),
                        "salesperson_email": sp["email"],
                    },
                )
            )

            return AssignLeadResult(
                session_id=result.id,
                status=result.status,
                salesperson_id=salesperson_id,
                salesperson_name=sp["email"].split("@")[0],
                assigned_at=result.updated_at.isoformat()
                if result.updated_at
                else None,
            )
        else:
            result = self._session_repo.assign_salesperson(session_id, tenant_id, None)
            if result is None:
                return None

            self._audit_logger.record(
                AuditEntry(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    action="LEAD_UNASSIGNED",
                    old_value={
                        "status": old_status,
                        "salesperson_id": str(old_salesperson_id)
                        if old_salesperson_id
                        else None,
                    },
                    new_value={
                        "status": result.status,
                        "salesperson_id": None,
                    },
                )
            )

            return AssignLeadResult(
                session_id=result.id,
                status=result.status,
                salesperson_id=None,
                salesperson_name=None,
                assigned_at=None,
            )
