"""
crm/views/health.py — Endpoints de salud para probes de Cloud Run.
"""

from django.http import HttpRequest, JsonResponse
from django.db import connection
from django.db.utils import OperationalError


def liveness_view(request: HttpRequest) -> JsonResponse:
    """
    GET /health/liveness
    Indica si la aplicación Django está corriendo y respondiendo peticiones HTTP.
    """
    return JsonResponse({"status": "ok"})


def readiness_view(request: HttpRequest) -> JsonResponse:
    """
    GET /health/readiness
    Verifica que la base de datos es accesible.
    Cloud Run no enviará tráfico si esto falla.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except OperationalError:
        return JsonResponse({"status": "unavailable"}, status=503)

    return JsonResponse({"status": "ready"})
