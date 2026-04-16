"""
crm/adapters/task_queue/railway_task_queue.py — Railway-compatible Task Queue Adapter.

Dos implementaciones:
- RailwayTaskQueue: Producción, hace POST HTTP directo al worker.
- HttpDispatchQueue: Fallback legacy para desarrollo local.

Railway usa worker processes separados que reciben HTTP requests.
"""

from __future__ import annotations

import logging
import uuid

import requests
from django.conf import settings

from core.log_utils import trace_id_var
from crm.domain.ports import EnqueueRequest, EnqueueResult, TaskQueue

logger = logging.getLogger(__name__)


class TaskQueueError(Exception):
    """Error de dominio: fallo al encolar una tarea en la cola de mensajes."""

    def __init__(self, message: str, underlying_error: Exception | None = None) -> None:
        super().__init__(message)
        self.underlying_error = underlying_error


class RailwayTaskQueue(TaskQueue):
    """
    Adapter de producción para Railway.
    Usa HTTP dispatch al worker process separado.
    """

    def enqueue(self, request: EnqueueRequest) -> EnqueueResult:
        worker_url: str = f"{settings.WORKER_BASE_URL}/api/workers/process-message/"
        internal_secret: str = getattr(settings, "CLOUD_TASKS_INTERNAL_SECRET", "")

        task_id = f"railway-task-{uuid.uuid4()}"
        trace_id = trace_id_var.get() or str(uuid.uuid4())

        logger.info(
            "Railway: Encolando tarea para worker.",
            extra={
                "component_name": "railway_task_queue",
                "task_id": task_id,
                "worker_url": worker_url,
                "message_sid": request.payload.get("MessageSid", ""),
            },
        )

        try:
            response = requests.post(
                worker_url,
                json=request.payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Secret": internal_secret,
                    "X-Trace-ID": trace_id,
                    "X-Railway-Task-ID": task_id,
                },
                timeout=30,
            )
        except requests.ConnectionError as exc:
            logger.error(
                "Railway: No se pudo conectar al worker.",
                extra={
                    "component_name": "railway_task_queue",
                    "worker_url": worker_url,
                    "error": str(exc),
                },
            )
            raise TaskQueueError(
                message="No se pudo conectar al worker",
                underlying_error=exc,
            ) from exc
        except requests.Timeout as exc:
            logger.error(
                "Railway: Timeout al conectar al worker.",
                extra={
                    "component_name": "railway_task_queue",
                    "worker_url": worker_url,
                    "error": str(exc),
                },
            )
            raise TaskQueueError(
                message="Timeout al conectar al worker",
                underlying_error=exc,
            ) from exc

        if response.status_code >= 500:
            logger.error(
                f"Railway: Worker respondió con error 5xx: {response.text}",
                extra={
                    "component_name": "railway_task_queue",
                    "task_id": task_id,
                    "status_code": response.status_code,
                },
            )
            raise TaskQueueError(
                message=f"Worker retornó {response.status_code} - {response.text}",
            )

        logger.info(
            "Railway: Tarea procesada exitosamente.",
            extra={
                "component_name": "railway_task_queue",
                "task_id": task_id,
                "status_code": response.status_code,
            },
        )
        return EnqueueResult(task_id=task_id, success=True)


class HttpDispatchQueue(TaskQueue):
    """
    Fallback legacy para desarrollo local.
    Mantenido por compatibilidad con tests existentes.
    """

    def enqueue(self, request: EnqueueRequest) -> EnqueueResult:
        worker_url: str = f"{settings.WORKER_BASE_URL}/api/workers/process-message/"
        internal_secret: str = getattr(settings, "CLOUD_TASKS_INTERNAL_SECRET", "")

        task_id = f"local-task-{uuid.uuid4()}"
        trace_id = str(uuid.uuid4())

        logger.info(
            "MODO LOCAL: Despachando payload al worker vía HTTP.",
            extra={
                "component_name": "http_dispatch_queue",
                "task_id": task_id,
                "worker_url": worker_url,
                "message_sid": request.payload.get("MessageSid", ""),
            },
        )

        try:
            response = requests.post(
                worker_url,
                json=request.payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Secret": internal_secret,
                    "X-Trace-ID": trace_id,
                    "X-Local-Task-ID": task_id,
                },
                timeout=30,
            )
        except requests.ConnectionError as exc:
            logger.error(
                "MODO LOCAL: No se pudo conectar al worker.",
                extra={
                    "component_name": "http_dispatch_queue",
                    "worker_url": worker_url,
                    "error": str(exc),
                },
            )
            raise TaskQueueError(
                message="No se pudo conectar al worker local",
                underlying_error=exc,
            ) from exc

        if response.status_code >= 500:
            logger.error(
                f"MODO LOCAL: Worker respondió con error 5xx: {response.text}",
                extra={
                    "component_name": "http_dispatch_queue",
                    "task_id": task_id,
                    "status_code": response.status_code,
                },
            )
            raise TaskQueueError(
                message=f"Worker local retornó {response.status_code} - {response.text}",
            )

        logger.info(
            "MODO LOCAL: Worker procesó el payload exitosamente.",
            extra={
                "component_name": "http_dispatch_queue",
                "task_id": task_id,
                "status_code": response.status_code,
            },
        )
        return EnqueueResult(task_id=task_id, success=True)
