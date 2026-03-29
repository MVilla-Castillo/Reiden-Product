"""
crm/services/cloud_tasks.py

Servicio de encolamiento asíncrono via GCP Cloud Tasks (SKILL: high_concurrency §1).

REGLA SRE: Esta función NO toca la base de datos y NO está dentro de ninguna
transaction.atomic(). Su única responsabilidad es hacer una llamada HTTP a la
API de Cloud Tasks para encolar la tarea de procesamiento.


Modo LOCAL (DEBUG=True):
  Cuando no hay credenciales de GCP, la función despacha el payload directamente
  al worker Django vía HTTP local, simulando fielmente el comportamiento de
  Cloud Tasks en producción. Si el worker responde con 5xx, se re-lanza la
  excepción para que Twilio también pueda reintentar.
"""
import json
import logging
import uuid
from typing import Any

import requests
from django.conf import settings
from google.cloud import tasks_v2
from google.cloud.tasks_v2.types import Task

from core.log_utils import trace_id_var

logger = logging.getLogger(__name__)


def enqueue_webhook_payload(payload: dict[str, Any]) -> str:
    """
    Encola el payload del webhook de Twilio en GCP Cloud Tasks.

    En producción: Cloud Tasks actúa como buffer de rate-limiting natural — si
    Twilio dispara webhooks en ráfaga, las tareas se procesan en orden sin
    saturar la DB.

    Returns:
        El nombre de la tarea creada (GCP task name o ID local).

    Raises:
        Exception: Si el despacho falla (permite que Twilio/Cloud Tasks reintente).
    """
    project: str = settings.GCP_PROJECT_ID
    location: str = settings.GCP_LOCATION
    queue: str = settings.GCP_QUEUE_NAME
    worker_url: str = f"{settings.WORKER_BASE_URL}/api/workers/process-message/"
    internal_secret: str = getattr(settings, 'CLOUD_TASKS_INTERNAL_SECRET', '')
    service_account_email: str = getattr(settings, 'GCP_OIDC_SERVICE_ACCOUNT_EMAIL', '')

    try:
        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(project, location, queue)
    except Exception as e:
        # SRE Grade: Fallback para desarrollo local sin infraestructura de GCP.
        # En DEBUG, despachamos directamente al worker vía HTTP local para
        # simular fielmente el comportamiento de Cloud Tasks en producción.
        if settings.DEBUG:
            return _dispatch_locally(payload, worker_url, internal_secret)
        raise e

    # El body del request que Cloud Tasks enviará al Worker Django
    body = json.dumps(payload, default=str).encode('utf-8')

    task_config: dict[str, Any] = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": worker_url,
            "headers": {
                "Content-Type": "application/json",
                # Secreto interno para autenticar Cloud Tasks → Django Worker (RNF-03)
                "X-Internal-Secret": internal_secret,
                # Trace ID para correlacionar logs en GCP Cloud Logging
                "X-Trace-ID": trace_id_var.get(),
            },
            "body": body,
        }
    }

    # Si hay una Service Account configurada, usamos OIDC para autenticación adicional
    if service_account_email:
        task_config["http_request"]["oidc_token"] = {
            "service_account_email": service_account_email,
            "audience": worker_url,
        }

    try:
        task: Task = client.create_task(request={"parent": parent, "task": task_config})
        logger.info(
            "Tarea de webhook encolada en Cloud Tasks.",
            extra={
                "component_name": "cloud_tasks_service",
                "task_name": task.name,
                "queue": queue,
            },
        )
        return task.name
    except Exception as e:
        if settings.DEBUG:
            return _dispatch_locally(payload, worker_url, internal_secret)
        raise e


def _dispatch_locally(
    payload: dict[str, Any],
    worker_url: str,
    internal_secret: str,
) -> str:
    """
    Dispatcher local para entorno de desarrollo (DEBUG=True).

    Simula a GCP Cloud Tasks: hace un POST HTTP síncrono al worker Django local
    con el mismo header X-Internal-Secret que usaría Cloud Tasks en producción.

    Regla SRE (AGENTS.md §8): Si el worker responde con 5xx, re-lanzamos la
    excepción para que el webhook retorne 500 a Twilio y Twilio pueda reintentar.
    Esto replica el comportamiento de producción fielmente.

    Returns:
        Un task ID local (UUID) para trazabilidad en logs.
    """
    task_id = f"local-task-{uuid.uuid4()}"
    trace_id = str(uuid.uuid4())

    logger.info(
        "MODO LOCAL: Despachando payload al worker vía HTTP.",
        extra={
            "component_name": "cloud_tasks_service",
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
                "X-Local-Task-ID": task_id,
            },
            timeout=30,
        )
    except requests.ConnectionError as exc:
        # El servidor Django local no está corriendo. Logueamos y re-lanzamos
        # para que el webhook retorne 500 y Twilio pueda reintentar.
        logger.error(
            "MODO LOCAL: No se pudo conectar al worker. ¿Está corriendo el servidor?",
            extra={
                "component_name": "cloud_tasks_service",
                "worker_url": worker_url,
                "error": str(exc),
            },
        )
        raise exc

    if response.status_code >= 500:
        # El worker falló. Re-lanzamos para que Twilio reintente el webhook.
        logger.error(
            "MODO LOCAL: El worker respondió con error 5xx.",
            extra={
                "component_name": "cloud_tasks_service",
                "task_id": task_id,
                "status_code": response.status_code,
                "response_body": response.text[:200],
            },
        )
        raise RuntimeError(
            f"Worker local retornó {response.status_code}: {response.text[:200]}"
        )

    logger.info(
        "MODO LOCAL: Worker procesó el payload exitosamente.",
        extra={
            "component_name": "cloud_tasks_service",
            "task_id": task_id,
            "status_code": response.status_code,
        },
    )
    return task_id
