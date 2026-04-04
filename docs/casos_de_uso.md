# Catálogo de Casos de Uso — CCRM-SAAS

> **Fuente:** `docs/REQUERIMIENTOS.md`
> **Sistema:** Customer Conversational Relationship Management (CCRM)
> **Total:** 35 casos de uso en 8 módulos

## Actores

| Actor | Descripción |
| :--- | :--- |
| **Lead** | Prospecto externo vía WhatsApp |
| **Bot FSM** | Agente automatizado de flujo conversacional |
| **Vendedor** | Agente interno de ventas |
| **Gerente** | Administrador del pipeline y equipo |
| **SystemAdmin** | Admin técnico multi-tenant |
| **Cloud Scheduler** | Actor GCP para tareas programadas |
| **Twilio** | Plataforma de mensajería (webhooks) |

---
## Módulo A — Ingesta

### UC-A01: Procesar Primer Mensaje de Lead Nuevo
**Actor:** Twilio / Bot FSM | **Req:** RF-1.1

**Precondición:** wa_id no existe en DB.

**Flujo:**
1. Twilio envía webhook
2. Sistema valida X-Twilio-Signature
3. Deriva wa_id_hash y confirma que Lead no existe
4. Crea Lead + ChatSession; inicializa FSM en Estado Cero
5. Si payload contiene referral, captura atribución en background (RF-02)
6. Bot envía primer mensaje INTERACTIVE
7. Retorna 200 OK < 100ms

**Postcondición:** Lead + ChatSession creados; FSM en Estado Cero.

---
### UC-A02: Reanudar Sesión Existente
**Actor:** Twilio / Bot FSM | **Req:** RF-01

**Precondición:** Lead existe + última ChatSession < 24h en estado activo (BOT / PENDING_ASSIGNMENT / CON_VENDEDOR).

**Flujo:**
1. Sistema localiza Lead por wa_id_hash
2. Evalúa última ChatSession (estado activo + TTL < 24h)
3. Reanuda la sesión y continúa FSM

**Postcondición:** Sesión reanudada; FSM continúa.

---
### UC-A03: Nueva Sesión para Lead con Sesión Terminal
**Actor:** Twilio / Bot FSM | **Req:** RF-01

**Precondición:** Lead existe; última sesión en estado terminal (GANADO / PERDIDO / ABANDONO_BOT).

**Flujo:**
1. Detecta estado terminal
2. Ignora TTL y crea nueva ChatSession obligatoriamente
3. Inicializa FSM en Estado Cero; historial anterior preservado

**Postcondición:** Nueva ChatSession; historial de adquisición original intacto.

---
### UC-A04: Capturar Atribución Publicitaria UTM/Referral
**Actor:** Twilio | **Req:** RF-02

**Precondición:** Payload contiene objeto referral.

**Flujo:**
1. Extrae acquisition_source y utm_metadata del payload
2. Persiste en ChatSession actual
3. No altera flujo FSM

**Postcondición:** Atribución persistida; nunca sobreescrita en sesiones futuras.

---
## Módulo B — Cualificación (FSM)

### UC-B01: Avanzar FSM con Respuesta Interactiva
**Actor:** Bot FSM / Lead | **Req:** RF-03, RF-26, RF-04

**Precondición:** ChatSession en BOT; paso FSM pendiente.

**Flujo:**
1. Lead recibe mensaje INTERACTIVE (botones/lista)
2. Lead selecciona opción (prohibido texto libre)
3. Sistema valida timestamp del webhook (idempotencia de orden)
4. Actualiza fsm_answers (JSONB) y avanza last_fsm_step
5. Envía siguiente mensaje INTERACTIVE

**Postcondición:** fsm_answers actualizado; FSM avanzó un paso.

---
### UC-B02: Ignorar Webhook Desordenado
**Actor:** Twilio | **Req:** RF-03

**Precondición:** Webhook con timestamp anterior al último procesado.

**Flujo:**
1. Sistema compara timestamps
2. Detecta mensaje desordenado
3. Persiste mensaje en historial (sin perderlo)
4. Aborta actualización FSM y fsm_answers
5. Retorna 200 OK

**Postcondición:** Mensaje en historial; FSM no retrocedió.

---
### UC-B03: Calcular Urgency Score
**Actor:** Bot FSM | **Req:** RF-05

