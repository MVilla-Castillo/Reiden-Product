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
