"""
crm/application/use_cases/assign_lead.py — Caso de uso para asignar un lead
a un vendedor (o desasignarlo).

Regla Event Sourcing: Todo cambio de asignación DEBE registrar un AuditLog
dentro de la misma transacción atómica.

Soporta dos modos de routing:
- MANUAL: El Gerente asigna explícitamente a un vendedor.
- AUTO: Round-Robin automático al vendedor con menos sesiones activas.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from django.db import transaction

from core.log_utils import trace_id_var
from crm.domain.ports import (
    AuditEntry,
    AuditLogger,
    SessionRepository,
    TenantRepository,
    UserRepository,
)

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
    - Si salesperson_id es "AUTO" y tenant.routing_mode=AUTO: asigna Round-Robin.
    """

    def __init__(
        self,
        session_repo: SessionRepository,
        user_repo: UserRepository,
        tenant_repo: TenantRepository,
        audit_logger: AuditLogger,
    ) -> None:
        self._session_repo = session_repo
        self._user_repo = user_repo
        self._tenant_repo = tenant_repo
        self._audit_logger = audit_logger

    def execute(
        self,
        session_id: UUID,
        tenant_id: UUID,
        salesperson_id: Literal["AUTO"] | UUID | None,
    ) -> AssignLeadResult | None:
        session = self._session_repo.find_by_id(session_id, tenant_id)
        if session is None:
            return None

        old_status = session.status
        old_salesperson_id = session.salesperson_id

        # Auto-assign: buscar vendedor con menor carga
        if salesperson_id == "AUTO":
            tenant = self._tenant_repo.find_by_id(tenant_id)
            if tenant is None or tenant.get("routing_mode") != "AUTO":
                raise ValueError("Routing AUTO no habilitado para este tenant")

            salespeople = self._user_repo.find_salespeople_by_tenant(tenant_id)
            if not salespeople:
                raise ValueError("No hay vendedores disponibles en este tenant")

            # Ordenar por menor carga de sesiones activas
            salespeople_sorted = sorted(
                salespeople, key=lambda x: x["active_sessions_count"]
            )
            selected = salespeople_sorted[0]
            salesperson_id = selected["id"]

            logger.info(
                "Auto-assign Round-Robin",
                extra={
                    "component_name": "assign_lead_use_case",
                    "tenant_id": str(tenant_id),
                    "trace_id": trace_id_var.get() or "",
                    "session_id": str(session_id),
                    "selected_salesperson": selected["email"],
                    "active_sessions": selected["active_sessions_count"],
                },
            )

        if salesperson_id is not None and not isinstance(salesperson_id, str):
            sp = self._user_repo.find_by_id_and_tenant(
                salesperson_id, tenant_id
            )
            if sp is None:
                raise ValueError("Usuario no encontrado en este tenant")

            with transaction.atomic():
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
                assigned_at=result.assigned_at.isoformat()
                if result.assigned_at
                else None,
            )
        else:
            with transaction.atomic():
                result = self._session_repo.assign_salesperson(
                    session_id, tenant_id, None
                )
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
