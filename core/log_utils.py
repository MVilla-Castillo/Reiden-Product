"""
core/log_utils.py — Utilidades de Observabilidad y SRE.

Implementa un mecanismo basado en contextvars asincrónico para propagar
el Trace ID y Tenant ID a través de todo el ciclo de vida del Request,
incluyendo llamadas a tareas asíncronas y registros de log.
"""

import logging
import uuid
import contextvars

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
