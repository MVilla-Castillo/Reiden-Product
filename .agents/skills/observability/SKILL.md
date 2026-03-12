---
name: Observability & Monitoring
description: Reglas para la inyección de logs y métricas de RED (Rate, Errors, Duration) de nivel Plataforma Cloud.
---

# 👁️ Observability & Monitoring (CCRM-SAAS)

Esta skill obliga al agente a generar un rastro auditable (Audit Trail) perfecto en la consola de Google Cloud (Cloud Logging) y Sentry para no depender de hacer SSH o entrar a la base de datos a revisar fallos.

## 1. Traceability con Correlation IDs (`X-Correlation-ID`)
*   Todo log que se imprima durante el procesamiento de un Webhook o un Request del Dashboard **DEBE** incluir un Correlation ID y el `tenant_id`.
*   Esto aplica desde que el mensaje entra a Django (Ingesta) hasta que termina en Cloud Tasks (Ejecución Asíncrona). 

## 2. Structured JSON Logging Exclusivo
*   Prohibido hacer `print('Llegó un webhook de X')`.
*   Toda salida estándar (stdout/stderr) en Producción debe usar un Handler que formatee el log en **JSON estructurado** para que GCP Cloud Logging los parsee como atributos consultables, no como texto plano crudo.

## 3. Manejo Crítico de Excepciones y Stack Trace (Sentry)
*   Atrapa (try/except) las excepciones esperables (ej. Timeout a Twilio) y encolalas para DLQ sin alarmar el Sentry si es un fallo intermitente de la red.
*   Si falla el código de negocio (ej. `fsm_answers` no tiene la llave esperada), deja que Sentry atrape el Exception Global o usa `sentry_sdk.capture_exception()`, asegurándote de adjuntar variables locales sanadas (enmascaradas) para debug póstumo.

## 4. Auditoría de Dominio (AuditLog DB Table)
*   **Toda vez** que la entidad `ChatSession` cambia de `.status` (ej. de `BOT` a `CON_VENDEDOR` o a `GANADO`), un registro paralelo debe insertarse en la tabla `AuditLog`.
*   Captura el `old_value` (JSON previo) y el `new_value` (JSON post-estado) + el `actor_id` (quién lo cambió: Bot o Vendedor). Esto es el motor matemático irrefutable para la facturación de comisiones y gamificación (Win-Rate).

## 5. Healthchecks (Obligatorio para Cloud Run)
*   Implementar dos endpoints que Cloud Run usa para gestionar el ciclo de vida del contenedor:
    *   `GET /health/liveness` → responde `200 OK` si Django arrancó correctamente.
    *   `GET /health/readiness` → verifica conexión real a PostgreSQL (`SELECT 1`). Responde `503` si la BD no está disponible. Sin este endpoint, Cloud Run puede enrutar tráfico a una instancia sin BD.
*   Estos endpoints no requieren autenticación OIDC.

## 6. Alertas Simples (Sentry)
*   Configurar **una sola alerta de Sentry** que notifique por email cuando ocurran 3+ errores HTTP 5xx en menos de 5 minutos. Es suficiente para un equipo pequeño con 1 tenant.
*   **Prohibido "Log Noise":** No loguear cada request HTTP exitoso en producción. Solo loguear: Warnings, Errors y eventos de negocio importantes (transiciones FSM, asignación de vendedor). El costo de GCP Logging es proporcional al volumen.