**Precondición:** fsm_answers tiene al menos una respuesta.

**Flujo:**
1. Evalúa llaves de fsm_answers (tipo_pago, presupuesto, urgencia)
2. Calcula urgency_score (int 0-160+)
3. Persiste en ChatSession

**Postcondición:** urgency_score almacenado.

---
### UC-B04: Transicionar a ABANDONO_BOT por Timeout
**Actor:** Cloud Scheduler | **Req:** RF-06

**Precondición:** ChatSession en BOT con updated_at > 30 min.

**Flujo:**
1. Scheduler dispara auditoría periódica
2. Identifica sesiones BOT con inactividad > 30 min
3. Cambia estado a ABANDONO_BOT (incluso con fsm_answers incompleto)
4. Escribe en AuditLog

**Postcondición:** Pipeline limpio; AuditLog actualizado.

---
### UC-B05: Compilar Ficha de Cliente al Finalizar FSM
**Actor:** Bot FSM | **Req:** RF-1.2

**Precondición:** Todos los pasos FSM completados.

**Flujo:**
1. Compila fsm_answers en perfil unificado
2. Transiciona ChatSession a PENDING_ASSIGNMENT
3. Perfil disponible en Dashboard vía HTTP Polling

**Postcondición:** Sesión en PENDING_ASSIGNMENT; ficha lista.

---
## Módulo C — Gerencia

### UC-C01: Ver Pool de Leads Pendientes
**Actor:** Gerente | **Req:** RF-07

**Precondición:** Gerente autenticado (JWT OIDC válido).

**Flujo:**
1. Consulta ChatSession filtradas por tenant_id agrupadas por estado
2. Renderiza lista ordenada por urgency_score DESC (Rojo=HOY, Amarillo=Semana)

**Postcondición:** Pool segmentado por estado y prioridad visible.

---
### UC-C02: Asignar Lead a Vendedor (Modo Manual)
**Actor:** Gerente | **Req:** RF-08

**Precondición:** Toggle en MANUAL; sesión en PENDING_ASSIGNMENT.

**Flujo:**
1. Gerente selecciona lead y elige vendedor del mismo tenant
2. transaction.atomic(): actualiza salesperson_id, assigned_at → CON_VENDEDOR
3. AuditLog + notificación FCM opcional

**Postcondición:** Lead asignado; assigned_at poblado; sesión en CON_VENDEDOR.

---
### UC-C03: Activar Enrutamiento Automático Round-Robin
**Actor:** Gerente | **Req:** RF-08

**Precondición:** Gerente autenticado.

**Flujo:**
1. Toggle → AUTO confirmado para el tenant
2. Cada lead que complete FSM asignado automáticamente por Round-Robin
3. PENDING_ASSIGNMENT → CON_VENDEDOR sin intervención manual

**Postcondición:** Enrutamiento automático activo.

---
### UC-C04: Consultar Métrica LRT (Lead Response Time)
**Actor:** Gerente | **Req:** RF-09

**Precondición:** Sesiones con first_response_at y assigned_at poblados.

**Flujo:**
1. Gerente filtra por fecha y vendedor
2. Backend calcula delta first_response_at − assigned_at
3. Retorna avg_time_to_first_response

**Postcondición:** LRT visualizado.

---
## Módulo D — Vendedores

### UC-D01: Ver Bandeja de Leads Asignados
**Actor:** Vendedor | **Req:** RF-10

**Precondición:** Vendedor autenticado; sesiones con salesperson_id == su id.

**Flujo:**
1. Consulta con select_related('lead') (anti N+1 obligatorio)
2. Renderiza lista con ficha de cliente de fsm_answers

**Postcondición:** Bandeja cargada en un solo SQL JOIN.

---
### UC-D02: Abrir Chat con Lazy Loading de Historial
**Actor:** Vendedor | **Req:** RF-10.2

**Precondición:** Vendedor selecciona ChatSession.

**Flujo:**
1. Sistema carga últimos 10 mensajes (índice B-Tree session_id, created_at DESC)
2. UI renderiza histórico inmediato
3. Scroll hacia arriba carga siguientes bloques (cursor pagination)

**Postcondición:** Chat con baja latencia; historial accesible bajo demanda.

---
### UC-D03: Enviar Mensaje de Texto al Lead
**Actor:** Vendedor | **Req:** RF-10, RF-11.1

