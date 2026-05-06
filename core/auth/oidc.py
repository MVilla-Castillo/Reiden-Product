import logging
from typing import Any, Callable

import jwt
from jwt import PyJWKClient
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse, JsonResponse

from core.log_utils import tenant_id_var
from core.rate_limit import check_rate_limit

try:
    import sentry_sdk
except ImportError:  # pragma: no cover
    sentry_sdk = None

logger = logging.getLogger(__name__)
User = get_user_model()


def _get_client_ip(request: HttpRequest) -> str:
    """Extrae la IP del cliente respetando X-Forwarded-For (proxy/Cloud Run)."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


class OIDCStatelessMiddleware:
    """
    Middleware SRE-grade para validación JWT con Supabase Auth.
    - Stateless: No toca DB para validar sesión activa, solo firma criptográfica.
    - ES256: Validación con clave pública del JWKS de Supabase.
    - Single-Issuer (Supabase): `_is_valid_issuer` acepta únicamente
      `f"{settings.SUPABASE_URL}/auth/v1"`. Para soportar múltiples
      proveedores en el futuro, hacer la lista configurable vía
      `env.list("OIDC_VALID_ISSUERS", default=[...])`.
    - Multi-Tenant a nivel de aplicación: tras validar el JWT, inyecta
      `request.tenant` desde el `AppUser.tenant` asociado al `oidc_sub`.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # 1. Ignorar rutas públicas (healthchecks, webhooks de Twilio y workers internos)
        # SRE Grade: Bypass robusto para endpoints operativos
        PUBLIC_PATH_PREFIXES = (
            "/admin/",
            "/health/",
            "/api/webhooks/twilio/",
            "/api/workers/process-message/",
            "/api/schedulers/",  # Cloud Scheduler usa X-Internal-Secret
        )
        if any(request.path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES):
            return self.get_response(request)

        # SSE ticket validation: Endpoints SSE no pueden enviar Authorization header.
        # El ticket es un UUID de un solo uso emitido por sse_ticket_view tras validar JWT completo.
        if request.path.startswith("/api/sse/"):
            ticket = request.GET.get("ticket")
            if ticket:
                from django.core.cache import cache

                ticket_data = cache.get(f"sse_ticket_{ticket}")
                if ticket_data:
                    cache.delete(f"sse_ticket_{ticket}")
                    try:
                        user = User.objects.select_related("tenant").get(
                            oidc_sub=ticket_data["sub"],
                            oidc_issuer=ticket_data["issuer"],
                            is_active=True,
                        )
                    except User.DoesNotExist:
                        return JsonResponse(
                            {
                                "error": "Unauthorized",
                                "detail": "Usuario del ticket no encontrado",
                            },
                            status=401,
                        )
                    if not user.tenant:
                        return JsonResponse(
                            {
                                "error": "Unauthorized",
                                "detail": "Usuario sin tenant asignado",
                            },
                            status=401,
                        )
                    request.user = user
                    request.tenant = user.tenant
                    tenant_id_var.set(str(user.tenant.id))
                    return self.get_response(request)
                logger.info(
                    "SSE ticket no encontrado o expirado: %s... (path=%s)",
                    ticket[:8],
                    request.path,
                )
                return JsonResponse(
                    {
                        "error": "Unauthorized",
                        "detail": "Ticket SSE inválido o expirado",
                    },
                    status=401,
                )

        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            logger.info(f"OIDC: Unauthorized access attempt to {request.path}")
            return self._unauthorized("Token no proveído o formato inválido")

        token_parts = auth_header.split(" ", 1)
        if len(token_parts) != 2 or not token_parts[1]:
            logger.info(
                f"OIDC: Token vacío en Authorization header para {request.path}"
            )
            return self._unauthorized("Token no proveído o formato inválido")

        token = token_parts[1]

        try:
            header = jwt.get_unverified_header(token)
            alg = header.get("alg", "ES256")

            unverified_payload = jwt.decode(
                token, options={"verify_signature": False}, algorithms=[alg]
            )
            issuer = unverified_payload.get("iss")

            if not issuer:
                return self._unauthorized("Token malformado: iss faltante")

            if not self._is_valid_issuer(issuer):
                return self._unauthorized(f"Issuer no soportado: {issuer}")

            signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            decoded_token = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256"],
                audience="authenticated",
                leeway=10,
                options={"verify_exp": True, "verify_aud": True, "verify_iss": True},
            )

            # 6. Inyección de Identidad al Request
            request.oidc_payload = decoded_token
            # Buscar o inyectar usuario (Idealmente cacheado o mediante lazy loading)
            user, tenant = self._resolve_user_and_tenant(decoded_token, issuer)
            if not user:
                return self._unauthorized(
                    "Usuario asociado al Token denegado o inactivo"
                )

            request.user = user
            if not tenant:
                return self._unauthorized("Usuario sin tenant asignado")
            request.tenant = tenant
            tenant_id_var.set(str(tenant.id))

        except jwt.ExpiredSignatureError:
            if not self._allow_auth_attempt(request):
                return self._too_many_attempts()
            return self._unauthorized("Token expirado")
        except jwt.InvalidTokenError:
            logger.warning("JWT inválido")
            if not self._allow_auth_attempt(request):
                return self._too_many_attempts()
            return self._unauthorized("Token inválido")
        except (AttributeError, TypeError):
            logger.exception("OIDC: Error de atributo/tipo en middleware")
            return self._unauthorized("Token malformado")
        except Exception:
            if sentry_sdk is not None:
                sentry_sdk.set_tag("oidc_middleware_error", "true")
            logger.exception(
                "OIDC: Error inesperado en Middleware (revisar stacktrace)"
            )
            if settings.DEBUG:
                raise
            return JsonResponse(
                {"error": "Internal Server Error", "detail": "Unexpected error"},
                status=500,
            )

        return self.get_response(request)

    def _unauthorized(self, message: str) -> JsonResponse:
        return JsonResponse({"error": "Unauthorized", "detail": message}, status=401)

    def _too_many_attempts(self) -> JsonResponse:
        return JsonResponse(
            {
                "error": "Too Many Requests",
                "detail": "Demasiados intentos de autenticación.",
            },
            status=429,
        )

    def _allow_auth_attempt(self, request: HttpRequest) -> bool:
        """Rate limit per-IP en intentos de auth fallidos (token presente pero inválido).

        Devuelve True si la petición está dentro del límite, False si lo excede.
        Reusa core.rate_limit.check_rate_limit (in-memory; aceptable single-replica).
        """
        ip = _get_client_ip(request)
        return check_rate_limit(f"oidc:fail:{ip}", max_requests=30, window=60)

    def _is_valid_issuer(self, issuer: str) -> bool:
        expected_issuer = f"{settings.SUPABASE_URL}/auth/v1"
        return issuer == expected_issuer

    def _resolve_user_and_tenant(
        self, payload: dict[str, Any], issuer: str
    ) -> tuple[Any | None, Any | None]:
        """
        Mapea el oidc_sub (Subject) + issuer al AppUser de la base de datos local.
        """
        sub = payload.get("sub")
        if not sub:
            return None, None

        try:
            user = User.objects.select_related("tenant").get(
                oidc_sub=sub, oidc_issuer=issuer, is_active=True
            )
            return user, user.tenant
        except User.DoesNotExist:
            return None, None
