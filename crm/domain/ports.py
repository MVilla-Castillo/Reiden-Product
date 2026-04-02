"""
crm/domain/ports.py — Interfaces (puertos) de Arquitectura Hexagonal.

Define contratos abstractos mediante typing.Protocol.
Cero dependencias externas. Las implementaciones concretas
(adapters) vivirán en crm/adapters/ y serán inyectadas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from crm.domain.entities import LeadEntity, MessageEntity, SessionEntity

__all__ = [
    "SendMessageRequest",
    "SendMessageResult",
    "SignatureValidationRequest",
    "SignatureValidationResult",
    "EnqueueRequest",
    "EnqueueResult",
    "AuditEntry",
    "MessageProvider",
    "TaskQueue",
    "LeadRepository",
    "SessionRepository",
    "MessageRepository",
    "UserRepository",
    "AuditLogger",
    "TenantRepository",
]


# ─────────────────────────────────────────────────────────
# DTOs de entrada/salida para los puertos
# ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SendMessageRequest:
    """DTO para solicitud de envío de mensaje."""

    to_number: str
    from_number: str
    text: str
    interactive_payload: dict[str, Any] | None = None
    content_sid: str | None = None
    content_variables: str | None = None


@dataclass(frozen=True)
class SendMessageResult:
    """DTO para resultado de envío de mensaje."""

    provider_message_id: str | None
    success: bool


@dataclass(frozen=True)
class SignatureValidationRequest:
    """DTO para validación de firma de webhook."""

    url: str
    post_data: dict[str, str]
    signature: str


@dataclass(frozen=True)
class SignatureValidationResult:
    """DTO para resultado de validación de firma."""

    is_valid: bool


@dataclass(frozen=True)
class EnqueueRequest:
    """DTO para encolar una tarea en la cola de mensajes."""

    payload: dict[str, Any]


@dataclass(frozen=True)
class EnqueueResult:
    """DTO para resultado de encolamiento."""

    task_id: str
    success: bool


@dataclass(frozen=True)
class AuditEntry:
    """DTO para registro de auditoría."""

    session_id: UUID
    tenant_id: UUID
    action: str
    old_value: dict[str, Any]
    new_value: dict[str, Any]
    actor_id: UUID | None = None


# ─────────────────────────────────────────────────────────
# Puertos (Protocolos)
# ─────────────────────────────────────────────────────────


class MessageProvider(Protocol):
    """Puerto para proveedores de mensajería (Twilio, Meta WA, etc.)."""

    def send_message(self, request: SendMessageRequest) -> SendMessageResult:
        """Envía un mensaje y retorna el ID del proveedor o None si falla."""
        ...

    def validate_signature(
        self, request: SignatureValidationRequest
    ) -> SignatureValidationResult:
        """Valida la firma criptográfica de un webhook entrante."""
        ...


class TaskQueue(Protocol):
    """Puerto para colas de tareas asíncronas (GCP Cloud Tasks, AWS SQS, etc.)."""

    def enqueue(self, request: EnqueueRequest) -> EnqueueResult:
        """Encola un payload para procesamiento asíncrono."""
        ...


class LeadRepository(Protocol):
    """Puerto para persistencia de Leads."""

    def find_by_wa_id_hash(self, tenant_id: UUID, wa_id_hash: str) -> LeadEntity | None:
        """Busca un Lead por su hash de WhatsApp dentro de un tenant."""
        ...

    def upsert(
        self, tenant_id: UUID, wa_id_hash: str, defaults: dict[str, Any]
    ) -> LeadEntity:
        """Crea o actualiza un Lead por wa_id_hash. Retorna la entidad resultante."""
        ...

    def for_tenant(self, tenant_id: UUID) -> list[LeadEntity]:
        """Retorna todos los Leads activos de un tenant."""
        ...

    def find_wa_id(self, lead_id: UUID, tenant_id: UUID | None = None) -> str | None:
        """Retorna el wa_id decifrado de un Lead por su ID, opcionalmente filtrado por tenant."""
        ...


class SessionRepository(Protocol):
    """Puerto para persistencia de ChatSessions."""

    def find_active(self, tenant_id: UUID, lead_id: UUID) -> SessionEntity | None:
        """Busca la sesión activa más reciente para un Lead en un tenant."""
        ...

    def find_by_id(self, session_id: UUID, tenant_id: UUID) -> SessionEntity | None:
        """Busca una sesión por su ID dentro de un tenant."""
        ...

    def create(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        status: str = "BOT",
    ) -> SessionEntity:
        """Crea una nueva sesión y la retorna."""
        ...

    def save(
        self, session: SessionEntity, update_fields: list[str] | None = None
    ) -> SessionEntity:
        """Persiste los cambios de una sesión existente."""
        ...

    def assign_salesperson(
        self, session_id: UUID, tenant_id: UUID, salesperson_id: UUID | None
    ) -> SessionEntity | None:
        """Asigna o desasigna un vendedor a una sesión. Retorna None si no existe."""
        ...

    def change_status(
        self, session_id: UUID, tenant_id: UUID, new_status: str
    ) -> SessionEntity | None:
        """Cambia el estado de una sesión. Retorna None si no existe."""
        ...

    def get_dashboard_sessions(
        self, tenant_id: UUID, limit: int = 50
    ) -> list[SessionEntity]:
        """Retorna sesiones ordenadas por urgency_score para el dashboard."""
        ...

    def find_active_for_update(
        self, tenant_id: UUID, lead_id: UUID
    ) -> SessionEntity | None:
        """Busca sesión activa con bloqueo de fila (SELECT FOR UPDATE)."""
        ...

    def expire_if_inactive(
        self, tenant_id: UUID, lead_id: UUID, hours: int = 24
    ) -> SessionEntity | None:
        """Marca como ABANDONO_BOT si inactiva >hours. Retorna None si expiró."""
        ...

    def check_session_expired(self, session_id: UUID, hours: int = 24) -> bool:
        """Verifica si una sesión activa ha expirado por inactividad."""
        ...

    def mark_as_abandoned(self, session_id: UUID) -> None:
        """Marca una sesión como ABANDONO_BOT."""
        ...


class MessageRepository(Protocol):
    """Puerto para persistencia de Messages."""

    def exists_by_provider_id(
        self, provider_message_id: str, tenant_id: UUID | None = None
    ) -> bool:
        """Verifica si ya existe un mensaje con este ID de proveedor, opcionalmente filtrado por tenant."""
        ...

    def create(
        self,
        tenant_id: UUID,
        session_id: UUID,
        provider_message_id: str,
        direction: str,
        message_type: str,
        body: str,
    ) -> MessageEntity:
        """Crea un nuevo mensaje y lo retorna."""
        ...

    def find_by_session(self, session_id: UUID, tenant_id: UUID) -> list[MessageEntity]:
        """Retorna todos los mensajes de una sesión ordenados cronológicamente."""
        ...


class UserRepository(Protocol):
    """Puerto para consulta de usuarios."""

    def find_salespeople_by_tenant(self, tenant_id: UUID) -> list[dict[str, Any]]:
        """Retorna vendedores del tenant con conteo de sesiones activas."""
        ...

    def find_by_id_and_tenant(
        self, user_id: UUID, tenant_id: UUID, role: str | None = None
    ) -> dict[str, Any] | None:
        """Busca un usuario por ID dentro de un tenant, opcionalmente filtrando por rol."""
        ...


class AuditLogger(Protocol):
    """Puerto para registro inmutable de eventos de auditoría."""

    def record(self, entry: AuditEntry) -> None:
        """Registra un evento de auditoría. Operación append-only."""
        ...


class TenantRepository(Protocol):
    """Puerto para consulta de Tenants."""

    def find_id_by_phone_number(self, phone_number_id: str) -> UUID | None:
        """Busca el ID de un Tenant por su phone_number_id de WhatsApp."""
        ...
