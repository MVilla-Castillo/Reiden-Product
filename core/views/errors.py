import logging

from django.http import JsonResponse

from core.log_utils import tenant_id_var, trace_id_var

logger = logging.getLogger(__name__)


def handler404(request, exception):
    trace_id = trace_id_var.get()
    logger.warning(
        "404 Not Found",
        extra={"path": request.path, "method": request.method, "tenant_id": tenant_id_var.get()},
    )
    return JsonResponse({"error": "Not Found", "trace_id": trace_id}, status=404)


def handler500(request):
    trace_id = trace_id_var.get()
    logger.error(
        "500 Internal Server Error",
        extra={"path": request.path, "tenant_id": tenant_id_var.get()},
    )
    return JsonResponse({"error": "Internal Server Error", "trace_id": trace_id}, status=500)
