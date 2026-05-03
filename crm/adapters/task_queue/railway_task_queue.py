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


def _do_http_dispatch(
    worker_url: str,
    internal_secret: str,
    task_prefix: str,
    component_name: str,
    task_id_header: str,
    payload: dict,
) -> EnqueueResult:
    """Lógica compartida para dispatch HTTP a worker."""
    task_id = f"{task_prefix}-{uuid.uuid4()}"
    trace_id = trace_id_var.get() or str(uuid.uuid4())

    logger.info(
        f"{component_name}: Enviando payload al worker.",
        extra={
            "component_name": component_name,
            "task_id": task_id,
            "worker_url": worker_url,
            "message_sid": payload.get("MessageSid", ""),
        },
    )

    try:
        response = requests.post(
            worker_url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-Internal-Secret": internal_secret,
                "X-Trace-ID": trace_id,
                task_id_header: task_id,
            },
            timeout=30,
        )
    except requests.ConnectionError as exc:
        logger.error(
            f"{component_name}: No se pudo conectar al worker.",
            extra={
                "component_name": component_name,
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
            f"{component_name}: Timeout al conectar al worker.",
            extra={
                "component_name": component_name,
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
            f"{component_name}: Worker respondió con error 5xx: {response.text}",
            extra={
                "component_name": component_name,
                "task_id": task_id,
                "status_code": response.status_code,
            },
        )
        raise TaskQueueError(
            message=f"Worker retornó {response.status_code} - {response.text}",
        )

    logger.info(
        f"{component_name}: Worker procesó exitosamente.",
        extra={
            "component_name": component_name,
            "task_id": task_id,
            "status_code": response.status_code,
        },
    )
    return EnqueueResult(task_id=task_id, success=True)


class RailwayTaskQueue(TaskQueue):
    """
    Adapter de producción para Railway.
    Usa HTTP dispatch al worker process separado.
    """

    def enqueue(self, request: EnqueueRequest) -> EnqueueResult:
        worker_url: str = f"{settings.WORKER_BASE_URL}/api/workers/process-message/"
        internal_secret: str = getattr(settings, "INTERNAL_SECRET", "")

        return _do_http_dispatch(
            worker_url=worker_url,
            internal_secret=internal_secret,
            task_prefix="railway-task",
            component_name="railway_task_queue",
            task_id_header="X-Railway-Task-ID",
            payload=request.payload,
        )


class HttpDispatchQueue(TaskQueue):
    """
    Fallback legacy para desarrollo local.
    Mantenido por compatibilidad con tests existentes.
    """

    def enqueue(self, request: EnqueueRequest) -> EnqueueResult:
        worker_url: str = f"{settings.WORKER_BASE_URL}/api/workers/process-message/"
        internal_secret: str = getattr(settings, "INTERNAL_SECRET", "")

        logger.info(
            "MODO LOCAL: Despachando payload al worker vía HTTP.",
            extra={
                "component_name": "http_dispatch_queue",
                "message_sid": request.payload.get("MessageSid", ""),
            },
        )

        return _do_http_dispatch(
            worker_url=worker_url,
            internal_secret=internal_secret,
            task_prefix="local-task",
            component_name="http_dispatch_queue",
            task_id_header="X-Local-Task-ID",
            payload=request.payload,
        )