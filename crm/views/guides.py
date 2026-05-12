"""crm/views/guides.py — Endpoint de guías interactivas por pestaña y rol."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse

from crm.guides import GUIDES, MANAGER_ONLY_TABS, VALID_TABS
from crm.models import AppUser


_ROLE_TO_KEY = {
    AppUser.Role.ADMIN: "manager",
    AppUser.Role.MANAGER: "manager",
    AppUser.Role.SALESPERSON: "salesperson",
}


def guides_api(request: HttpRequest, tab: str) -> JsonResponse:
    """GET /api/dashboard/guides/<tab>/ → JSON con los pasos del tour para la pestaña.

    - Requiere autenticación (la middleware OIDC ya inyecta request.user).
    - Tabs válidos: dashboard, leads, chat, reports.
    - Dashboard y Reports están restringidos a MANAGER/ADMIN.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    if tab not in VALID_TABS:
        return JsonResponse({"error": f"Tab desconocida: {tab}"}, status=404)

    role_key = _ROLE_TO_KEY.get(user.role)
    if role_key is None:
        return JsonResponse({"error": "Rol de usuario no reconocido."}, status=403)

    if tab in MANAGER_ONLY_TABS and role_key != "manager":
        return JsonResponse({"error": "Acceso restringido a gerentes."}, status=403)

    tab_content = GUIDES.get(tab, {})
    payload = tab_content.get(role_key)
    if payload is None:
        return JsonResponse(
            {"error": f"No hay guía para tab={tab} role={role_key}"}, status=404
        )

    return JsonResponse(
        {
            "tab": tab,
            "role": role_key,
            "title": payload["title"],
            "steps": payload["steps"],
        },
        status=200,
    )
