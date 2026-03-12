---
name: High Concurrency & SRE
description: Reglas de Site Reliability Engineering (SRE) enfocadas a defender la Base de Datos y la red de saturación y cuellos de botella (Deadlocks).
---

# ⚡ High Concurrency & SRE (CCRM-SAAS)

Esta skill está enfocada a programar de forma defensiva para que el sistema soporte picos de tráfico sin crashear. Aplica esto al código de Ingesta (Webhooks) y Dashboards.

## 1. Transacciones Relámpago (Micro-Transactions)
*   **La red no entra en la DB:** Nunca hagas llamadas HTTP (ej. llamar a la API de Twilio) dentro de un bloque `transaction.atomic()`. 
*   Si la red de Twilio demora 3 segundos, mantendrás bloqueada la base de datos por 3 segundos, causando *Connection Pool Exhaustion*. Las transacciones ACID en PostgreSQL deben durar menos de 10 milisegundos.
*   **Orden correcto:** Abre transacción -> Guarda los datos -> Cierra transacción -> Llama a Twilio/Cloud Tasks asíncronamente.

## 2. Control de Concurrencia (Idempotencia)
*   Usa siempre `update_or_create` u operaciones atómicas (`INSERT ... ON CONFLICT`) en PostgreSQL usando el ID que provee el tercero (ej. el Message-ID de Twilio) como `unique_key`.
*   Esto garantiza que si Twilio reintenta enviar el mismo Webhook 5 veces al mismo tiempo, la DB lo rechace a nivel de motor y Django no cree registros duplicados.

## 3. El Asesino N+1
*   **Dashboard Queries:** Prohibido retornar listas (`Django Rest Framework` u ORM JSON) que hagan una query por fila.
*   Usa siempre `select_related()` (Foreign Keys) o `prefetch_related()` (Many-to-Many). El dashboard de vendedores que carga 50 chats concurrentes debe generar máximo **1 o 2 queries SQL** en total.

## 4. Programación Defensiva (Fallas Externas)
*   Asume que la API de Twilio (o Microsoft Entra ID) se va a caer o demorar.
*   Siempre, sin excepción, aplica un argumento de `timeout=5.0` (o menor) a cualquier petición externa HTTP. Si falla, delega a GCP Cloud Tasks para reintento automático (Dead Letter Queue).

## 5. Connection Management (PostgreSQL)
*   **`CONN_MAX_AGE`:** Configura `CONN_MAX_AGE` en `settings.py` (recomendado: `60` segundos) para reutilizar conexiones de BD entre requests y evitar el overhead de establecer nueva conexión TCP en cada petición en Cloud Run.
*   **Sin conexiones dentro de loops:** Prohibido ejecutar queries dentro de bucles Python. Si necesitas procesar N registros, usa `queryset.iterator()` para streaming eficiente o una sola query con `IN`.
*   **Cloud SQL Auth Proxy:** En producción (Cloud Run), la conexión a PostgreSQL pasa obligatoriamente por Cloud SQL Auth Proxy. Prohibido exponer el puerto de PostgreSQL directamente. Esto gestiona TLS y autenticación IAM sin credenciales en código.

## 6. Row-Level Locking para FSM (select_for_update)
*   **Patrón obligatorio para transiciones FSM:** Toda actualización al campo `status` o `fsm_answers` de `ChatSession` DEBE seguir este patrón exacto dentro de `transaction.atomic()`:
    ```python
    with transaction.atomic():
        session = ChatSession.objects.select_for_update().get(id=session_id)
        # ... lógica de transición ...
        session.save()
    ```
*   **`select_for_update(nowait=False)`:** El parámetro por defecto `nowait=False` hace que la transacción espere a que se libere el lock. Esto es correcto para nuestro caso porque el volumen de mensajes concurrentes del mismo Lead es bajo. Si en el futuro se detecta contención, evaluar `skip_locked=True` para procesamiento en paralelo.
*   **`UniqueConstraint` como última línea de defensa:** El constraint parcial en `ChatSession` garantiza a nivel de base de datos (no solo aplicación) que un Lead sólo tenga una sesión activa. Es el seguro para el Thundering Herd en Cloud Run escalado a cero.
