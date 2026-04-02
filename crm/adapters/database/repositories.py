"""
crm/adapters/database/repositories.py — Implementaciones Django ORM de los ports.

Cada clase adapta el protocolo del dominio (crm.domain.ports) al ORM de Django.
Conversión bidireccional: Model → Entity y Entity → Model.

REGLAS SRE:
- update_or_create dentro de transaction.atomic() para evitar race conditions.
- save() siempre con update_fields explícitos para no reescribir filas completas.
- select_related('lead') obligatorio en queries de ChatSession para evitar N+1.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from django.db import connection, models, transaction
from django.utils import timezone

from core.crypto import decrypt, encrypt
from crm.domain.entities import LeadEntity, MessageEntity, SessionEntity
from crm.domain.ports import (
    AuditEntry,
    AuditLogger,
    LeadRepository,
    MessageRepository,
    SessionRepository,
    TenantRepository,
    UserRepository,
)
from crm.models import AppUser, AuditLog, ChatSession, Lead, Message, Tenant


def _tenant_to_id(tenant: Any) -> Any:
    """Acepta UUID, Tenant model, o tenant_id directo."""
    if hasattr(tenant, "id"):
        return tenant.id
    return tenant


def _lead_to_entity(model: Lead) -> LeadEntity:
    return LeadEntity(
        id=model.id,
        tenant_id=model.tenant_id,
        wa_id_hash=model.wa_id_hash,
        first_name=model.first_name,
        last_interaction=model.last_interaction,
        is_deleted=model.is_deleted,
    )


def _session_to_entity(model: ChatSession) -> SessionEntity:
    return SessionEntity(
        id=model.id,
        tenant_id=model.tenant_id,
        lead_id=model.lead_id,
        status=model.status,
        fsm_answers=dict(model.fsm_answers) if model.fsm_answers else {},
        urgency_score=model.urgency_score,
        salesperson_id=model.salesperson_id,
        last_fsm_step=model.last_fsm_step,
        last_client_message_at=model.last_client_message_at,
        last_message_timestamp=model.last_message_timestamp,
        lost_reason=model.lost_reason,
        created_at=model.created_at,
        updated_at=model.updated_at,
        is_deleted=model.is_deleted,
    )


def _message_to_entity(model: Message) -> MessageEntity:
    return MessageEntity(
        id=model.id,
        tenant_id=model.tenant_id,
        session_id=model.session_id,
        provider_message_id=model.provider_message_id,
        direction=model.direction,
        message_type=model.message_type,
        body=model.body,
        created_at=model.created_at,
    )


class DjangoLeadRepository(LeadRepository):
    def find_by_wa_id_hash(self, tenant: Any, wa_id_hash: str) -> LeadEntity | None:
        tenant_id = _tenant_to_id(tenant)
        try:
            model = Lead.objects.get(
                tenant_id=tenant_id,
                wa_id_hash=wa_id_hash,
                is_deleted=False,
            )
            return _lead_to_entity(model)
        except Lead.DoesNotExist:
            return None

    def upsert(
        self, tenant: Any, wa_id_hash: str, defaults: dict[str, Any]
    ) -> LeadEntity:
        """
        Upsert atómico seguro contra race conditions.

        Usa INSERT ... ON CONFLICT DO UPDATE (PostgreSQL) via raw SQL
        para evitar el gap entre SELECT e INSERT de update_or_create.
        El wa_id se cifra antes de persistir (PII compliance).
        """
        tenant_id = _tenant_to_id(tenant)
        first_name = defaults.get("first_name")
        wa_id_plain = defaults.get("wa_id", "")
        wa_id_encrypted = encrypt(wa_id_plain) if wa_id_plain else ""

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {Lead._meta.db_table} (id, tenant_id, wa_id_hash, wa_id, first_name, is_deleted, last_interaction)
                    VALUES (gen_random_uuid(), %s, %s, %s, %s, False, NOW())
                    ON CONFLICT (wa_id_hash)
                    DO UPDATE SET
                        tenant_id = EXCLUDED.tenant_id,
                        wa_id = EXCLUDED.wa_id,
                        first_name = COALESCE(EXCLUDED.first_name, {Lead._meta.db_table}.first_name),
                        last_interaction = NOW()
                    RETURNING id, tenant_id, wa_id_hash, first_name, is_deleted, last_interaction
                    """,
                    [
                        str(tenant_id),
                        wa_id_hash,
                        wa_id_encrypted,
                        first_name,
                    ],
                )
                row = cursor.fetchone()

        return LeadEntity(
            id=row[0],
            tenant_id=row[1],
            wa_id_hash=row[2],
            first_name=row[3],
            is_deleted=row[4],
            last_interaction=row[5],
        )

    def for_tenant(self, tenant: Any) -> list[LeadEntity]:
        tenant_id = _tenant_to_id(tenant)
        return [
            _lead_to_entity(m)
            for m in Lead.objects.filter(tenant_id=tenant_id, is_deleted=False)
        ]

    def find_wa_id(
        self, lead_id: uuid.UUID, tenant_id: uuid.UUID | None = None
    ) -> str | None:
        filters: dict[str, uuid.UUID | bool] = {"id": lead_id, "is_deleted": False}
        if tenant_id is not None:
            filters["tenant_id"] = tenant_id
        result = Lead.objects.filter(**filters).values_list("wa_id", flat=True).first()
        if result is None:
            return None
        return decrypt(result)