**Precondición:** Sesión en CON_VENDEDOR; TTL 24h activo.

**Flujo:**
1. Valida ventana de 24h activa
2. Persiste Message en DB
3. Actualiza first_response_at si es primer mensaje OUTBOUND
4. Post a Twilio API (FUERA de transaction.atomic)
5. AuditLog registra evento

**Postcondición:** Mensaje enviado; first_response_at actualizado si aplica.

---
### UC-D04: Descargar Documento Adjunto del Lead
**Actor:** Vendedor | **Req:** RF-10.1

**Precondición:** Lead envió un archivo; tarjeta de documento en bandeja.

**Flujo:**
1. Vendedor hace clic en tarjeta
2. Sistema genera URL firmada de GCP Cloud Storage
3. Archivo descargado en PC del Vendedor

**Postcondición:** Documento descargado; sin URLs permanentes expuestas.

---
### UC-D05: Enviar Plantilla HSM (Re-enganche Outbound)
**Actor:** Vendedor | **Req:** RF-11.1

**Precondición:** TTL 24h expirado; input de texto bloqueado en UI.

**Flujo:**
1. UI bloquea texto libre y muestra selector de Plantillas HSM
2. Vendedor selecciona plantilla
3. Backend hidrata variables {{1}}, {{2}} desde fsm_answers
4. POST a Twilio con HSM completa

**Postcondición:** HSM enviado; re-enganche sin violar políticas WhatsApp.

---
### UC-D06: Cerrar Sesión Manualmente (GANADO / PERDIDO)
**Actor:** Vendedor / Gerente | **Req:** RF-11

**Precondición:** Sesión en CON_VENDEDOR.

**Flujo:**
1. Selecciona "Cerrar sesión" + resultado GANADO o PERDIDO
2. Si PERDIDO exige lost_reason
3. transaction.atomic(): actualiza estado + closed_at
4. AuditLog registra cierre

**Postcondición:** Sesión en estado terminal; closed_at y lost_reason persistidos.

---
### UC-D07: Recibir Notificación Push de Lead Asignado
**Actor:** Vendedor | **Req:** RF-12

**Precondición:** Lead asignado al Vendedor.

**Flujo:**
1. Sistema detecta asignación
2. GCP Cloud Tasks despacha notificación FCM
3. Si SLA se rompe → push FCM al vendedor
4. Fallback: mensaje WhatsApp directo (WhatsAppception)

**Postcondición:** Vendedor notificado; SLA monitoreado.

---
### UC-D08: Sincronización Reactiva por HTTP Polling
**Actor:** Vendedor (UI Angular) | **Req:** RF-15

**Precondición:** UI abierta.

**Flujo:**
1. Angular hace polling cada 2-3 segundos al endpoint REST
2. Backend devuelve estado actualizado
3. DOM actualizado sin recargar página

**Postcondición:** Bandeja cuasi-realtime sin WebSockets.

---
## Módulo E — Dashboards

### UC-E01: Ver Dashboard Gerencial con Pipeline
**Actor:** Gerente | **Req:** RF-13

**Precondición:** Rol TenantManager autenticado.

**Flujo:**
1. Renderiza PENDING_ASSIGNMENT ordenados por urgency_score DESC con semaforización
2. Muestra Toggle MANUAL/AUTO
3. Permite interactuar con UC-C02 y UC-C03

**Postcondición:** Pipeline priorizado y visible.

---
### UC-E02: Consultar Panel de Telemetría y Conversión
**Actor:** Gerente | **Req:** RF-13.1

**Precondición:** Datos históricos disponibles.

**Flujo:**
1. Gerente filtra por fechas, vendedor, acquisition_source
2. GET /api/dashboard/metrics/ agrega en tiempo real
3. UI renderiza: LRT, Win-Rate, FSM Drop-off, Volumen Activo

**Postcondición:** Panel de telemetría actualizado.

---
### UC-E03: Ver Leaderboard y Gamificación
**Actor:** Gerente / Vendedor | **Req:** RF-14, RF-14.1

**Precondición:** Sesiones cerradas en GANADO existen.

**Flujo:**
1. Sistema calcula ranking al vuelo (ORM + índices B-Tree)
2. Ordena por leads GANADO por vendedor
3. Renderiza Win-Rate, comisiones estimadas, posición

