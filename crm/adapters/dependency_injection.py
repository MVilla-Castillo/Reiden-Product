"""
crm/adapters/dependency_injection.py — Contenedor simple de dependencias.

Resuelve las implementaciones concretas de los ports según el entorno:
- DEBUG=True:  HttpDispatchQueue para cola de tareas (fallback local).
- DEBUG=False: GcpCloudTasksQueue para cola de tareas (producción).

El MessageProvider siempre es TwilioMessageProvider en prod;
en tests se inyecta InMemoryMessageProvider vía los setters.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings

from crm.adapters.database.repositories import (
    DjangoAuditLogger,
    DjangoLeadRepository,
    DjangoMessageRepository,
    DjangoSessionRepository,
    DjangoTenantRepository,
    DjangoUserRepository,
)
from crm.adapters.messaging.twilio_adapter import TwilioMessageProvider
from crm.adapters.push import NoOpPushAdapter
from crm.adapters.task_queue.gcp_tasks_adapter import (
    GcpCloudTasksQueue,
    HttpDispatchQueue,
)
from crm.application.use_cases.assign_lead import AssignLeadUseCase
from crm.application.use_cases.change_session_status import ChangeSessionStatusUseCase
from crm.application.use_cases.get_session_messages import GetSessionMessagesUseCase
from crm.application.use_cases.process_message import ProcessMessageUseCase
from crm.application.use_cases.send_outbound_message import SendOutboundMessageUseCase
from crm.domain.ports import (
    AuditLogger,
    LeadRepository,
    MessageProvider,
    MessageRepository,
    PushAdapter,
    SessionRepository,
    TaskQueue,
    TenantRepository,
    UserRepository,
)


class DIContainer:
    """
    Contenedor de dependencias singleton.
    Resuelve adapters concretos según configuración.
    """

    _instance: DIContainer | None = None
    _tenant_repo: TenantRepository | None = None
    _user_repo: UserRepository | None = None
    _lead_repo: LeadRepository | None = None
    _session_repo: SessionRepository | None = None
    _message_repo: MessageRepository | None = None
    _message_provider: MessageProvider | None = None
    _audit_logger: AuditLogger | None = None
    _task_queue: TaskQueue | None = None
    _use_case: ProcessMessageUseCase | None = None
    _get_session_messages_use_case: GetSessionMessagesUseCase | None = None
    _send_outbound_message_use_case: SendOutboundMessageUseCase | None = None
    _assign_lead_use_case: AssignLeadUseCase | None = None
    _change_session_status_use_case: ChangeSessionStatusUseCase | None = None
    _push_adapter: PushAdapter | None = None

    @classmethod
    def instance(cls) -> DIContainer:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Limpia el singleton. Útil para tests."""
        cls._instance = None

    @property
    def tenant_repo(self) -> TenantRepository:
        if self._tenant_repo is None:
            self._tenant_repo = DjangoTenantRepository()
        return self._tenant_repo

    @property
    def user_repo(self) -> UserRepository:
        if self._user_repo is None:
            self._user_repo = DjangoUserRepository()
        return self._user_repo

    @property
    def lead_repo(self) -> LeadRepository:
        if self._lead_repo is None:
            self._lead_repo = DjangoLeadRepository()
        return self._lead_repo

    @property
    def session_repo(self) -> SessionRepository:
        if self._session_repo is None:
            self._session_repo = DjangoSessionRepository()
        return self._session_repo

    @property
    def message_repo(self) -> MessageRepository:
        if self._message_repo is None:
            self._message_repo = DjangoMessageRepository()
        return self._message_repo

    @property
    def message_provider(self) -> MessageProvider:
        if self._message_provider is None:
            self._message_provider = TwilioMessageProvider()
        return self._message_provider

    @property
    def audit_logger(self) -> AuditLogger:
        if self._audit_logger is None:
            self._audit_logger = DjangoAuditLogger()
        return self._audit_logger

    @property
    def task_queue(self) -> TaskQueue:
        if self._task_queue is None:
            if settings.DEBUG:
                self._task_queue = HttpDispatchQueue()
            else:
                self._task_queue = GcpCloudTasksQueue()
        return self._task_queue

    @property
    def process_message_use_case(self) -> ProcessMessageUseCase:
        if self._use_case is None:
            content_sids: dict[str, str] = getattr(settings, "TWILIO_CONTENT_SIDS", {})
            self._use_case = ProcessMessageUseCase(
                lead_repo=self.lead_repo,
                session_repo=self.session_repo,
                message_repo=self.message_repo,
                message_provider=self.message_provider,
                audit_logger=self.audit_logger,
                tenant_repo=self.tenant_repo,
                content_sids=content_sids,
            )
        return self._use_case

    def set_tenant_repo(self, repo: TenantRepository) -> None:
        self._tenant_repo = repo

    def set_user_repo(self, repo: UserRepository) -> None:
        self._user_repo = repo

    def set_lead_repo(self, repo: LeadRepository) -> None:
        self._lead_repo = repo

    def set_session_repo(self, repo: SessionRepository) -> None:
        self._session_repo = repo

    def set_message_repo(self, repo: MessageRepository) -> None:
        self._message_repo = repo

    def set_message_provider(self, provider: MessageProvider) -> None:
        self._message_provider = provider

    def set_audit_logger(self, logger: AuditLogger) -> None:
        self._audit_logger = logger

    def set_task_queue(self, queue: TaskQueue) -> None:
        self._task_queue = queue

    @property
    def get_session_messages_use_case(self) -> GetSessionMessagesUseCase:
        if self._get_session_messages_use_case is None:
            self._get_session_messages_use_case = GetSessionMessagesUseCase(
                session_repo=self.session_repo,
                message_repo=self.message_repo,
            )
        return self._get_session_messages_use_case

    @property
    def send_outbound_message_use_case(self) -> SendOutboundMessageUseCase:
        if self._send_outbound_message_use_case is None:
            tenant_phone = self._get_tenant_phone_number_from_settings()
            self._send_outbound_message_use_case = SendOutboundMessageUseCase(
                session_repo=self.session_repo,
                message_repo=self.message_repo,
                lead_repo=self.lead_repo,
                message_provider=self.message_provider,
                tenant_phone_number_id=tenant_phone,
                audit_logger=self.audit_logger,
            )
        return self._send_outbound_message_use_case

    @property
    def assign_lead_use_case(self) -> AssignLeadUseCase:
        if self._assign_lead_use_case is None:
            self._assign_lead_use_case = AssignLeadUseCase(
                session_repo=self.session_repo,
                user_repo=self.user_repo,
                tenant_repo=self.tenant_repo,
                audit_logger=self.audit_logger,
            )
        return self._assign_lead_use_case

    @property
    def change_session_status_use_case(self) -> ChangeSessionStatusUseCase:
        if self._change_session_status_use_case is None:
            self._change_session_status_use_case = ChangeSessionStatusUseCase(
                session_repo=self.session_repo,
                audit_logger=self.audit_logger,
            )
        return self._change_session_status_use_case

    @property
    def push_adapter(self) -> PushAdapter:
        if self._push_adapter is None:
            self._push_adapter = NoOpPushAdapter()
        return self._push_adapter

    def set_push_adapter(self, adapter: PushAdapter) -> None:
        self._push_adapter = adapter

    def _get_tenant_phone_number_from_settings(self) -> str:
        """
        Obtiene el phone_number_id desde settings, no desde la DB.
        En producción se inyecta vía TENANT_PHONE_NUMBER_ID env var.
        """
        return getattr(settings, "TENANT_PHONE_NUMBER_ID", "")


def get_use_case() -> ProcessMessageUseCase:
    """Función helper para obtener el use case configurado."""
    return DIContainer.instance().process_message_use_case


def get_task_queue() -> TaskQueue:
    """Función helper para obtener la cola de tareas configurada."""
    return DIContainer.instance().task_queue