class DjangoSessionRepository(SessionRepository):
    ACTIVE_STATUSES = [
        ChatSession.Status.BOT,
        ChatSession.Status.PENDING_ASSIGNMENT,
        ChatSession.Status.CON_VENDEDOR,
    ]

    def find_active(self, tenant: Any, lead_id: Any) -> SessionEntity | None:
        tenant_id = _tenant_to_id(tenant)
        model = (
            ChatSession.objects.select_related("lead")
            .filter(
                lead_id=lead_id,
                tenant_id=tenant_id,
                status__in=self.ACTIVE_STATUSES,
                is_deleted=False,
            )
            .order_by("-created_at")
            .first()
        )
        if model is None:
            return None
        return _session_to_entity(model)

    def find_by_id(self, session_id: uuid.UUID, tenant: Any) -> SessionEntity | None:
        tenant_id = _tenant_to_id(tenant)
        try:
            model = ChatSession.objects.select_related("lead").get(
                id=session_id, tenant_id=tenant_id, is_deleted=False
            )
            return _session_to_entity(model)
        except ChatSession.DoesNotExist:
            return None

    def find_active_for_update(self, tenant: Any, lead_id: Any) -> SessionEntity | None:
        """
        Busca sesión activa con bloqueo de fila (SELECT FOR UPDATE).
        Previene race conditions cuando dos webhooks del mismo lead llegan simultáneamente.
        Incluye select_related('lead') para evitar N+1 al acceder a lead.id.
        """
        tenant_id = _tenant_to_id(tenant)
        model = (
            ChatSession.objects.select_for_update()
            .select_related("lead")
            .filter(
                lead_id=lead_id,
                tenant_id=tenant_id,
                status__in=self.ACTIVE_STATUSES,
                is_deleted=False,
            )
            .order_by("-created_at")
            .first()
        )
        if model is None:
            return None
        return _session_to_entity(model)

    def create(self, tenant: Any, lead_id: Any, status: str = "BOT") -> SessionEntity:
        tenant_id = _tenant_to_id(tenant)
        model = ChatSession.objects.create(
            tenant_id=tenant_id,
            lead_id=lead_id,
            status=status,
        )
        return _session_to_entity(model)

    def save(
        self, session: SessionEntity, update_fields: list[str] | None = None
    ) -> SessionEntity:
        """
        Persiste cambios usando UPDATE directo (sin SELECT previo).
        Envuelto en transaction.atomic() para garantizar atomicidad si se llama fuera de un use case.
        """
        fields_to_update: list[str] = []
        update_data: dict[str, Any] = {}

        if session.status:
            update_data["status"] = session.status
            fields_to_update.append("status")
        if session.fsm_answers is not None:
            update_data["fsm_answers"] = session.fsm_answers
            fields_to_update.append("fsm_answers")
        update_data["urgency_score"] = session.urgency_score
        fields_to_update.append("urgency_score")
        update_data["last_fsm_step"] = session.last_fsm_step
        fields_to_update.append("last_fsm_step")
        update_data["last_client_message_at"] = session.last_client_message_at
        fields_to_update.append("last_client_message_at")
        update_data["last_message_timestamp"] = session.last_message_timestamp
        fields_to_update.append("last_message_timestamp")
        update_data["lost_reason"] = session.lost_reason
        fields_to_update.append("lost_reason")
        update_data["salesperson_id"] = session.salesperson_id
        fields_to_update.append("salesperson_id")
        update_data["is_deleted"] = session.is_deleted
        fields_to_update.append("is_deleted")

        if update_fields:
            fields_to_update = [f for f in update_fields if f in fields_to_update]
            update_data = {k: v for k, v in update_data.items() if k in update_fields}

        if not fields_to_update:
            return session

        with transaction.atomic():
            ChatSession.objects.filter(id=session.id).update(**update_data)

        return session

    def assign_salesperson(
        self,
        session_id: uuid.UUID,
        tenant: Any,
        salesperson_id: uuid.UUID | None,
    ) -> SessionEntity | None:
        tenant_id = _tenant_to_id(tenant)
        with transaction.atomic():
            ChatSession.objects.filter(
                id=session_id, tenant_id=tenant_id, is_deleted=False
            ).update(
                salesperson_id=salesperson_id,
                status=(
                    ChatSession.Status.CON_VENDEDOR
                    if salesperson_id
                    else ChatSession.Status.PENDING_ASSIGNMENT
                ),
            )
            model = (
                ChatSession.objects.select_related("lead").filter(id=session_id).first()
            )
            if model is None:
                return None
            return _session_to_entity(model)

    def change_status(
        self, session_id: uuid.UUID, tenant: Any, new_status: str
    ) -> SessionEntity | None:
        tenant_id = _tenant_to_id(tenant)
        with transaction.atomic():
            ChatSession.objects.filter(
                id=session_id, tenant_id=tenant_id, is_deleted=False
            ).update(status=new_status)
            model = (
                ChatSession.objects.select_related("lead").filter(id=session_id).first()
            )
            if model is None:
                return None
            return _session_to_entity(model)

    def get_dashboard_sessions(
        self, tenant: Any, limit: int = 50
    ) -> list[SessionEntity]:
        tenant_id = _tenant_to_id(tenant)
        models = (
            ChatSession.tenant_objects.for_tenant(tenant_id)
            .order_by("-urgency_score", "-updated_at")
            .select_related("lead")[:limit]
        )
        return [_session_to_entity(m) for m in models]

    def expire_if_inactive(
        self,
        tenant: Any,
        lead_id: Any,
        hours: int = 24,
    ) -> SessionEntity | None:
        """
        Si la sesión activa lleva más de `hours` sin actividad, la marca como ABANDONO_BOT.
        Retorna None si la sesión fue expirada (caller debe crear una nueva).
        Usa select_for_update() para evitar race conditions con otros workers.
        """
        tenant_id = _tenant_to_id(tenant)
        model = (
            ChatSession.objects.select_for_update()
            .filter(
                lead_id=lead_id,
                tenant_id=tenant_id,
                status__in=self.ACTIVE_STATUSES,
                is_deleted=False,
            )
            .order_by("-created_at")
            .first()
        )
        if model is None:
            return None

        if model.updated_at < timezone.now() - timedelta(hours=hours):
            model.status = ChatSession.Status.ABANDONO_BOT
            model.save(update_fields=["status", "updated_at"])
            return None

        return _session_to_entity(model)


