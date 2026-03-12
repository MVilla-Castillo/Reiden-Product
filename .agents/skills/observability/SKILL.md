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

## 5. SLI/SLO & Error Budget (CCRM-SAAS)
*   **SLOs definidos para producción:**
    *   Webhook Ingestion: 99.5% de disponibilidad mensual (max ~3.6h downtime/mes). Métrica: `HTTP 200` en `/webhook/`.
    *   FSM Worker: 99% de tareas procesadas exitosamente por Cloud Tasks sin llegar a DLQ.
    *   Dashboard API: p95 latencia < 500ms para listado de sesiones activas.
*   **Error Budget:** Si el error budget del Webhook se consume más del 50% en una semana, se activa congelación de despliegues hasta identificar la causa raíz.
*   **Healthchecks obligatorios:** Implementar `/health/liveness` (responde 200 si Django arrancó) y `/health/readiness` (verifica conexión real a PostgreSQL). Cloud Run los usa para enrutar tráfico y escalar.

## 6. Alert Routing (GCP Cloud Logging + Sentry)
*   **P1 – Alerta Crítica (respuesta inmediata):** Disparar cuando tasa de errores HTTP 5xx en el Webhook supere el 1% en ventana de 5 minutos, o cuando Cloud Tasks reporte más de 10 tareas en DLQ en 15 minutos.
*   **P2 – Alerta de Degradación:** Disparar cuando latencia p95 del Dashboard API supere 800ms sostenido por 10 minutos.
*   **Prohibido "Log Noise":** No loguear eventos de bajo nivel (ej. cada request HTTP exitoso) en producción. Solo loguear Warnings, Errors y eventos de negocio importantes (transiciones FSM, asignaciones de vendedor). Costo de GCP Logging es proporcional al volumen.