**Postcondición:** Ranking visible; gamificación activa.

---
## Módulo E2 — Analytics

### UC-E2-01: Consultar Métricas de Embudo
**Actor:** Gerente | **Req:** RF-XX (Embudo)

**Flujo:**
GET /api/dashboard/metrics/?date_from=&date_to=  
Retorna: total_leads, completed_fsm, assigned_leads, won_sessions, lost_sessions, abandoned_sessions, conversion_rate_fsm, conversion_rate_assignment, win_rate.

**Postcondición:** Embudo de conversión calculado.

---
### UC-E2-02: Distribución de Atributos FSM
**Actor:** Gerente | **Req:** RF-XX (Distribución FSM)

**Flujo:**
1. Agrega sobre JSONB fsm_answers con índices GIN
2. Retorna: distribución de vehículo, pago, presupuesto, intención de compra

**Postcondición:** Gerente ajusta inventario y estrategia.

---
### UC-E2-03: Distribución de Urgency Score
**Actor:** Gerente | **Req:** RF-XX (Urgencia)

**Flujo:**
1. Histograma sobre urgency_score: Frío(0-30), Tibio(31-60), Cálido(61-100), Caliente(100+)
2. Define SLA diferenciados por bucket

**Postcondición:** Recursos asignados por prioridad real.

---
### UC-E2-04: Performance Individual de Vendedor
**Actor:** Gerente | **Req:** RF-XX (Performance)

**Flujo:**
1. Filtra por salesperson_id y período
2. Retorna: leads_assigned, wins, losses, win_rate, avg_first_response_time, budget_distribution

**Postcondición:** Métricas individuales para evaluación y gamificación.

---
## Módulo F — Auditoría

### UC-F01: Registrar Evento Inmutable en AuditLog
**Actor:** Sistema | **Req:** RF-16

**Precondición:** Mutación crítica en ChatSession o Lead.

**Flujo:**
1. Cualquier transición de estado dispara escritura Append-Only
2. Registra: event_type, tenant_id, entity_id, old_state, new_state, actor_id, timestamp

**Postcondición:** Historial inmutable; trazabilidad completa.

---
### UC-F02: Limpiar Pipeline por Inactividad (Scheduler)
**Actor:** Cloud Scheduler | **Req:** RF-16.1

**Precondición:** Sesiones con inactividad > 7 días.

**Flujo:**
1. Scheduler cada 60 minutos
2. CON_VENDEDOR > 7 días → PERDIDO (lost_reason="Inactividad 7 dias")
3. BOT/PENDING_ASSIGNMENT > 7 días → ABANDONO_BOT
4. lost_reason dinámico basado en last_fsm_step
5. AuditLog actualizado

**Postcondición:** Pipeline limpio; razón contextual registrada.

---
### UC-F03: Sincronizar Plantillas HSM desde Twilio
**Actor:** Cloud Scheduler | **Req:** RNF-11

**Flujo:**
1. Scheduler dispara sincronización periódica
2. Consulta API Twilio → lista plantillas aprobadas
3. Upsert atómico (INSERT ... ON CONFLICT) en PostgreSQL

**Postcondición:** Plantillas locales sincronizadas con Twilio.

---
## Módulo G — RBAC / Multi-tenant

### UC-G01: Autenticar con OIDC Multi-Issuer
**Actor:** Todos los usuarios | **Req:** RF-18, RNF-43

**Flujo:**
1. Detecta proveedor (Microsoft Entra ID o Google Workspace) por claim iss
2. Valida claims iss, aud, exp del JWT
3. Extrae tenant_id desde tid (Microsoft) o hd (Google)
4. Sesión stateless; sin guardar en DB

**Postcondición:** Usuario autenticado; aislamiento por tenant garantizado.

---
### UC-G02: Control de Acceso por Rol (RBAC)
**Actor:** Sistema / Middleware | **Req:** RF-18

**Flujo:**
1. Middleware extrae rol del JWT
2. Valida permisos para el recurso solicitado
3. Deniega con error JSON estándar si no autoriza

**Roles:**
- SystemAdmin → acceso total cross-tenant
- TenantManager → gestión completa de su tenant
- Salesperson → solo sus ChatSession asignadas

**Postcondición:** Acceso concedido o denegado; multi-tenant aislado.

