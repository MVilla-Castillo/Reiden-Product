"""
core/metrics.py — Middleware SRE-grade para emitir métricas RED (Rate, Errors, Duration).

Emite un log estructurado por cada request procesado a un logger dedicado
('metrics.red'), separado de los logs de negocio. Esto permite configurar
handlers independientes, filtros y log-based metrics en GCP/Datadog sin
ruido de logs de aplicación.

Usa el patrón de ruta (request.resolver_match.route) en lugar del path raw
para evitar cardinalización infinita en dashboards de observabilidad.
"""

import time
import logging
from typing import Callable

from django.http import HttpRequest, HttpResponse

from core.log_utils import tenant_id_var

logger = logging.getLogger("metrics.red")


class REDMetricsMiddleware:
    """
    Middleware SRE-grade para emitir métricas RED (Rate, Errors, Duration).

    Rate: agrupando por path_pattern y timestamp en el dashboard.
    Errors: filtrando status_code >= 400.
    Duration: promedio o percentil 95 de duration_ms.
    """

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start_time = time.perf_counter()
        status_code: int = 500

        try:
            response = self.get_response(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000

            if (
                not request.path.startswith("/static/")
                and request.path != "/favicon.ico"
            ):
                path_pattern = self._resolve_path_pattern(request)

                logger.info(
                    "RED Metric",
                    extra={
                        "metric_type": "RED",
                        "http_method": request.method,
                        "path_pattern": path_pattern,
                        "path_raw": request.path,
                        "status_code": status_code,
                        "duration_ms": round(duration_ms, 2),
                        "tenant_id": tenant_id_var.get(),
                        "component_name": "red_metrics_middleware",
                    },
                )

    @staticmethod
    def _resolve_path_pattern(request: HttpRequest) -> str:
        """
        Retorna el patrón de ruta (ej: 'api/webhooks/twilio/') en lugar
        del path raw (ej: 'api/webhooks/twilio/'). Esto evita cardinalización
        infinita cuando hay IDs en la URL (ej: 'api/leads/<uuid>/').

        Si el resolver no tiene información (middleware falló antes de routing),
        retorna el path raw como fallback.
        """
        if request.resolver_match:
            return request.resolver_match.route
        return request.path