class DjangoMessageRepository(MessageRepository):
    def exists_by_provider_id(
        self, provider_message_id: str, tenant_id: uuid.UUID | None = None
    ) -> bool:
        filters: dict[str, str | bool] = {
            "provider_message_id": provider_message_id,
            "is_deleted": False,
        }
        if tenant_id is not None:
            filters["tenant_id"] = tenant_id
        return Message.objects.filter(**filters).exists()

    def create(
        self,
        tenant: Any,
        session_id: Any,
        provider_message_id: str,
        direction: str,
        message_type: str,
        body: str,
    ) -> MessageEntity:
        tenant_id = _tenant_to_id(tenant)
        model = Message.objects.create(
            tenant_id=tenant_id,
            session_id=session_id,
            provider_message_id=provider_message_id,
            direction=direction,
            message_type=message_type,
            body=body,
        )
        return _message_to_entity(model)

    def find_by_session(
        self, session_id: uuid.UUID, tenant: Any
    ) -> list[MessageEntity]:
        tenant_id = _tenant_to_id(tenant)
        models = (
            Message.objects.filter(
                session_id=session_id,
                tenant_id=tenant_id,
                is_deleted=False,
            )
            .order_by("created_at")
            .select_related("session")
        )
        return [_message_to_entity(m) for m in models]


class DjangoAuditLogger(AuditLogger):
    def record(self, entry: AuditEntry) -> None:
        AuditLog.objects.create(
            session_id=entry.session_id,
            tenant_id=entry.tenant_id,
            action=entry.action,
            old_value=entry.old_value,
            new_value=entry.new_value,
            actor_id=entry.actor_id,
        )


class DjangoTenantRepository(TenantRepository):
    def find_id_by_phone_number(self, phone_number_id: str) -> uuid.UUID | None:
        result = (
            Tenant.objects.filter(phone_number_id=phone_number_id)
            .values_list("id", flat=True)
            .first()
        )
        return result


class DjangoUserRepository(UserRepository):
    def find_salespeople_by_tenant(self, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
        salespeople = (
            AppUser.objects.filter(
                tenant_id=tenant_id,
                role=AppUser.Role.SALESPERSON,
                is_active=True,
            )
            .annotate(
                active_sessions_count=models.Count(
                    "assigned_sessions",
                    filter=models.Q(
                        assigned_sessions__status__in=[
                            ChatSession.Status.CON_VENDEDOR,
                            ChatSession.Status.PENDING_ASSIGNMENT,
                            ChatSession.Status.BOT,
                        ],
                        assigned_sessions__is_deleted=False,
                    ),
                )
            )
            .values("id", "email", "role", "active_sessions_count")
        )
        return [
            {
                "id": sp["id"],
                "name": sp["email"].split("@")[0],
                "email": sp["email"],
                "active_sessions_count": sp["active_sessions_count"],
            }
            for sp in salespeople
        ]

    def find_by_id_and_tenant(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        role: str | None = None,
    ) -> dict[str, Any] | None:
        filters: dict[str, Any] = {
            "id": user_id,
            "tenant_id": tenant_id,
            "is_active": True,
        }
        if role:
            filters["role"] = role

        user = AppUser.objects.filter(**filters).values("id", "email", "role").first()
        if not user:
            return None
        return {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"],
        }
