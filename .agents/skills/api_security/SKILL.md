---
name: API Security (Endpoints REST)
description: Hardening de los endpoints REST de CCRM-SAAS. Cubre validación de payloads Twilio, CORS, input validation y protección sin Redis.
---

# 🔐 API Security - Endpoints REST (CCRM-SAAS)

> Esta skill complementa `security_compliance` (que cubre OIDC/JWT). Aquí se cubren los endpoints REST específicos: el Webhook de Twilio y el Dashboard API de Angular.

## 1. Validación de Firma Twilio (Webhook)

El endpoint `/webhook/` es público (no requiere JWT) pero DEBE validar que el request proviene de Twilio:

```python
from twilio.request_validator import RequestValidator
from django.conf import settings
from django.http import HttpResponseForbidden

def validate_twilio_signature(request) -> bool:
    """Valida que el webhook proviene realmente de Twilio (HMAC-SHA1)."""
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    url = request.build_absolute_uri()
    signature = request.headers.get('X-Twilio-Signature', '')
    return validator.validate(url, request.POST, signature)

# En la vista:
def webhook_view(request):
    if not validate_twilio_signature(request):
        return HttpResponseForbidden("Invalid signature")
    # ... procesar
```

## 2. Input Validation Defensiva (Payloads Twilio)

*   **Prohibido `KeyError`:** El payload de Twilio puede cambiar entre versiones de API. Siempre usa `.get()` con defaults.
*   **Nunca asumir campos presentes:** El objeto `referral`, `button_payload` o `list_reply` son opcionales según el tipo de mensaje.
*   **Validar tipos:** Si se espera un `string` de `wa_id`, validar que no exceda 50 caracteres antes de intentar insertar en BD.

```python
# ✅ Correcto: defensivo y sin KeyError
wa_id = payload.get('From', '').replace('whatsapp:', '')[:50]
message_text = payload.get('Body', '') or payload.get('ButtonText', '')

# ❌ Incorrecto: falla si 'referral' no existe
vehicle_type = payload['referral']['headline']
```

## 3. CORS (Dashboard Angular)

*   Solo permitir el dominio de Firebase Hosting de la app Angular. **Prohibido `CORS_ALLOW_ALL_ORIGINS = True`**.
*   Configuración en `settings.py`:
    ```python
    CORS_ALLOWED_ORIGINS = [
        "https://tu-app.web.app",    # Firebase Hosting
        "http://localhost:4200",      # Local Angular
    ]
    CORS_ALLOW_CREDENTIALS = True
    ```

## 4. Rate Limiting (Cloud Tasks como Buffer Natural)

No se necesita Redis ni Cloud Armor a este volumen de tráfico:
*   **Cloud Tasks es el rate limiter:** El Webhook recibe el payload de Twilio, lo encola en Cloud Tasks y responde `200 OK` en < 100ms. Si Twilio envía en ráfaga, las tareas se procesan en orden sin saturar la BD.
*   **Timeout obligatorio en vistas:** Todo `view` debe completar su lógica en < 10s. Las llamadas externas (Twilio API, JWKS) deben tener `timeout=5.0` explícito.

## 5. Headers de Seguridad HTTP

Agregar en `settings.py` (usando `django-secure`):

```python
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# En Cloud Run, el TLS lo gestiona Google; no forzar redirect aquí.
# SECURE_SSL_REDIRECT = True  # Solo si Django maneja TLS directamente
```

## 6. Sanitización de Errores (No Exponer Internos)

*   **Prohibido exponer stack traces en producción:** El `DEBUG = False` en settings de producción es obligatorio.
*   El endpoint de Webhook responde siempre `{"status": "ok"}` o `{"error": "internal_error"}` sin detalles internos.
*   Los detalles del error van a Sentry/GCP Logging, **no al cliente**.
