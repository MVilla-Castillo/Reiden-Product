# Modelo Entidad-Relación (MER) - Arquitectura CCRM

## 1. Entidades de Estructura y Multi-Tenancy

### Tenant (Automotora)
*La raíz de aislamiento de datos y configuración del negocio.*
- **id**: UUID (PK)
- **nombre_legal**: String (Ej: "Villagran & Jara Limitada")
- **rut_empresa**: String (Unique)
- **phone_number_id**: String (Unique)
- **waba_id**: String (Unique, B-Tree Indexed)
- **routing_mode**: Enum (MANUAL, AUTO) - Default: MANUAL (RF-08)
- **is_verified**: Boolean
- **created_at**: Timestamp

### User (Operadores de la Plataforma)
*Implementación del RBAC y Gamificación vía Proveedor de Identidad (IdP).*
- **id**: UUID (PK)
- **tenant_id**: FK (-> Tenant.id, Indexed)
- **oidc_sub**: String (Unique) - Subject ID agnóstico (Entra ID Object ID o Google ID)
- **oidc_issuer**: String (Indexed) - Origen del Subject (ej. `sts.windows.net` o `accounts.google.com`)
- **role**: Enum (ADMIN, MANAGER, SALESPERSON)
- **email**: String (Unique)
- **is_active**: Boolean (Consistencia histórica para rankings)

---

## 2. Entidades Transaccionales (El Motor de Ventas)

### Lead (Cliente Potencial)
*Identidad del prospecto con privacidad garantizada.*
- **id**: UUID (PK)
- **tenant_id**: FK (-> Tenant.id, Indexed)
- **wa_id_hash**: String (Unique, Indexed) - Hash SHA-256 para búsqueda O(1) en webhooks
- **wa_id**: String (Unique) - ID de WhatsApp en texto plano (KISS)
- **first_name**: String (Extraído de Twilio o FSM)
- **last_interaction**: Timestamp
- **is_deleted**: Boolean (Soft-Delete)

### ChatSession (El Embudo)
*Entidad de alta concurrencia. Contiene la FSM y base para métricas.*
- **id**: UUID (PK)
- **tenant_id**: FK (-> Tenant.id, Indexed)
- **lead_id**: FK (-> Lead.id, Indexed)
- **salesperson_id**: FK (-> User.id, Nullable, Indexed) - NULL si es del bot
- **status**: Enum (BOT, PENDING_ASSIGNMENT, CON_VENDEDOR, GANADO, PERDIDO, ABANDONO_BOT)
- **fsm_answers**: JSONB (GIN Indexed) - "Ficha del Cliente" (RNF-05)
- **urgency_score**: Integer (B-Tree Indexed) - Para ORDER BY ultrarrápido (RNF-20)
- **last_fsm_step**: String (Rastreo de paso en la FSM)
- **last_client_message_at**: Timestamp (Ventana de 24h Twilio)
- **lost_reason**: String (Nullable) - Motivo de cierre (manual/automático)
- **created_at**: Timestamp
- **updated_at**: Timestamp
- **is_deleted**: Boolean (Soft-Delete)

---

## 3. Entidades de Comunicación y Trazabilidad

### Message (Historial de Chat)
*Registro inmutable de la conversación.*
- **id**: UUID (PK)
- **tenant_id**: FK (-> Tenant.id, Indexed)
- **session_id**: FK (-> ChatSession.id, Indexed)
- **provider_message_id**: String (Unique) - Idempotencia (RNF-03)
- **direction**: Enum (INBOUND, OUTBOUND)
- **message_type**: Enum (TEXT, IMAGE, AUDIO, DOCUMENTO)
- **body**: Text (String literal o URL firmada de GCP Cloud Storage)
- **created_at**: Timestamp

### AuditLog (Telemetría y Anti-Fraude)
*Base para RF-16 y Gamificación.*
- **id**: BigInt (PK, Auto-inc)
- **session_id**: FK (-> ChatSession.id, Indexed)
- **tenant_id**: FK (-> Tenant.id, Indexed)
- **actor_id**: FK (-> User.id, Nullable) - Humano o Bot
- **action**: String (Ej: "SESSION_START", "FSM_TRANSITION", "STATUS_CHANGED")
- **old_value**: JSONB (Snapshot previo)
- **new_value**: JSONB (Snapshot post-transacción)
- **owner_at_time_of_close**: FK (-> User.id, Nullable)
- **created_at**: Timestamp