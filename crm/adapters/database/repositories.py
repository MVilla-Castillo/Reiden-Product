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
from datetime import date, datetime, timedelta
from typing import Any

from django.db import connection, models, transaction
from django.db.models import Count, Q, Avg, F
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
        assigned_at=model.assigned_at,
        first_response_at=model.first_response_at,
        closed_at=model.closed_at,
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
        is_deleted=model.is_deleted,
    )


class DjangoLeadRepository(LeadRepository):
    def find_by_wa_id_hash(
        self, tenant_id: uuid.UUID, wa_id_hash: str
    ) -> LeadEntity | None:
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
        self, tenant_id: uuid.UUID, wa_id_hash: str, defaults: dict[str, Any]
    ) -> LeadEntity:
        """
        Upsert atómico seguro contra race conditions.

        Usa INSERT ... ON CONFLICT DO UPDATE (PostgreSQL) via raw SQL
        para evitar el gap entre SELECT e INSERT de update_or_create.
        El wa_id se cifra antes de persistir (PII compliance).
        """
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

    def for_tenant(self, tenant_id: uuid.UUID) -> list[LeadEntity]:
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

    def find_active(
        self, tenant_id: uuid.UUID, lead_id: uuid.UUID
    ) -> SessionEntity | None:
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

    def find_by_id(
        self, session_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> SessionEntity | None:
        try:
            model = ChatSession.objects.select_related("lead").get(
                id=session_id, tenant_id=tenant_id, is_deleted=False
            )
            return _session_to_entity(model)
        except ChatSession.DoesNotExist:
            return None

    def find_active_for_update(
        self, tenant_id: uuid.UUID, lead_id: uuid.UUID
    ) -> SessionEntity | None:
        """
        Busca sesión activa con bloqueo de fila (SELECT FOR UPDATE).
        Previene race conditions cuando dos webhooks del mismo lead llegan simultáneamente.
        Incluye select_related('lead') para evitar N+1 al acceder a lead.id.
        """
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

    def create(
        self, tenant_id: uuid.UUID, lead_id: uuid.UUID, status: str = "BOT"
    ) -> SessionEntity:
        model = ChatSession.objects.create(
            tenant_id=tenant_id,
            lead_id=lead_id,
            status=status,
        )
        return _session_to_entity(model)

    def save(
        self,
        session: SessionEntity,
        update_fields: list[str] | None = None,
        **extra_fields: Any,
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
        update_data["assigned_at"] = session.assigned_at
        fields_to_update.append("assigned_at")
        update_data["first_response_at"] = session.first_response_at
        fields_to_update.append("first_response_at")
        update_data["closed_at"] = session.closed_at
        fields_to_update.append("closed_at")
        update_data["is_deleted"] = session.is_deleted
        fields_to_update.append("is_deleted")

        if update_fields:
            fields_to_update = [f for f in update_fields if f in fields_to_update]
            update_data = {k: v for k, v in update_data.items() if k in update_fields}

        if extra_fields:
            update_data.update(extra_fields)
            fields_to_update.extend(extra_fields.keys())

        if not fields_to_update:
            return session

        with transaction.atomic():
            ChatSession.objects.filter(id=session.id).update(**update_data)

        return session

    def assign_salesperson(
        self,
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
        salesperson_id: uuid.UUID | None,
    ) -> SessionEntity | None:
        now = timezone.now()
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
                assigned_at=now if salesperson_id else None,
            )
            model = (
                ChatSession.objects.select_related("lead").filter(id=session_id).first()
            )
            if model is None:
                return None
            return _session_to_entity(model)

    def change_status(
        self, session_id: uuid.UUID, tenant_id: uuid.UUID, new_status: str
    ) -> SessionEntity | None:
        now = timezone.now()
        terminal_statuses = {
            ChatSession.Status.GANADO,
            ChatSession.Status.PERDIDO,
            ChatSession.Status.ABANDONO_BOT,
        }
        with transaction.atomic():
            update_fields = {"status": new_status}
            if new_status in terminal_statuses:
                update_fields["closed_at"] = now
            ChatSession.objects.filter(
                id=session_id, tenant_id=tenant_id, is_deleted=False
            ).update(**update_fields)
            model = (
                ChatSession.objects.select_related("lead").filter(id=session_id).first()
            )
            if model is None:
                return None
            return _session_to_entity(model)

    def get_dashboard_sessions(
        self,
        tenant_id: uuid.UUID,
        limit: int = 50,
        filters: dict[str, Any] | None = None,
    ) -> list[SessionEntity]:
        qs = ChatSession.tenant_objects.for_tenant(tenant_id)

        if filters:
            date_from = filters.get("date_from")
            date_to = filters.get("date_to")

            if date_from:
                qs = qs.filter(created_at__date__gte=date_from)
            if date_to:
                qs = qs.filter(created_at__date__lte=date_to)

            if status := filters.get("status"):
                qs = qs.filter(status=status)

            if vehicle_type := filters.get("vehicle_type"):
                qs = qs.filter(fsm_answers__vehicle_type=vehicle_type)

            if payment_method := filters.get("payment_method"):
                qs = qs.filter(fsm_answers__payment_method=payment_method)

            if budget_range := filters.get("budget_range"):
                qs = qs.filter(fsm_answers__budget_range=budget_range)

            if purchase_intent := filters.get("purchase_intent"):
                qs = qs.filter(fsm_answers__purchase_intent=purchase_intent)

            if salesperson_id := filters.get("salesperson_id"):
                qs = qs.filter(salesperson_id=salesperson_id)

            if min_urgency := filters.get("min_urgency"):
                qs = qs.filter(urgency_score__gte=min_urgency)

            if max_urgency := filters.get("max_urgency"):
                qs = qs.filter(urgency_score__lte=max_urgency)

        models = qs.order_by("-urgency_score", "-updated_at").select_related("lead")[
            :limit
        ]
        return [_session_to_entity(m) for m in models]

    def get_pending_sessions(
        self, tenant_id: uuid.UUID, limit: int = 50
    ) -> list[SessionEntity]:
        """Retorna sesiones pendientes de asignación (status=BOT o PENDING_ASSIGNMENT)."""
        models = (
            ChatSession.tenant_objects.for_tenant(tenant_id)
            .filter(
                status__in=[
                    ChatSession.Status.BOT,
                    ChatSession.Status.PENDING_ASSIGNMENT,
                ]
            )
            .order_by("-urgency_score", "-updated_at")
            .select_related("lead")[:limit]
        )
        return [_session_to_entity(m) for m in models]

    def expire_if_inactive(
        self,
        tenant_id: uuid.UUID,
        lead_id: uuid.UUID,
        hours: int = 168,
    ) -> SessionEntity | None:
        """
        Si la sesión activa lleva más de `hours` sin ningún mensaje, la marca como PERDIDO.
        Si está en BOT/PENDING_ASSIGNMENT, la marca como ABANDONO_BOT.
        Usa select_for_update() para evitar race conditions con otros workers.
        """
        with transaction.atomic():
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

            last_activity = model.last_client_message_at
            if last_activity is None:
                last_activity = model.created_at

            if last_activity < timezone.now() - timedelta(hours=hours):
                if model.status in [
                    ChatSession.Status.BOT,
                    ChatSession.Status.PENDING_ASSIGNMENT,
                ]:
                    model.status = ChatSession.Status.ABANDONO_BOT
                    model.lost_reason = "Abandono en FSM"
                else:
                    model.status = ChatSession.Status.PERDIDO
                    model.lost_reason = "Inactividad 7 dias"
                    model.closed_at = timezone.now()

                model.save(
                    update_fields=["status", "lost_reason", "closed_at", "updated_at"]
                )
                return None

            return _session_to_entity(model)

    def check_session_expired(
        self,
        session_id: uuid.UUID,
        hours: int = 24,
    ) -> bool:
        model = (
            ChatSession.objects.select_for_update()
            .filter(
                id=session_id,
                status__in=self.ACTIVE_STATUSES,
                is_deleted=False,
            )
            .first()
        )
        if model is None:
            return False
        return model.updated_at < timezone.now() - timedelta(hours=hours)

    def mark_as_abandoned(self, session_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        now = timezone.now()
        ChatSession.objects.filter(id=session_id, tenant_id=tenant_id).update(
            status=ChatSession.Status.ABANDONO_BOT,
            closed_at=now,
        )

    def get_funnel_metrics(
        self, tenant_id: uuid.UUID, date_from: date, date_to: date
    ) -> dict[str, Any]:
        qs = ChatSession.tenant_objects.for_tenant(tenant_id).filter(
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        )

        total_leads = qs.count()
        completed_fsm = qs.filter(
            status__in=[
                ChatSession.Status.PENDING_ASSIGNMENT,
                ChatSession.Status.CON_VENDEDOR,
                ChatSession.Status.GANADO,
                ChatSession.Status.PERDIDO,
                ChatSession.Status.ABANDONO_BOT,
            ]
        ).count()
        assigned_leads = qs.exclude(salesperson_id__isnull=True).count()
        won_sessions = qs.filter(status=ChatSession.Status.GANADO).count()
        lost_sessions = qs.filter(status__in=[ChatSession.Status.PERDIDO]).count()
        abandoned_sessions = qs.filter(status=ChatSession.Status.ABANDONO_BOT).count()

        conversion_rate_fsm = (
            (completed_fsm / total_leads * 100) if total_leads > 0 else 0
        )
        conversion_rate_assignment = (
            (assigned_leads / completed_fsm * 100) if completed_fsm > 0 else 0
        )
        win_rate = (
            (won_sessions / (won_sessions + lost_sessions) * 100)
            if (won_sessions + lost_sessions) > 0
            else 0
        )

        return {
            "total_leads": total_leads,
            "completed_fsm": completed_fsm,
            "assigned_leads": assigned_leads,
            "won_sessions": won_sessions,
            "lost_sessions": lost_sessions,
            "abandoned_sessions": abandoned_sessions,
            "conversion_rate_fsm": round(conversion_rate_fsm, 2),
            "conversion_rate_assignment": round(conversion_rate_assignment, 2),
            "win_rate": round(win_rate, 2),
        }

    def get_fsm_distribution(
        self, tenant_id: uuid.UUID, date_from: date, date_to: date
    ) -> dict[str, Any]:
        qs = ChatSession.tenant_objects.for_tenant(tenant_id).filter(
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
            status__in=[
                ChatSession.Status.PENDING_ASSIGNMENT,
                ChatSession.Status.CON_VENDEDOR,
                ChatSession.Status.GANADO,
                ChatSession.Status.PERDIDO,
            ],
        )

        def _json_agg(field: str) -> dict[str, int]:
            result = qs.values(f"fsm_answers__{field}").annotate(count=Count("id"))
            dist = {}
            for r in result:
                key = r.get(f"fsm_answers__{field}")
                if key:
                    dist[key] = r["count"]
            return dist

        return {
            "vehicle_type": _json_agg("vehicle_type"),
            "payment_method": _json_agg("payment_method"),
            "budget_range": _json_agg("budget_range"),
            "purchase_intent": _json_agg("purchase_intent"),
        }

    def get_urgency_distribution(
        self,
        tenant_id: uuid.UUID,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, int]:
        qs = ChatSession.tenant_objects.for_tenant(tenant_id)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        buckets = {"0-30": 0, "31-60": 0, "61-100": 0, "100+": 0}
        for session in qs.only("urgency_score"):
            score = session.urgency_score
            if score <= 30:
                buckets["0-30"] += 1
            elif score <= 60:
                buckets["31-60"] += 1
            elif score <= 100:
                buckets["61-100"] += 1
            else:
                buckets["100+"] += 1
        return buckets

    def get_time_metrics(
        self, tenant_id: uuid.UUID, date_from: date, date_to: date
    ) -> dict[str, float]:
        qs = ChatSession.tenant_objects.for_tenant(tenant_id).filter(
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        )

        completed = qs.filter(
            status__in=[
                ChatSession.Status.PENDING_ASSIGNMENT,
                ChatSession.Status.CON_VENDEDOR,
            ],
            assigned_at__isnull=False,
        )

        avg_time_to_complete_fsm = completed.aggregate(
            avg=Avg(F("assigned_at") - F("created_at"))
        )["avg"]
        avg_time_to_assign = completed.aggregate(
            avg=Avg(F("assigned_at") - F("created_at"))
        )["avg"]

        with_response = qs.filter(
            status__in=[
                ChatSession.Status.CON_VENDEDOR,
                ChatSession.Status.GANADO,
                ChatSession.Status.PERDIDO,
            ],
            first_response_at__isnull=False,
        )
        avg_time_to_first_response = with_response.aggregate(
            avg=Avg(F("first_response_at") - F("assigned_at"))
        )["avg"]

        closed = qs.filter(
            status__in=[
                ChatSession.Status.GANADO,
                ChatSession.Status.PERDIDO,
            ],
            closed_at__isnull=False,
        )
        avg_time_to_close = closed.aggregate(
            avg=Avg(F("closed_at") - F("assigned_at"))
        )["avg"]

        def _to_minutes(td: timedelta | None) -> float:
            if td is None:
                return 0.0
            return round(td.total_seconds() / 60, 2)

        def _to_days(td: timedelta | None) -> float:
            if td is None:
                return 0.0
            return round(td.total_seconds() / 86400, 2)

        return {
            "avg_time_to_complete_fsm": _to_minutes(avg_time_to_complete_fsm),
            "avg_time_to_assign": _to_minutes(avg_time_to_assign),
            "avg_time_to_first_response": _to_minutes(avg_time_to_first_response),
            "avg_time_to_close": _to_days(avg_time_to_close),
        }

    def get_salesperson_performance(
        self, tenant_id: uuid.UUID, date_from: date, date_to: date
    ) -> list[dict[str, Any]]:
        qs = ChatSession.tenant_objects.for_tenant(tenant_id).filter(
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
            salesperson_id__isnull=False,
        )

        salespeople = (
            qs.values("salesperson_id")
            .annotate(
                leads_assigned=Count("id"),
                wins=Count("id", filter=Q(status=ChatSession.Status.GANADO)),
                losses=Count(
                    "id",
                    filter=Q(
                        status__in=[
                            ChatSession.Status.PERDIDO,
                        ]
                    ),
                ),
                avg_first_response=Avg(
                    F("first_response_at") - F("assigned_at"),
                    filter=Q(first_response_at__isnull=False),
                ),
            )
            .order_by("-wins")
        )

        results = []
        for sp in salespeople:
            wins = sp["wins"]
            losses = sp["losses"]
            win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

            results.append(
                {
                    "salesperson_id": str(sp["salesperson_id"]),
                    "leads_assigned": sp["leads_assigned"],
                    "wins": wins,
                    "losses": losses,
                    "win_rate": round(win_rate, 2),
                    "avg_first_response_minutes": (
                        round(sp["avg_first_response"].total_seconds() / 60, 2)
                        if sp["avg_first_response"]
                        else 0.0
                    ),
                }
            )
        return results


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
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        provider_message_id: str,
        direction: str,
        message_type: str,
        body: str,
    ) -> MessageEntity:
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
        self,
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MessageEntity]:
        models = (
            Message.objects.filter(
                session_id=session_id,
                tenant_id=tenant_id,
                is_deleted=False,
            )
            .order_by("created_at")
            .select_related("session")[offset : offset + limit]
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

    def find_by_id(self, tenant_id: uuid.UUID) -> dict[str, Any] | None:
        tenant = (
            Tenant.objects.filter(id=tenant_id)
            .values("id", "nombre_legal", "routing_mode", "is_verified")
            .first()
        )
        if tenant:
            tenant["routing_mode"] = str(tenant["routing_mode"])
        return tenant


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
