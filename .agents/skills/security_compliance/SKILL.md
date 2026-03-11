---
name: Security & Compliance (Data Privacy)
description: Reglas estrictas para el protocolo de identidad (OIDC) y resguardo de la privacidad de los datos empresariales.
---

# 🛡️ Security & Compliance (CCRM-SAAS)

Aplica el rigor de una empresa Fintech/Salud a la autenticación y almacenamiento del CCRM.

## 1. Aislamiento Lógico Imperativo (Multi-Tenancy)
*   **Tenant ID Inyectado:** Cada solicitud que pida ver datos o insertar datos en BD requiere leer el `tenant_id` atado a la identidad del usuario y aplicarlo explícitamente en el Query.
*   Nunca confíes en el ID del recurso aportado por el frontend sin cruzarlo con el Tenant. `ChatSession.objects.get(id=X, tenant_id=current_tenant)`.

## 2. Protocolo Identidad (Microsoft Entra ID / OIDC)
*   **Stateless Puro:** El backend actúa como Validador JWT, no mantiene estado ni cookies de sesión propietarias.
*   En cada petición segura del Angular, Django debe validar criptográficamente el Access Token contra las claves públicas de Microsoft (JWKS).
*   **Claims Obligatorios:** Verifica siempre `iss` (Entra ID), `exp` (no expirado), y extrae el `tid` (Tenant ID de Microsoft) para vincularlo a nuestro Tenant local.

## 3. Manejo de Secretos (Zero-Hardcoding)
*   ¡Jamás escribas una contraseña, Token, API Key o Cadena de conexión dentro de un archivo de código Python (ej. `utils.py` o `settings.py`)!
*   Extrae obligatoriamente vía `os.getenv('TWILIO_AUTH_TOKEN')` o inyección dinámica de `GCP Secret Manager`.

## 4. Data Masking (Data Privacy)
*   Al escribir comandos de logs (ej. `logger.info()`), enmascara todos los números telefónicos (`wa_id`) de los usuarios o campos con PII (Personal Identifiable Information).
*   El único momento donde se ve el campo completo es en la respuesta de red autorizada o ejecutando queries directas en Cloud SQL (donde aplica el Data-at-Rest Encryption).
