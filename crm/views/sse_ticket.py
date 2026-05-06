"""
crm/views/sse_ticket.py — Endpoint de ticket de un solo uso para autenticar SSE.

Flujo:
  1. Frontend hace POST /api/sse/ticket/ con Authorization: Bearer <jwt>
  2. Este endpoint valida la identidad (via middleware OIDC normal) y genera un UUID
  3. Guarda en caché: ticket_<uuid> → {sub, issuer, tenant_id} (TTL 30s)
  4. Devuelve { "ticket": "<uuid>" }
  5. Frontend usa /api/sse/dashboard/?ticket=<uuid> — el JWT nunca va en la URL
"""

import uuid
import logging
from django.core.cache import cache
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

TICKET_TTL = 30  # segundos — tiempo máximo entre obtener el ticket y abrir el SSE


@csrf_exempt
def sse_ticket_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    # El middleware OIDC ya validó la identidad y dejó request.user y request.tenant
    user = getattr(request, "user", None)
    tenant = getattr(request, "tenant", None)

    if not user or not user.is_authenticated or not tenant:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    ticket = str(uuid.uuid4())
    cache_key = f"sse_ticket_{ticket}"
    cache.set(
        cache_key,
        {
            "sub": user.oidc_sub,
            "issuer": user.oidc_issuer,
            "tenant_id": str(tenant.id),
        },
        timeout=TICKET_TTL,
    )

    logger.debug("SSE ticket generado para %s (TTL=%ds)", user.email, TICKET_TTL)
    return JsonResponse({"ticket": ticket})
