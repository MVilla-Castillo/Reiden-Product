import logging
from typing import Any

import jwt
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import JsonResponse

from core.log_utils import tenant_id_var

logger = logging.getLogger(__name__)
User = get_user_model()


class OIDCStatelessMiddleware:
    """
    Middleware SRE-grade para validación JWT con Google Workspace (OIDC).
    - Stateless: No toca DB para validar sesión activa, solo firma criptográfica.
    - Resiliente: Maneja fallos de JWKS con re-fetch dinámico.
    - Multi-Tenant: Inyecta request.tenant asumiendo que el JWT lo provee (o la DB).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
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

        # DEBUG bypass: resuelve tenant+user desde el JWT de Supabase (sin verificar firma).
        # IMPORTANTE: settings.DEBUG DEBE estar False en producción — el OIDC completo toma el control.
        if settings.DEBUG and (
            request.path.startswith("/api/dashboard/")
            or request.path.startswith("/api/sse/")
        ):
            from crm.models import Tenant

            # Extraer el JWT desde Authorization header o query param ?token= (SSE no soporta headers)
            resolved_email = None
            raw_token = None

            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                raw_token = auth_header.split(" ", 1)[1]
            elif request.path.startswith("/api/sse/"):
                # EventSource no puede enviar headers; el frontend pasa el token como ?token=
                raw_token = request.GET.get("token")

            # Para SSE: aceptar ?ticket=<uuid> (token de un solo uso, TTL 30s)
            if not raw_token and request.path.startswith("/api/sse/"):
                ticket = request.GET.get("ticket")
                if ticket:
                    from django.core.cache import cache
                    ticket_data = cache.get(f"sse_ticket_{ticket}")
                    if ticket_data:
                        cache.delete(f"sse_ticket_{ticket}")  # un solo uso
                        resolved_email = ticket_data.get("email")
                    else:
                        logger.warning("OIDC DEBUG: ticket SSE inválido o expirado para %s", request.path)
                        return JsonResponse({"error": "Unauthorized", "detail": "Ticket SSE inválido o expirado"}, status=401)

            if raw_token:
                try:
                    payload = jwt.decode(raw_token, options={"verify_signature": False})
                    resolved_email = payload.get("email") or payload.get("sub")
                except Exception:
                    pass

            if not resolved_email:
                logger.warning("OIDC DEBUG: token ausente o sin email — acceso denegado a %s", request.path)
                return JsonResponse({"error": "Unauthorized", "detail": "Token inválido o sin identidad"}, status=401)

            # Resolver usuario primero — su tenant viene de la DB, no de un orden arbitrario
            try:
                user = User.objects.select_related("tenant").get(
                    email=resolved_email, is_active=True
                )
            except User.DoesNotExist:
                logger.warning("OIDC DEBUG: email '%s' no registrado en el sistema", resolved_email)
                return JsonResponse(
                    {"error": "Forbidden", "detail": f"El correo '{resolved_email}' no tiene acceso a este sistema."},
                    status=403,
                )

            if not user.tenant:
                logger.warning("OIDC DEBUG: usuario '%s' sin tenant asignado", resolved_email)
                return JsonResponse({"error": "Forbidden", "detail": "Usuario sin tenant asignado."}, status=403)

            request.tenant = user.tenant
            request.user = user
            request.oidc_bypass = True
            tenant_id_var.set(str(user.tenant.id))
            logger.debug("OIDC DEBUG bypass: %s → %s (%s)", resolved_email, request.path, user.role)
            return self.get_response(request)

        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            logger.info(f"OIDC: Unauthorized access attempt to {request.path}")
            return self._unauthorized("Token no proveído o formato inválido")

        token_parts = auth_header.split(" ", 1)
        if len(token_parts) != 2 or not token_parts[1]:
            logger.info(f"OIDC: Token vacío en Authorization header para {request.path}")
            return self._unauthorized("Token no proveído o formato inválido")

        token = token_parts[1]

        try:
            # 2. Extraer Header y Payload sin validar firma todavía
            unverified_header = jwt.get_unverified_header(token)
            unverified_payload = jwt.decode(token, options={"verify_signature": False})

            issuer = unverified_payload.get("iss")
            kid = unverified_header.get("kid")

            if not issuer or not kid:
                return self._unauthorized("Token malformado: iss o kid faltante")

            # 3. Validar que el issuer sea Google
            if not self._is_google_issuer(issuer):
                return self._unauthorized(f"Issuer no soportado: {issuer}")

            # 4. Obtener clave pública (JWKS) con mecanismo de re-fetch
            public_key = self._get_public_key(kid)
            if not public_key:
                # Edge Case 1: Rotación silenciosa de llaves. Forzamos re-fetch.
                logger.warning(f"KID {kid} no encontrado en caché. Forzando re-fetch.")
                public_key = self._get_public_key(kid, force_refresh=True)

            if not public_key:
                return self._unauthorized(
                    "Fallo firma: Llave pública no encontrada tras re-fetch"
                )

            # 5. Validación Criptográfica Fuerte (PyJWT)
            decoded_token = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=settings.OIDC_GOOGLE_AUDIENCE,
                issuer=settings.OIDC_GOOGLE_ISSUER,
                leeway=30,
                options={
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )

            # 6. Inyección de Identidad al Request
            request.oidc_payload = decoded_token
            # Buscar o inyectar usuario (Idealmente cacheado o mediante lazy loading)
            user, tenant = self._resolve_user_and_tenant(decoded_token)
            if not user:
                return self._unauthorized(
                    "Usuario asociado al Token denegado o inactivo"
                )

            request.user = user
            request.tenant = tenant
            tenant_id_var.set(str(tenant.id))

        except jwt.ExpiredSignatureError:
            return self._unauthorized("Token expirado")
        except jwt.InvalidTokenError as e:
            logger.error(f"JWT Inválido: {str(e)}")
            return self._unauthorized("Token inválido")
        except requests.RequestException as e:
            logger.error(f"OIDC: Fallo de red al obtener JWKS: {str(e)}")
            return JsonResponse({"error": "Internal Server Error", "detail": "External service unavailable"}, status=500)
        except Exception:
            logger.exception("OIDC: Error inesperado en Middleware (revisar stacktrace)")
            if settings.DEBUG:
                raise
            return JsonResponse({"error": "Internal Server Error", "detail": "Unexpected error"}, status=500)

        return self.get_response(request)

    def _unauthorized(self, message: str) -> JsonResponse:
        return JsonResponse({"error": "Unauthorized", "detail": message}, status=401)

    def _is_google_issuer(self, issuer: str) -> bool:
        return issuer in [
            settings.OIDC_GOOGLE_ISSUER,
            "accounts.google.com",
            "https://accounts.google.com",
        ]

    def _get_public_key(self, kid: str, force_refresh: bool = False) -> str | None:
        """Obtiene la llave RSA del sistema de caché o hace fetch a la red."""
        cache_key = "jwks_google"
        jwks = cache.get(cache_key)

        if not jwks or force_refresh:
            try:
                response = requests.get(settings.OIDC_GOOGLE_JWKS_URL, timeout=5)
                response.raise_for_status()
                jwks = response.json()
                cache.set(cache_key, jwks, timeout=86400)
            except requests.RequestException as e:
                logger.error(f"Fallo red al obtener JWKS de Google: {e}")
                return None

        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                try:
                    return jwt.algorithms.RSAAlgorithm.from_jwk(key)
                except Exception as e:
                    logger.error(f"Error parseando JWK a llave RSA: {e}")
                    return None
        return None

    def _resolve_user_and_tenant(
        self, payload: dict[str, Any]
    ) -> tuple[Any | None, Any | None]:
        """
        Mapea el oidc_sub (Subject) al AppUser de la base de datos local.
        """
        sub = payload.get("sub")
        if not sub:
            return None, None

        try:
            user = User.objects.select_related("tenant").get(
                oidc_sub=sub, is_active=True
            )
            return user, user.tenant
        except User.DoesNotExist:
            return None, None
