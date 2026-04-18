"""
core/log_utils.py — Utilidades de Observabilidad y SRE.

Implementa un mecanismo basado en contextvars asincrónico para propagar
el Trace ID y Tenant ID a través de todo el ciclo de vida del Request,
incluyendo llamadas a tareas asíncronas y registros de log.
"""

import logging
import time
import uuid
import contextvars
from typing import Any

from django.http import HttpRequest, HttpResponse

# Context variables for request-scoped data
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default="-"
)
tenant_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "tenant_id", default="-"
)


class TraceIDMiddleware:
    """
    Middleware SRE-grade para trazabilidad.
    Intercepta `X-Trace-ID` (inyectado por GCP o Cloud Tasks) o genera uno nuevo.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Prefer GCP trace header, then explicit custom trace header, then generate new
        trace_id = (
            request.headers.get("X-Cloud-Trace-Context")
            or request.headers.get("X-Trace-ID")
            or str(uuid.uuid4())
        )
        # Limpiar si el X-Cloud-Trace-Context viene con /SPAN_ID
        trace_id = trace_id.split("/")[0]

        # Guardar en contexto thread-safe (async compatible)
        trace_id_token = trace_id_var.set(trace_id)
        tenant_id_token = tenant_id_var.set("-")

        # También lo adjuntamos al request por comodidad de acceso plano
        request.trace_id = trace_id

        try:
            response = self.get_response(request)

            # Si el middleware de OIDC o alguna vista adjuntó un tenant, lo subimos
            if hasattr(request, "tenant") and request.tenant:
                tenant_id_var.set(str(request.tenant.id))

            response["X-Trace-ID"] = trace_id
            return response
        finally:
            trace_id_var.reset(trace_id_token)
            tenant_id_var.reset(tenant_id_token)


class ContextFilter(logging.Filter):
    """
    Filtro de Logging que inyecta `trace_id` y `tenant_id` en cada registro
    para que Python JSON Logger lo capture como campos estructurados indexables
    en Google Cloud Logging.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get()
        record.tenant_id = tenant_id_var.get()
        return True


def mask_pii(wa_id: str) -> str:
    """Enmascara un número de WhatsApp mostrando solo los últimos 4 dígitos."""
    if not wa_id or len(wa_id) < 4:
        return "****"
    return "****" + wa_id[-4:]


_stage_timings: contextvars.ContextVar[dict[str, float]] = contextvars.ContextVar(
    "_stage_timings", default=None
)


def _get_stage_timings() -> dict[str, float]:
    timings = _stage_timings.get()
    if timings is None:
        timings = {}
        _stage_timings.set(timings)
    return timings


def stage_start(stage_name: str) -> None:
    """Registra el inicio de un stage cronometrado. Usar en par con stage_end()."""
    timings = _get_stage_timings()
    timings[stage_name] = time.perf_counter()


def stage_end(
    stage_name: str,
    logger: logging.Logger,
    extra: dict[str, Any] | None = None,
) -> None:
    """
    Emite un log estructurado con la duración del stage iniciado con stage_start().

    Si stage_name no fue iniciado previamente, retorna silenciosamente.
    El campo extra se fusiona con los campos de observabilidad estándar.
    """
    timings = _get_stage_timings()
    start_time = timings.pop(stage_name, None)
    if start_time is None:
        return
    duration_ms = (time.perf_counter() - start_time) * 1000

    log_extra = {
        "metric_type": "STAGE_DURATION",
        "stage": stage_name,
        "duration_ms": round(duration_ms, 2),
        "trace_id": trace_id_var.get(),
        "tenant_id": tenant_id_var.get(),
    }
    if extra:
        log_extra.update(extra)

    logger.info(
        f"Stage: {stage_name}",
        extra=log_extra,
    )
