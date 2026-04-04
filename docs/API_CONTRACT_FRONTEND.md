# API Contract — Frontend Integration

> Documento para el equipo de Frontend (Angular 18+). Describe los endpoints disponibles, formatos de request/response, y lo que falta por construir.

---

## 1. Endpoints Disponibles

### 1.1 Dashboard de Leads

```
GET /api/dashboard/leads/
```

**Autenticación:** `Authorization: Bearer <JWT>` (Google OIDC)

El JWT debe contener el `sub` de Google previamente registrado en la plataforma. El backend resuelve el `tenant` automáticamente desde el usuario asociado.

#### Request

Headers obligatorios. Query params opcionales para filtrado y paginación.

```http
GET /api/dashboard/leads/?limit=50&date_filter=week&status=BOT&min_urgency=50 HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Query Params opcionales:**

| Param | Tipo | Default | Descripción |
|---|---|---|---|
| `limit` | int | 50 | Máximo de resultados (max 100) |
| `date_filter` | string | — | Filtro rápido: `today`, `week`, `month`, `year`, `all` |
| `date_from` | date (ISO 8601) | — | Fecha inicio personalizada |
| `date_to` | date (ISO 8601) | — | Fecha fin personalizada |
| `status` | string | — | Filtrar por estado: `BOT`, `PENDING_ASSIGNMENT`, `CON_VENDEDOR`, `GANADO`, `PERDIDO`, `ABANDONO_BOT` |
| `vehicle_type` | string | — | `City Car`, `SUV`, `Sedan` |
| `payment_method` | string | — | `Contado`, `Credito`, `Retoma` |
| `budget_range` | string | — | `<6M`, `7-14M`, `>15M` |
| `purchase_intent` | string | — | `HOY`, `ESTA_SEMANA`, `MES_O_MAS` |
| `salesperson_id` | UUID | — | Filtrar por vendedor asignado |
| `min_urgency` | int | — | Urgencia mínima (0-160) |
| `max_urgency` | int | — | Urgencia máxima (0-160) |

#### Response 200 — OK

```json
{
  "leads": [
    {
      "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "lead_phone_hash": "e5f6g7h8-i9j0-1234-klmn-op5678901234",
      "status": "BOT",
      "urgency_score": 160,
      "fsm_step": "VEHICLE_TYPE",
      "vehicle_type": "SUV",
      "payment_method": "Credito",
      "budget_range": "7-14M",
      "purchase_intent": "HOY",
      "salesperson_id": null,
      "assigned_at": null,
      "closed_at": null,
      "created_at": "2026-04-01T10:30:00Z",
      "updated_at": "2026-04-01T10:35:00Z"
    }
  ],
  "count": 1
}
```

Los leads vienen ordenados por `urgency_score` descendente (más urgentes primero). Máximo 50 por request.

#### Response 401 — Unauthorized

Token ausente, expirado o inválido.

```json
{
  "error": "Unauthorized",
  "detail": "Token expirado"
}
```

Posibles valores de `detail`:
- `"Token no proveído o formato inválido"`
- `"Token malformado: iss o kid faltante"`
- `"Issuer no soportado: https://..."`
- `"Fallo firma: Llave pública no encontrada tras re-fetch"`
- `"Token expirado"`
- `"Token inválido"`
- `"Usuario asociado al Token denegado o inactivo"`

#### Response 403 — Forbidden

```json
{
  "error": "Tenant no definido."
}
```

#### Response 405 — Method Not Allowed

```json
{
  "error": "Method Not Allowed"
}
```

---

## 2. Endpoints Implementados (Sprint 6 — Completos)

Todos los endpoints de esta sección están **implementados y funcionales**. Requieren autenticación OIDC (Google JWT).

### 2.1 Detalle de Mensajes de una Sesión

```
GET /api/dashboard/leads/<session_id>/messages/
```

**Autenticación:** `Authorization: Bearer <JWT>`

#### Response 200 — OK

```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "lead_id": "e5f6g7h8-i9j0-1234-klmn-op5678901234",
  "status": "BOT",
  "messages": [
    {
      "message_id": "msg-0001-uuid",
      "direction": "INBOUND",
      "message_type": "TEXT",
      "body": "Quiero info de un auto",
      "created_at": "2026-04-01T10:30:00Z"
    },
    {
      "message_id": "msg-0002-uuid",
      "direction": "OUTBOUND",
      "message_type": "TEXT",
      "body": "¿Qué tipo de auto buscas?",
      "created_at": "2026-04-01T10:30:01Z"
    }
  ]
}
```

Los mensajes vienen ordenados por `created_at` ascendente (más antiguos primero).

#### Response 404 — Sesión no encontrada

```json
{ "error": "Sesión no encontrada" }
```

#### Response 403 — Tenant no definido

```json
{ "error": "Tenant no definido." }
```

---

### 2.2 Enviar Mensaje como Vendedor

```
POST /api/dashboard/leads/<session_id>/messages/send/
```

**Autenticación:** `Authorization: Bearer <JWT>`

La sesión debe estar en estado `CON_VENDEDOR`.

#### Request

```http
POST /api/dashboard/leads/a1b2c3d4-e5f6-7890-abcd-ef1234567890/messages/send/ HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
Content-Type: application/json
```

```json
{
  "body": "Hola, soy Juan de la automotora. ¿En qué puedo ayudarte?"
}
```

#### Response 200 — Mensaje enviado

```json
{
  "message_id": "msg-outbound-uuid",
  "direction": "OUTBOUND",
  "body": "Hola, soy Juan de la automotora. ¿En qué puedo ayudarte?",
  "created_at": "2026-04-01T11:05:00Z",
  "provider_message_sid": "SM-twilio-message-sid"
}
```

El backend envía el mensaje vía Twilio al WhatsApp del lead y lo persiste como `OUTBOUND`.

#### Response 400 — Body inválido

```json
{ "error": "body es requerido y no puede estar vacío" }
```

#### Response 403 — Sesión no en estado CON_VENDEDOR

```json
{ "error": "Solo puedes enviar mensajes en sesiones asignadas (CON_VENDEDOR)" }
```

#### Response 404 — Sesión no encontrada

```json
{ "error": "Sesión no encontrada" }
```

#### Response 500 — Fallo Twilio

```json
{ "error": "Fallo al enviar mensaje por Twilio" }
```

---

### 2.3 Asignar Lead a Vendedor

```
POST /api/dashboard/leads/<session_id>/assign/
```

**Autenticación:** `Authorization: Bearer <JWT>`

#### Request

```http
POST /api/dashboard/leads/a1b2c3d4-e5f6-7890-abcd-ef1234567890/assign/ HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
Content-Type: application/json
```

```json
{
  "salesperson_id": "sp-uuid-here"
}
```

#### Response 200 — Asignación exitosa

```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "CON_VENDEDOR",
  "salesperson_id": "sp-uuid-here",
  "salesperson_name": "Juan Pérez",
  "assigned_at": "2026-04-01T11:00:00Z"
}
```

#### Response 400 — Body inválido

```json
{ "error": "salesperson_id inválido" }
```

#### Response 404 — Sesión o vendedor no encontrado

```json
{ "error": "Vendedor no encontrado en este tenant" }
```

```json
{ "error": "Sesión no encontrada" }
```

---

### 2.4 Reasignar o Desasignar Lead

```
PATCH /api/dashboard/leads/<session_id>/reassign/
```

**Autenticación:** `Authorization: Bearer <JWT>`

#### Request — Reasignar a otro vendedor

```json
{
  "salesperson_id": "sp-uuid-nuevo"
}
```

#### Request — Desasignar (volver a cola de espera)

```json
{
  "salesperson_id": null
}
```

Al desasignar, la sesión vuelve al estado `PENDING_ASSIGNMENT`.

#### Response 200 — Reasignación exitosa

```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "CON_VENDEDOR",
  "salesperson_id": "sp-uuid-nuevo",
  "salesperson_name": "María López",
  "assigned_at": "2026-04-01T14:00:00Z"
}
```

#### Response 200 — Desasignación exitosa

```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "PENDING_ASSIGNMENT",
  "salesperson_id": null,
  "salesperson_name": null,
  "assigned_at": null
}
```

#### Response 400 — Body inválido

```json
{ "error": "salesperson_id es requerido (envía null para desasignar)" }
```

#### Response 404 — Sesión o vendedor no encontrado

```json
{ "error": "Sesión no encontrada" }
```

---

### 2.5 Cambiar Estado de Sesión (GANADO / PERDIDO)

```
PATCH /api/dashboard/leads/<session_id>/status/
```

**Autenticación:** `Authorization: Bearer <JWT>`

#### Request

```http
PATCH /api/dashboard/leads/a1b2c3d4-e5f6-7890-abcd-ef1234567890/status/ HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
Content-Type: application/json
```

```json
{
  "status": "GANADO"
}
```

Valores permitidos para `status`:
- `GANADO` — Cierre exitoso de venta
- `PERDIDO` — No se concretó la venta
- `ABANDONO_BOT` — Descartar lead inactivo

#### Response 200 — Estado actualizado

```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "GANADO",
  "updated_at": "2026-04-01T12:00:00Z"
}
```

#### Response 400 — Estado inválido

```json
{ "error": "Estado no válido. Solo se permiten: {'GANADO', 'PERDIDO', 'ABANDONO_BOT'}" }
```

#### Response 404 — Sesión no encontrada

```json
{ "error": "Sesión no encontrada" }
```

---

### 2.6 Listar Vendedores Disponibles

```
GET /api/dashboard/salespeople/
```

**Autenticación:** `Authorization: Bearer <JWT>`

Usado para poblar el dropdown de asignación de leads.

#### Response 200 — OK

```json
{
  "salespeople": [
    {
      "id": "sp-uuid-001",
      "name": "juan.perez",
      "email": "juan@automotora.cl",
      "active_sessions_count": 5
    },
    {
      "id": "sp-uuid-002",
      "name": "maria.lopez",
      "email": "maria@automotora.cl",
      "active_sessions_count": 3
    }
  ]
}
```

Solo retorna usuarios con rol `SALESPERSON` del mismo tenant. `active_sessions_count` incluye sesiones en estado `CON_VENDEDOR`, `PENDING_ASSIGNMENT` y `BOT`.

---

## 3. Catálogo de Campos

### 3.1 `status` — Estados de Sesión

| Valor | Significado | Color sugerido |
|-------|-------------|----------------|
| `BOT` | En conversación con el bot | Azul |
| `PENDING_ASSIGNMENT` | Calificado, esperando vendedor | Amarillo |
| `CON_VENDEDOR` | Asignado a un vendedor | Verde |
| `GANADO` | Cerrado exitosamente | Verde oscuro |
| `PERDIDO` | Cerrado sin venta (manual o inactividad) | Rojo |
| `ABANDONO_BOT` | Abandono durante FSM | Gris |

### 3.2 `fsm_step` — Paso Actual del Bot

| Valor | Cuándo aparece |
|-------|----------------|
| `INITIAL` | Primer contacto, aún no responde |
| `VEHICLE_TYPE` | Bot preguntando tipo de auto (City Car, SUV, Sedán) |
| `PAYMENT_METHOD` | Bot preguntando forma de pago (Contado, Crédito, Retoma) |
| `BUDGET_RANGE` | Bot preguntando presupuesto (<6M, 7-14M, >15M) |
| `PURCHASE_INTENT` | Bot preguntando urgencia (Hoy, Esta Semana, Mes o más) |
| `QUALIFIED` | Calificación completa, listo para asignar |

### 3.3 `intent` — Intención de Compra

| Valor | Significado |
|-------|-------------|
| `HOY` | Compra hoy mismo (urgencia máxima) |
| `ESTA_SEMANA` | Compra esta semana |
| `MES_O_MAS` | Compra a largo plazo |
| `null` | Aún no respondió esa pregunta del bot |

### 3.4 `urgency_score` — Score Numérico

- **Rango:** 0 a 160
- **Mayor = más urgente**
- Ya viene ordenado descendente desde el backend
- Se calcula automáticamente según respuestas del bot:
  - Intención: HOY=100, ESTA_SEMANA=20, MES_O_MAS=10
  - Presupuesto: >15M=40, 7-14M=20, <6M=10
  - Crédito: +20 puntos extra

### 3.5 `lead_phone_hash`

Es el UUID del Lead en la base de datos. **No es el número de teléfono real** (por privacidad). Úsalo como identificador visual en el dashboard, no para mostrar al usuario.

---

## 4. Autenticación (Google OIDC)

El backend **no maneja login ni contraseñas**. La autenticación se resuelve directamente con Google Workspace:

### Proveedor Soportado

| Proveedor | Tipo |
|-----------|------|
| Google Workspace | OIDC |

### Flujo

1. El frontend redirige al usuario al login de Google
2. Google devuelve un JWT al frontend
3. El frontend envía el JWT en cada request: `Authorization: Bearer <token>`
4. El backend valida la firma criptográfica del JWT (stateless, sin sesiones)

### Requisitos del JWT

- Debe incluir `sub` (Google Subject ID)
- El `sub` debe estar previamente registrado en la plataforma como `AppUser`
- El backend resuelve el `tenant` automáticamente desde la relación `AppUser.tenant`

---

## 5. Endpoints Operativos (NO usar desde Frontend)

Estos endpoints existen pero son **infraestructura interna**. El frontend NO los consume:

| Endpoint | Método | Uso |
|----------|--------|-----|
| `/api/webhooks/twilio/` | POST | Recibe webhooks de Twilio (WhatsApp) |
| `/api/workers/process-message/` | POST | Worker interno de Cloud Tasks |
| `/health/liveness` | GET | Probe de Cloud Run |
| `/health/readiness` | GET | Probe de Cloud Run |
| `/admin/` | GET | Django Admin (solo staff) |

---

## 6. Endpoints Adicionales (Implementados)

| Endpoint | Método | Descripción |
|---|---|---|
| `GET /api/dashboard/leads/pending/` | GET | Cola de leads pendientes de asignación |
| `GET /api/dashboard/metrics/` | GET | Métricas agregadas (embudo, FSM, urgencia, performance) |
| `GET /api/dashboard/salespeople/` | GET | Listar vendedores disponibles |
| `PATCH /api/dashboard/leads/<id>/status/` | PATCH | Cambiar estado (GANADO/PERDIDO/ABANDONO_BOT) |
| `PATCH /api/dashboard/leads/<id>/reassign/` | PATCH | Reasignar o desasignar lead |

---

## 7. Recomendaciones para el Frontend

### Polling

El backend no tiene WebSockets ni Server-Sent Events. Si necesitas actualización en tiempo real del dashboard, usa **HTTP Polling** cada 10-30 segundos al endpoint `GET /api/dashboard/leads/`.

Para el detalle de mensajes de una sesión, polling cada 5-10 segundos es suficiente.

### Manejo de Errores

- **401:** Redirigir al login del proveedor OIDC
- **403:** Mostrar "Sin acceso — contacta al administrador"
- **409:** Mostrar "Este lead ya tiene vendedor asignado"
- **500:** Mostrar "Error del servidor — intenta de nuevo"

### Ordenamiento

Los leads ya vienen ordenados por `urgency_score` descendente. No reordenar en el frontend.

---

## 8. Referencias

- **Modelo de datos completo:** `docs/MER.md`
- **Especificación técnica:** `docs/MASTER_SPEC.md`
- **Requerimientos funcionales:** `docs/REQUERIMIENTOS.md`
