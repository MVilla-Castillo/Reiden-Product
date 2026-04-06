"""
crm/adapters/push/__init__.py — Adapter stub para notificaciones push.

Stub permanente: El polling del frontend cumple la función de notificación.
FCM fue removido del stack. No se usarán notificaciones push en el sistema.
"""

from __future__ import annotations

import logging
from uuid import UUID

from crm.domain.ports import PushAdapter

logger = logging.getLogger(__name__)


class NoOpPushAdapter(PushAdapter):
    """
    Adapter no-op para notificaciones push.
    El polling del frontend cumple esta función.
    """

    def send_assignment_notification(
        self,
        user_id: UUID,
        session_id: UUID,
        tenant_id: UUID,
        lead_id: UUID,
    ) -> bool:
        logger.info(
            "Push: Notificación de asignación omitida. Polling del frontend.",
            extra={
                "component_name": "push_adapter",
                "user_id": str(user_id),
                "session_id": str(session_id),
            },
        )
        return False

    def send_ttl_warning(
        self,
        user_id: UUID,
        session_id: UUID,
        tenant_id: UUID,
        lead_id: UUID,
        hours_remaining: int,
    ) -> bool:
        logger.info(
            "Push: Alerta TTL omitida. Polling del frontend.",
            extra={
                "component_name": "push_adapter",
                "user_id": str(user_id),
                "session_id": str(session_id),
                "hours_remaining": hours_remaining,
            },
        )
        return False
