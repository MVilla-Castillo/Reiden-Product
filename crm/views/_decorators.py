"""crm/views/_decorators.py — Decoradores transversales para vistas del CRM."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from django.http import HttpRequest, HttpResponse, JsonResponse


def require_tenant(
    view_func: Callable[..., HttpResponse],
) -> Callable[..., HttpResponse]:
    """Garantiza que `request.tenant` esté presente; si no, retorna 403 JSON.

    El middleware OIDC normalmente inyecta `request.tenant` cuando la sesión
    es válida; si falta significa que la petición no está autenticada como
    miembro de un tenant y debe ser rechazada antes de tocar la lógica.
    """

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if getattr(request, "tenant", None) is None:
            return JsonResponse({"error": "Tenant no definido."}, status=403)
        return view_func(request, *args, **kwargs)

    return wrapper
