"""
crm/services/cloud_tasks.py

Servicio de encolamiento asíncrono via GCP Cloud Tasks (SKILL: high_concurrency §1).

REGLA SRE: Esta función NO toca la base de datos y NO está dentro de ninguna
transaction.atomic(). Su única responsabilidad es hacer una llamada HTTP a la
API de Cloud Tasks para encolar la tarea de procesamiento.

Orden correcto (anti-deadlock):
  1. Vista valida firma → guarda payload en DB si aplica → CIERRA transacción
  2. DESPUÉS llama a esta función para encolar el trabajo pesado.
"""
import json
import logging
import uuid
from typing import Any

from django.conf import settings
from google.cloud import tasks_v2
from google.cloud.tasks_v2.types import Task

logger = logging.getLogger(__name__)


def enqueue_webhook_payload(payload: dict[str, Any]) -> str:
    """
    Encola el payload del webhook de Twilio en GCP Cloud Tasks.

    Cloud Tasks actúa como buffer de rate-limiting natural: si Twilio dispara
    webhooks en ráfaga, las tareas se procesan en orden sin saturar la DB.

    El worker (`/api/workers/process-message/`) recibirá el payload como JSON
    en el cuerpo del request HTTP que Cloud Tasks le envía.

    Args:
        payload: El dict del payload POST de Twilio (ya validado y limpio).

    Returns:
        El nombre completo de la tarea GCP creada (útil para trazabilidad en logs).

    Raises:
        Exception: Si la API de Cloud Tasks falla (Cloud Tasks tiene reintentos
                   automáticos con DLQ nativo, por lo que esta excepción es atípica).
    """
    project: str = settings.GCP_PROJECT_ID
    location: str = settings.GCP_LOCATION
    queue: str = settings.GCP_QUEUE_NAME
    worker_url: str = f"{settings.WORKER_BASE_URL}/api/workers/process-message/"
    internal_secret: str = getattr(settings, 'CLOUD_TASKS_INTERNAL_SECRET', '')
    service_account_email: str = getattr(settings, 'GCP_OIDC_SERVICE_ACCOUNT_EMAIL', '')

    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(project, location, queue)

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
                "X-Trace-ID": str(uuid.uuid4()),
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
