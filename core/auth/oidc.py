import logging
import time
from typing import Optional, Dict, Any, Tuple

import jwt
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.core.cache import cache

logger = logging.getLogger(__name__)
User = get_user_model()


class OIDCStatelessMiddleware:
    """
    Middleware SRE-grade para validación JWT Multi-Issuer (Google & Microsoft).
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
            '/health/', 
            '/api/webhooks/twilio/', 
            '/api/workers/process-message/'
        )
        if any(request.path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES):
            return self.get_response(request)

        auth_header = request.headers.get('Authorization')

        # [DEV BYPASS] Permitir acceso al dashboard en desarrollo sin token para pruebas manuales
        if not auth_header and settings.DEBUG and request.path.startswith('/api/dashboard/leads/'):
            from crm.models import Tenant
            tenant = Tenant.objects.first()
            if tenant:
                request.tenant = tenant
                # Inyectamos también un usuario para evitar fallos en vistas que dependan de request.user
                request.user = User.objects.filter(tenant=tenant).first() or User.objects.first()
                # Inyectamos un flag para saber que es bypass
                request.oidc_bypass = True 
                
                from core.log_utils import tenant_id_var
                tenant_id_var.set(str(tenant.id))

                logger.warning(f"OIDC: DEV BYPASS activado para {request.path} usando Tenant {tenant.nombre_legal}")
                return self.get_response(request)

        if not auth_header or not auth_header.startswith('Bearer '):
            logger.info(f"OIDC: Unauthorized access attempt to {request.path}")
            return self._unauthorized('Token no proveído o formato inválido')

        token = auth_header.split(' ')[1]

        try:
            # 2. Extraer Header y Payload sin validar firma todavía
            unverified_header = jwt.get_unverified_header(token)
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            
            issuer = unverified_payload.get('iss')
            kid = unverified_header.get('kid')

            if not issuer or not kid:
                return self._unauthorized('Token malformado: iss o kid faltante')

            # 3. Identificar Proveedor (Google vs Microsoft)
            platform = self._identify_platform(issuer)
            if not platform:
                return self._unauthorized(f'Issuer no soportado: {issuer}')

            # 4. Obtener clave pública (JWKS) con mecanismo de re-fetch
            public_key = self._get_public_key(platform, kid)
            if not public_key:
                # Edge Case 1: Rotación silenciosa de llaves. Forzamos re-fetch.
                logger.warning(f"KID {kid} no encontrado en caché para {platform}. Forzando re-fetch.")
                public_key = self._get_public_key(platform, kid, force_refresh=True)
                
            if not public_key:
                return self._unauthorized('Fallo firma: Llave pública no encontrada tras re-fetch')

            # 5. Validación Criptográfica Fuerte (PyJWT)
            audience = getattr(settings, f'OIDC_{platform.upper()}_AUDIENCE')
            decoded_token = jwt.decode(
                token,
                public_key,
                algorithms=['RS256'],
                audience=audience,
                issuer=issuer,
                options={
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": True,
                }
            )

            # 6. Inyección de Identidad al Request
            request.oidc_payload = decoded_token
            # Buscar o inyectar usuario (Idealmente cacheado o mediante lazy loading)
            user, tenant = self._resolve_user_and_tenant(decoded_token)
            if not user:
                return self._unauthorized('Usuario asociado al Token denegado o inactivo')
            
            request.user = user
            request.tenant = tenant
            
            from core.log_utils import tenant_id_var
            tenant_id_var.set(str(tenant.id))

        except jwt.ExpiredSignatureError:
            return self._unauthorized('Token expirado')
        except jwt.InvalidTokenError as e:
            logger.error(f"JWT Invalido: {str(e)}")
            return self._unauthorized('Token inválido')
        except Exception as e:
            logger.exception("Error catastrófico en Middleware OIDC")
            return JsonResponse({'error': 'Internal Server Error'}, status=500)

        return self.get_response(request)

    def _unauthorized(self, message: str) -> JsonResponse:
        return JsonResponse({'error': 'Unauthorized', 'detail': message}, status=401)

    def _identify_platform(self, issuer: str) -> Optional[str]:
        if issuer == getattr(settings, 'OIDC_MICROSOFT_ISSUER', ''):
            return 'microsoft'
        if issuer in [
            getattr(settings, 'OIDC_GOOGLE_ISSUER', ''),
            'accounts.google.com',
            'https://accounts.google.com'
        ]:
            return 'google'
        return None

    def _get_public_key(self, platform: str, kid: str, force_refresh: bool = False) -> Optional[str]:
        """Obtiene la llave RSA del sistema de caché o hace fetch a la red."""
        cache_key = f"jwks_{platform}"
        jwks = cache.get(cache_key)

        if not jwks or force_refresh:
            jwks_url = getattr(settings, f'OIDC_{platform.upper()}_JWKS_URL')
            try:
                response = requests.get(jwks_url, timeout=5) # SRE Timeout
                response.raise_for_status()
                jwks = response.json()
                # Cached por 24 horas a menos que se fuerce refresco
                cache.set(cache_key, jwks, timeout=86400)
            except requests.RequestException as e:
                logger.error(f"Fallo red al obtener JWKS de {platform}: {e}")
                return None

        # Transformar JWK a objeto llave pública
        for key in jwks.get('keys', []):
            if key.get('kid') == kid:
                try:
                    return jwt.algorithms.RSAAlgorithm.from_jwk(key)
                except Exception as e:
                    logger.error(f"Error parseando JWK a llave RSA: {e}")
                    return None
        return None

    def _resolve_user_and_tenant(self, payload: Dict[str, Any]) -> Tuple[Optional[Any], Optional[Any]]:
        """
        Mapea el oidc_sub (Subject) al AppUser de la base de datos local.
        (En sistemas puramente stateless extremos, esto podría omitirse y fiarse solo del JWT,
        pero requerrimes el AppUser para las ForiegnKeys de ChatSession/AuditLog).
        """
        sub = payload.get('sub') or payload.get('oid') # sub (Google) u oid (Microsoft v2.0)
        if not sub:
             return None, None
             
        try:
            # Query ultra ligera, aprovechando índices y relaciones.
            user = User.objects.select_related('tenant').get(oidc_sub=sub, is_active=True)
            return user, user.tenant
        except User.DoesNotExist:
            return None, None
