"""
crm/application/use_cases/process_message.py — Caso de uso principal.

Orquesta el flujo completo de procesamiento de un mensaje de WhatsApp:
1. Lookup de Tenant
2. Upsert del Lead
3. Obtener/crear ChatSession
4. Guardar mensaje entrante
5. Ejecutar FSM
6. Registrar AuditLog
7. Enviar respuesta (fuera de transacción)
8. Guardar mensaje saliente

REGLA SRE: Las llamadas de red van FUERA de transaction.atomic().
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, replace
from typing import Any

from django.db import IntegrityError, transaction

from crm.domain.entities import SessionEntity
from crm.domain.ports import (
    AuditEntry,
    AuditLogger,
    LeadRepository,
    MessageProvider,
    MessageRepository,
    SendMessageRequest,
    SendMessageResult,
    SessionRepository,
    TenantRepository,
)
from crm.adapters.messaging.twilio_adapter import MessagingError
from crm.services.fsm_engine import FSMContext, FSMResult, advance_fsm

from core.log_utils import mask_pii, stage_start, stage_end, tenant_id_var

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessMessageResult:
    """Resultado del caso de uso."""

    status: str
    message_created: bool = False
    outbound_message_sid: str | None = None
    reply_text: str | None = None
    reply_interactive: dict[str, Any] | None = None


class ProcessMessageUseCase:
    """
    Caso de uso: procesar un payload de webhook de Twilio.

    Recibe todos los puertos como dependencias inyectadas (Inversión de Dependencias).
    """

    def __init__(
        self,
        lead_repo: LeadRepository,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
        message_provider: MessageProvider,
        audit_logger: AuditLogger,
        tenant_repo: TenantRepository,
        content_sids: dict[str, str] | None = None,
    ) -> None:
        self._lead_repo = lead_repo
        self._session_repo = session_repo
        self._message_repo = message_repo
        self._message_provider = message_provider
        self._audit_logger = audit_logger
        self._tenant_repo = tenant_repo
        self._content_sids = content_sids or {}

    def execute(self, payload: dict[str, Any]) -> ProcessMessageResult:
        message_sid: str = payload.get("MessageSid", "")
        if not message_sid:
            return ProcessMessageResult(status="error_no_message_sid")

        stage_start("idempotency_check")

        # Idempotencia temprana
        if self._message_repo.exists_by_provider_id(message_sid):
            stage_end(
                "idempotency_check",
                logger,
                extra={"message_sid": message_sid, "result": "duplicate_ignored"},
            )
            logger.info(
                "UseCase: MessageSid duplicado. Ignorando.",
                extra={
                    "component_name": "process_message_use_case",
                    "message_sid": message_sid,
                },
            )
            return ProcessMessageResult(status="duplicate_ignored")

        stage_end(
            "idempotency_check",
            logger,
            extra={"message_sid": message_sid},
        )

        stage_start("tenant_resolution")

        # Resolver tenant
        tenant_phone_id = payload.get("To", "").replace("whatsapp:", "").lstrip("+")
        tenant_id = self._tenant_repo.find_id_by_phone_number(tenant_phone_id)

        if tenant_id is None:
            stage_end(
                "tenant_resolution",
                logger,
                extra={"to_number": mask_pii(tenant_phone_id), "result": "not_found"},
            )
            logger.error(
                "UseCase: Tenant no encontrado.",
                extra={
                    "component_name": "process_message_use_case",
                    "to_number": mask_pii(tenant_phone_id),
                },
            )
            return ProcessMessageResult(status="tenant_not_found")

        tenant_id_var.set(str(tenant_id))

        stage_end(
            "tenant_resolution",
            logger,
            extra={"tenant_id": str(tenant_id)},
        )

        stage_start("lead_upsert")

        # Upsert Lead
        wa_id_raw = payload.get("WaId", "") or payload.get("From", "").replace(
            "whatsapp:", ""
        )
        wa_id_clean = wa_id_raw[:12]
        wa_id_hash = hashlib.sha256(wa_id_clean.encode()).hexdigest()

        lead = self._lead_repo.upsert(
            tenant_id=tenant_id,
            wa_id_hash=wa_id_hash,
            defaults={"wa_id": wa_id_clean},
        )

        stage_end(
            "lead_upsert",
            logger,
            extra={"lead_id": str(lead.id)},
        )

        stage_start("db_transaction")

        # Procesar sesión + mensaje + FSM dentro de transacción
        reply_result: FSMResult | None = None
        session: SessionEntity | None = None
        is_new_session = False
        message_created = False

        with transaction.atomic():
            # Obtener sesión con bloqueo de fila (SELECT FOR UPDATE)
            # Previene race conditions cuando dos webhooks del mismo lead llegan simultáneamente
            existing = self._session_repo.find_active_for_update(
                tenant_id=tenant_id,
                lead_id=lead.id,
            )

            if existing is None:
                # Expirar sesión inactiva (también usa select_for_update internamente)
                not_expired = self._session_repo.expire_if_inactive(
                    tenant_id=tenant_id,
                    lead_id=lead.id,
                    hours=24,
                )

                if not_expired is None:
                    # Crear nueva sesión (puede fallar por race condition con otro thread)
                    try:
                        with transaction.atomic():
                            session = self._session_repo.create(
                                tenant_id=tenant_id,
                                lead_id=lead.id,
                                status="BOT",
                            )
                    except IntegrityError:
                        # Otro thread ya creó la sesión. Re-fetch con lock.
                        session = self._session_repo.find_active_for_update(
                            tenant_id=tenant_id,
                            lead_id=lead.id,
                        )
                        if session is None:
                            raise

                    if session is not None and not is_new_session:
                        is_new_session = (
                            session.status == "BOT"
                            and not session.fsm_answers.get("current_step")
                        )

                        if is_new_session:
                            self._audit_logger.record(
                                AuditEntry(
                                    session_id=session.id,
                                    tenant_id=tenant_id,
                                    action="SESSION_START",
                                    old_value={},
                                    new_value={
                                        "status": session.status,
                                        "lead_id": str(lead.id),
                                    },
                                )
                            )
                else:
                    session = not_expired
            else:
                is_expired = self._session_repo.check_session_expired(
                    session_id=existing.id,
                    hours=24,
                )

                if is_expired:
                    self._session_repo.mark_as_abandoned(
                        existing.id, tenant_id=tenant_id
                    )

                    try:
                        with transaction.atomic():
                            session = self._session_repo.create(
                                tenant_id=tenant_id,
                                lead_id=lead.id,
                                status="BOT",
                            )
                    except IntegrityError:
                        session = self._session_repo.find_active_for_update(
                            tenant_id=tenant_id,
                            lead_id=lead.id,
                        )
                        if session is None:
                            raise

                    is_new_session = True

                    self._audit_logger.record(
                        AuditEntry(
                            session_id=session.id,
                            tenant_id=tenant_id,
                            action="SESSION_START",
                            old_value={},
                            new_value={
                                "status": session.status,
                                "lead_id": str(lead.id),
                            },
                        )
                    )
                else:
                    session = existing

            # Guardar mensaje entrante
            _message_type_map = {
                "text": "TEXT",
                "button": "TEXT",
                "interactive": "TEXT",  # Botones interactivos de Twilio (listas, botones)
                "image": "IMAGE",
                "audio": "AUDIO",
                "document": "DOCUMENTO",
            }
            _raw_type = payload.get("MessageType", "text").lower()
            _message_type = _message_type_map.get(_raw_type, "TEXT")
            _body = (
                payload.get("Body", "")
                or payload.get("ButtonPayload", "")
                or payload.get("ButtonText", "")
                or payload.get("MediaUrl0", "")
            )

            try:
                with transaction.atomic():
                    self._message_repo.create(
                        tenant_id=tenant_id,
                        session_id=session.id,
                        provider_message_id=message_sid,
                        direction="INBOUND",
                        message_type=_message_type,
                        body=_body,
                    )
                    message_created = True

                    self._audit_logger.record(
                        AuditEntry(
                            session_id=session.id,
                            tenant_id=tenant_id,
                            action="MSG_RECEIVED",
                            old_value={},
                            new_value={
                                "message_sid": message_sid,
                                "message_type": _message_type,
                                "body_length": len(_body),
                                "is_new_session": is_new_session,
                            },
                        )
                    )
            except IntegrityError:
                # Otro thread ya persistió este mensaje (race condition en idempotencia).
                # Continuamos procesando la FSM normalmente.
                message_created = False

            # Ejecutar FSM
            old_fsm_state = dict(session.fsm_answers) if session.fsm_answers else {}
            old_status = session.status

            fsm_context = FSMContext(
                current_step=session.fsm_answers.get("current_step"),
                fsm_answers=session.fsm_answers,
                status=session.status,
                error_count=session.fsm_answers.get("error_count", 0),
            )

            reply_result = advance_fsm(fsm_context, _body, _message_type)

            # Aplicar cambios de FSM a la entidad (inmutable via replace)
            updated_session = session
            if reply_result.updated_fsm_answers != session.fsm_answers:
                updated_session = replace(
                    updated_session, fsm_answers=reply_result.updated_fsm_answers
                )
            if reply_result.new_status and reply_result.new_status != session.status:
                updated_session = replace(
                    updated_session, status=reply_result.new_status
                )
            if (
                reply_result.urgency_score
                and reply_result.urgency_score != session.urgency_score
            ):
                updated_session = replace(
                    updated_session, urgency_score=reply_result.urgency_score
                )

            new_fsm_state = (
                dict(updated_session.fsm_answers) if updated_session.fsm_answers else {}
            )
            new_status = updated_session.status

            if (
                old_fsm_state.get("current_step") != new_fsm_state.get("current_step")
                or old_status != new_status
            ):
                self._audit_logger.record(
                    AuditEntry(
                        session_id=updated_session.id,
                        tenant_id=tenant_id,
                        action="FSM_TRANSITION",
                        old_value={"status": old_status, "fsm_answers": old_fsm_state},
                        new_value={"status": new_status, "fsm_answers": new_fsm_state},
                    )
                )

            # Persistir cambios de sesión
            self._session_repo.save(updated_session)

        stage_end(
            "db_transaction",
            logger,
            extra={
                "session_id": str(session.id) if session else None,
                "is_new_session": is_new_session,
                "message_created": message_created,
            },
        )

        # FUERA de transacción: enviar respuesta
        outbound_sid: str | None = None
        if reply_result and reply_result.text:
            stage_start("twilio_send")
            lead_phone = payload.get("From", "").replace("whatsapp:", "").lstrip("+")
            lead_phone_masked = mask_pii(lead_phone)

            current_step = reply_result.updated_fsm_answers.get("current_step")
            content_sid = self._content_sids.get(current_step)

            send_request = SendMessageRequest(
                to_number=lead_phone,
                from_number=tenant_phone_id,
                text=reply_result.text,
                interactive_payload=reply_result.interactive,
                content_sid=content_sid,
            )

            try:
                send_result: SendMessageResult = self._message_provider.send_message(
                    send_request
                )
            except MessagingError:
                logger.exception(
                    "UseCase: Fallo al enviar respuesta (mensaje entrante ya persistido).",
                    extra={
                        "component_name": "process_message_use_case",
                        "message_sid": message_sid,
                        "session_id": str(session.id),
                    },
                )
                send_result = SendMessageResult(
                    provider_message_id=None,
                    success=False,
                )

            if send_result.success and send_result.provider_message_id:
                outbound_sid = send_result.provider_message_id
                self._message_repo.create(
                    tenant_id=tenant_id,
                    session_id=session.id,
                    provider_message_id=outbound_sid,
                    direction="OUTBOUND",
                    message_type="TEXT",
                    body=reply_result.text,
                )

            stage_end(
                "twilio_send",
                logger,
                extra={
                    "success": send_result.success,
                    "provider_message_id": send_result.provider_message_id,
                },
            )

        logger.info(
            "UseCase: Mensaje procesado exitosamente.",
            extra={
                "component_name": "process_message_use_case",
                "message_sid": message_sid,
                "lead_id": str(lead.id),
                "session_id": str(session.id),
                "msg_created": message_created,
            },
        )

        return ProcessMessageResult(
            status="processed",
            message_created=message_created,
            outbound_message_sid=outbound_sid,
            reply_text=reply_result.text if reply_result else None,
            reply_interactive=reply_result.interactive if reply_result else None,
        )
