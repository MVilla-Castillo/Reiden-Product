"""
crm/application/use_cases/send_outbound_message.py — Caso de uso para que un
vendedor envíe un mensaje a un lead vía Twilio.

Regla Event Sourcing: Todo mensaje saliente DEBE registrar un AuditLog.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

import sentry_sdk

from crm.domain.ports import (
    AuditEntry,
    AuditLogger,
    LeadRepository,
    MessageProvider,
    MessageRepository,
    SendMessageRequest,
    SendMessageResult,
    SessionRepository,
)

logger = logging.getLogger(__name__)


class MessageDeliveryError(Exception):
    """Error de dominio: fallo al entregar un mensaje vía proveedor externo."""


@dataclass(frozen=True)
class SendOutboundMessageResult:
    message_id: str
    direction: str
    body: str
    created_at: str
    provider_message_sid: str | None


class SendOutboundMessageUseCase:
    """
    Envía un mensaje de un vendedor a un lead por WhatsApp.
    Solo permitido si la sesión está en estado CON_VENDEDOR.
    """

    VALID_STATUSES = {"CON_VENDEDOR"}

    def __init__(
        self,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
        lead_repo: LeadRepository,
        message_provider: MessageProvider,
        tenant_phone_number_id: str,
        audit_logger: AuditLogger,
    ) -> None:
        self._session_repo = session_repo
        self._message_repo = message_repo
        self._lead_repo = lead_repo
        self._message_provider = message_provider
        self._tenant_phone_number_id = tenant_phone_number_id
        self._audit_logger = audit_logger

    def execute(
        self,
        session_id: UUID,
        tenant_id: UUID,
        body: str,
    ) -> SendOutboundMessageResult | None:
        session = self._session_repo.find_by_id(session_id, tenant_id)
        if session is None:
            return None

        if session.status not in self.VALID_STATUSES:
            raise PermissionError(
                f"Sesión en estado '{session.status}'. Solo se permiten: {self.VALID_STATUSES}"
            )

        lead_wa_id = self._lead_repo.find_wa_id(session.lead_id, tenant_id)
        if not lead_wa_id:
            logger.error(
                "UseCase: Lead no encontrado para enviar mensaje.",
                extra={
                    "component_name": "send_outbound_message_use_case",
                    "lead_id": str(session.lead_id),
                },
            )
            return None

        send_request = SendMessageRequest(
            to_number=lead_wa_id,
            from_number=self._tenant_phone_number_id,
            text=body,
        )

        send_result: SendMessageResult = self._message_provider.send_message(
            send_request
        )

        if not send_result.success or not send_result.provider_message_id:
            logger.error(
                "UseCase: Fallo al enviar mensaje por Twilio.",
                extra={
                    "component_name": "send_outbound_message_use_case",
                    "session_id": str(session_id),
                },
            )
            sentry_sdk.capture_exception(
                extra={
                    "component_name": "send_outbound_message_use_case",
                    "session_id": str(session_id),
                    "tenant_id": str(tenant_id),
                    "failed_provider_message_id": send_result.provider_message_id,
                }
            )
            raise MessageDeliveryError("Fallo al enviar mensaje por Twilio")

        message = self._message_repo.create(
            tenant_id=tenant_id,
            session_id=session_id,
            provider_message_id=send_result.provider_message_id,
            direction="OUTBOUND",
            message_type="TEXT",
            body=body,
        )

        if session.first_response_at is None:
            self._session_repo.save(
                session,
                update_fields=["first_response_at"],
                first_response_at=message.created_at,
            )

        self._audit_logger.record(
            AuditEntry(
                session_id=session_id,
                tenant_id=tenant_id,
                action="OUTBOUND_MESSAGE_SENT",
                old_value={},
                new_value={
                    "message_id": str(message.id),
                    "provider_message_sid": send_result.provider_message_id,
                    "body_length": len(body),
                    "message_type": "TEXT",
                },
            )
        )

        return SendOutboundMessageResult(
            message_id=str(message.id),
            direction=message.direction,
            body=message.body,
            created_at=message.created_at.isoformat() if message.created_at else "",
            provider_message_sid=send_result.provider_message_id,
        )