---
### UC-G03: Soft-Delete en Entidad Core
**Actor:** Gerente / SystemAdmin | **Req:** RF-20

**Flujo:**
1. Sistema intercepta solicitud de eliminación
2. Prohíbe SQL DELETE
3. transaction.atomic(): is_deleted = True
4. ActiveManager filtra automáticamente en queries futuras
5. AuditLog registra el evento

**Postcondición:** Registro lógicamente eliminado; datos para auditoría preservados.

---
### UC-G04: Error Estándar JSON Fail-Safe
**Actor:** Sistema / Middleware Global | **Req:** RF-19

**Flujo:**
1. Middleware captura excepción no controlada
2. Enmascara stack trace (nunca HTML)
3. Retorna JSON con code, message, trace_id
4. Envía a Sentry con tenant_id, user_id (sin PII)

**Postcondición:** Cliente recibe JSON limpio; Sentry captura contexto.

---
## Resumen Ejecutivo — 35 Casos de Uso

| ID | Nombre | Actor | Módulo |
| :--- | :--- | :--- | :--- |
| UC-A01 | Procesar primer mensaje de nuevo lead | Twilio / Bot | Ingesta |
| UC-A02 | Reanudar sesión existente | Twilio / Bot | Ingesta |
| UC-A03 | Nueva sesión para lead con sesión terminal | Twilio / Bot | Ingesta |
| UC-A04 | Capturar atribución publicitaria UTM | Twilio | Ingesta |
| UC-B01 | Avanzar FSM con respuesta interactiva | Bot / Lead | Cualificación |
| UC-B02 | Ignorar webhook desordenado | Sistema | Cualificación |
| UC-B03 | Calcular urgency score del lead | Bot FSM | Cualificación |
| UC-B04 | Timeout → ABANDONO_BOT | Cloud Scheduler | Cualificación |
| UC-B05 | Compilar ficha de cliente al finalizar FSM | Bot FSM | Cualificación |
| UC-C01 | Ver pool de leads pendientes | Gerente | Gerencia |
| UC-C02 | Asignar lead a vendedor (modo manual) | Gerente | Gerencia |
| UC-C03 | Activar enrutamiento automático Round-Robin | Gerente | Gerencia |
| UC-C04 | Consultar métrica LRT | Gerente | Gerencia |
| UC-D01 | Ver bandeja de leads asignados | Vendedor | Vendedores |
| UC-D02 | Abrir chat con lazy loading | Vendedor | Vendedores |
| UC-D03 | Enviar mensaje de texto al lead | Vendedor | Vendedores |
| UC-D04 | Descargar documento adjunto | Vendedor | Vendedores |
| UC-D05 | Enviar plantilla HSM (re-enganche) | Vendedor | Vendedores |
| UC-D06 | Cerrar sesión (GANADO / PERDIDO) | Vendedor / Gerente | Vendedores |
| UC-D07 | Recibir notificación push FCM | Sistema / FCM | Vendedores |
| UC-D08 | Sincronización reactiva por HTTP Polling | UI Angular | Vendedores |
| UC-E01 | Dashboard gerencial con pipeline | Gerente | Dashboards |
| UC-E02 | Panel de telemetría y conversión | Gerente | Dashboards |
| UC-E03 | Leaderboard y gamificación | Gerente / Vendedor | Dashboards |
| UC-E2-01 | Métricas de embudo de conversión | Gerente | Analytics |
| UC-E2-02 | Distribución de atributos FSM | Gerente | Analytics |
| UC-E2-03 | Distribución de urgency score | Gerente | Analytics |
| UC-E2-04 | Performance individual de vendedor | Gerente | Analytics |
| UC-F01 | Registrar evento en AuditLog | Sistema | Auditoría |
| UC-F02 | Limpiar pipeline por inactividad | Cloud Scheduler | Auditoría |
| UC-F03 | Sincronizar plantillas HSM desde Twilio | Cloud Scheduler | Auditoría |
| UC-G01 | Autenticar con OIDC multi-issuer | Todos | RBAC / Auth |
| UC-G02 | Control de acceso por rol (RBAC) | Sistema / Middleware | RBAC / Auth |
| UC-G03 | Soft-delete en entidad core | Gerente / Admin | RBAC / Auth |
| UC-G04 | Error estándar JSON fail-safe | Sistema / Middleware | RBAC / Auth |
