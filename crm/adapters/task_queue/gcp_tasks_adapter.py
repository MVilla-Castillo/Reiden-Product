"""
crm/adapters/task_queue/gcp_tasks_adapter.py — Adapters para el port TaskQueue.

Dos implementaciones:
- GcpCloudTasksQueue: Producción, usa SDK de GCP Cloud Tasks.
- HttpDispatchQueue: Fallback local que hace POST HTTP al worker Django.

Excepciones de dominio: los errores crudos de GCP o requests nunca se exponen
al caller. Se traducen a TaskQueueError.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import requests
from django.conf import settings
from google.cloud import tasks_v2
from google.cloud.tasks_v2.types import Task

from core.log_utils import trace_id_var
from crm.domain.ports import EnqueueRequest, EnqueueResult, TaskQueue

logger = logging.getLogger(__name__)


class TaskQueueError(Exception):
    """Error de dominio: fallo al encolar una tarea en la cola de mensajes."""

    def __init__(self, message: str, underlying_error: Exception | None = None) -> None:
        super().__init__(message)
        self.underlying_error = underlying_error


class GcpCloudTasksQueue(TaskQueue):
    """Adapter de producción: encola payloads en GCP Cloud Tasks."""

    _client: tasks_v2.CloudTasksClient | None = None

    @property
    def client(self) -> tasks_v2.CloudTasksClient:
        if self._client is None:
            self._client = tasks_v2.CloudTasksClient()
        return self._client

    def enqueue(self, request: EnqueueRequest) -> EnqueueResult:
        project: str = settings.GCP_PROJECT_ID
        location: str = settings.GCP_LOCATION
        queue: str = settings.GCP_QUEUE_NAME
        worker_url: str = f"{settings.WORKER_BASE_URL}/api/workers/process-message/"
        internal_secret: str = getattr(settings, "CLOUD_TASKS_INTERNAL_SECRET", "")
        service_account_email: str = getattr(
            settings, "GCP_OIDC_SERVICE_ACCOUNT_EMAIL", ""
        )

        try:
            parent = self.client.queue_path(project, location, queue)
        except Exception as exc:
            if settings.DEBUG:
                fallback = HttpDispatchQueue()
                return fallback.enqueue(request)
            raise TaskQueueError(
                message=f"No se pudo inicializar Cloud Tasks: {exc}",
                underlying_error=exc,
            ) from exc

        body = json.dumps(request.payload, default=str).encode("utf-8")

        task_config: dict[str, Any] = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": worker_url,
                "headers": {
                    "Content-Type": "application/json",
                    "X-Internal-Secret": internal_secret,
                    "X-Trace-ID": trace_id_var.get(),
                },
                "body": body,
            }
        }

        if service_account_email:
            task_config["http_request"]["oidc_token"] = {
                "service_account_email": service_account_email,
                "audience": worker_url,
            }

        try:
            task: Task = self.client.create_task(
                request={"parent": parent, "task": task_config}
            )
            logger.info(
                "Tarea encolada en Cloud Tasks.",
                extra={
                    "component_name": "gcp_tasks_adapter",
                    "task_name": task.name,
                    "queue": queue,
                },
            )
            return EnqueueResult(task_id=task.name, success=True)
        except Exception as exc:
            if settings.DEBUG:
                fallback = HttpDispatchQueue()
                return fallback.enqueue(request)
            raise TaskQueueError(
                message=f"Fallo al crear tarea en Cloud Tasks: {exc}",
                underlying_error=exc,
            ) from exc


class HttpDispatchQueue(TaskQueue):
    """
    Fallback local: simula Cloud Tasks haciendo POST HTTP directo al worker.
    Usado en desarrollo (DEBUG=True) y como fallback si el SDK de GCP falla.
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
