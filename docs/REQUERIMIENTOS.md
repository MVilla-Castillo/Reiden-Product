# Especificación de Requisitos del Sistema (CCRM)

## 1. Requisitos Funcionales

### Módulo A: Ingesta y Creación de Sesión
* **RF-01 Actualizado (Milisegundo Cero y Enrutamiento Finito):** El sistema procesa el webhook y busca al Lead mediante el `wa_id_hash`. Si el Lead existe, evalúa su última ChatSession. El sistema reanudará la sesión SOLO SI la sesión tiene menos de 24 horas Y su estado actual pertenece al grupo activo (status IN [BOT, PENDING_ASSIGNMENT, CON_VENDEDOR]). Si el estado es terminal (GANADO, PERDIDO_SISTEMA, ABANDONO_BOT), el sistema ignorará el TTL y creará obligatoriamente una nueva ChatSession.
* **RF-1.1 (Ingesta Universal y Arranque FSM Base):** El sistema procesará el primer mensaje del lead de forma agnóstica a su contenido textual. Ya sea un texto libre o un mensaje predefinido (wa.me / Click-to-WhatsApp), el sistema obligatoriamente creará la ChatSession e inicializará la máquina de estados (FSM) en su estado primario (Estado Cero), delegando al bot la recolección secuencial de datos. Si el payload de Twilio incluye el objeto nativo referral, este se extraerá en segundo plano únicamente para poblar la atribución publicitaria (RF-02), sin alterar ni saltar ningún paso del flujo conversacional.
* **RF-1.2 / RF-XX (Ficha de Lead Instantánea):** Al finalizar la FSM o al ser asignado manualmente, el sistema debe compilar las respuestas del prospecto en un perfil unificado y presentarlo en el Dashboard del Vendedor de forma inmediata (vía HTTP Polling), eliminando la necesidad de que el vendedor repita preguntas de perfilamiento.
* **RF-02 (Atribución por Sesión):** El origen publicitario (acquisition_source y utm_metadata) se guarda en la ChatSession, garantizando que compras futuras de un cliente antiguo no sobreescriban su historial de adquisición original.

### Módulo B: Cualificación (FSM) y Construcción de Perfil
* **RF-03 (Ejecución FSM Idempotente y Temporal):** El bot avanza el campo last_fsm_step secuencialmente. Para garantizar consistencia ante asimetrías de red de Twilio (webhooks desordenados), el sistema debe evaluar el timestamp nativo del payload de Twilio. Si el timestamp entrante es anterior al timestamp del último mensaje procesado en esa sesión, el mensaje se almacenará en el historial, pero se abortará la actualización del estado FSM y del JSON fsm_answers.
* **RF-26 (Interactividad Fricción Cero - UI Ingesta):**
    * **Justificación:** Para que el lead fluya por las 4 preguntas (Modelo, Pago, Presupuesto, Urgencia) sin abandonar.
    * **Lógica:** La FSM en el Módulo B debe orquestar estas preguntas obligatoriamente utilizando el tipo de mensaje INTERACTIVE (Listas o Botones nativos de WhatsApp). Queda estrictamente prohibido obligar al lead a escribir texto libre ("escribe 1 para X"), garantizando una recolección de datos determinista que alimente el JSON fsm_answers sin fallos de parsing.
* **RF-04 (Construcción de Perfil / FSM Answers):** Cada respuesta válida extraída por el bot debe almacenarse progresivamente en el campo fsm_answers (JSONB) de la ChatSession. Este JSON será la "Ficha del Cliente" que visualizará el vendedor.
* **RF-05 (Scoring):** Cálculo del score evaluando las llaves dentro del JSON fsm_answers.
* **RF-06 (Timeout Activo):** Tarea asíncrona audita sesiones en BOT con updated_at superior a 30 minutos, pasándolas a ABANDONO_BOT aunque el JSON fsm_answers esté incompleto.

### Módulo C: Gerencia
* **RF-07 (Data Pool):** Filtrado de leads pasivos agrupando por el status de su última ChatSession.
* **RF-08 (Ruteo & Bandeja con Toggle de Autonomía):** El gerente necesita gobernar el flujo. El sistema proveerá un Toggle (Interruptor) global: MANUAL o AUTO.
    * **Lógica:** Si está en MANUAL, todo lead que termine la FSM cae al estado PENDING_ASSIGNMENT para que el gerente lo asigne a dedo (o lo tome él mismo si es de alto valor). Si el gerente va a almorzar, cambia el toggle a AUTO, y el sistema aplicará un algoritmo Round-Robin sobre los vendedores activos, pasando el lead directamente al estado CON_VENDEDOR.
* **RF-09 (Métrica LRT):** Cálculo del delta de tiempo de primera respuesta.

### Módulo D: Vendedores y Notificaciones
* **RF-10 (Bandeja RLS):** Vendedores solo ven ChatSessions donde salesperson_id == su_id. Al abrir el chat, la UI debe renderizar el JSON fsm_answers como una ficha de cliente.
    * **Restricción de Implementación:** Las consultas de esta bandeja deben utilizar obligatoriamente select_related('lead') a nivel del ORM para resolver los datos de la identidad del cliente mediante un SQL JOIN, previniendo el problema de consultas N+1 al cargar listas concurrentes.
* **RF-10.1 (Gestión de Documentos Adjuntos y Evaluación de Crédito):** La interfaz de chat del vendedor debe renderizar los mensajes de tipo DOCUMENTO (ej. PDFs, Word) como tarjetas de archivo descargables. Al hacer clic, el vendedor podrá descargar el archivo directamente a su PC local accediendo a la URL firmada de GCP Cloud Storage, permitiendo la extracción de antecedentes financieros para derivarlos a las entidades de crédito externas.
* **RF-10.2 (Carga Progresiva de Historial / Lazy Loading):** Al abrir una ChatSession, la interfaz renderizará únicamente los últimos 10 mensajes (inbound/outbound) para proveer contexto inmediato sin penalizar el tiempo de carga (Latencia Zero). El sistema debe proveer un mecanismo en la UI (ej. scroll infinito hacia arriba o botón "Cargar anteriores") para solicitar bloques adicionales de mensajes históricos solo a demanda del usuario.
* **RF-11 (Resolución de Sesión y Abandono Contextual):** El sistema exige el campo lost_reason para cierres manuales. Para evitar la fricción operativa y mantener la higiene de la bandeja, un proceso programado (GCP Cloud Scheduler) evaluará las sesiones inactivas por >48hrs. El sistema cerrará la sesión asignando un lost_reason dinámico basado en el last_fsm_step (ej. si quedó en PRESUPUESTO, la razón será "Abandono tras consultar Presupuesto").
* **RF-11.1 (Motor de Re-enganche Outbound / HSM):** Cuando el TTL de la sesión supere las 24 horas desde el last_client_message_timestamp, el sistema debe bloquear a nivel de frontend el input de texto libre. En su lugar, desplegará una interfaz para despachar Plantillas HSM pre-aprobadas. El backend en Django deberá hidratar las variables posicionales de la plantilla (ej. {{1}}) leyendo los valores previamente almacenados en el fsm_answers del lead antes de orquestar el POST hacia Twilio.
* **RF-12 (Alertas FCM & Fallback):** Push notifications y WhatsAppception vía Cloud Tasks si el SLA de respuesta se rompe.

### Módulo E: Dashboards
* **RF-13 (Dashboard Gerencial - Vista Global):** Gestión del flujo de trabajo en tiempo real.
    * **Lógica:** Renderiza la lista de leads en estado PENDING_ASSIGNMENT ordenados estrictamente por el urgency_score (Semaforización: Rojo para "HOY", Amarillo para "Semana"). Incluye el Toggle global de enrutamiento (MANUAL/AUTO) para controlar el comportamiento del RF-08.
* **RF-13.1 (Dashboard Gerencial - Panel de Telemetría y Conversión):**
    * **Objetivo:** Visibilidad instantánea de la salud del embudo de ventas y rendimiento del equipo.
    * **Lógica:** La UI proveerá una vista superior (widgets o panel lateral) con las siguientes métricas agregadas, filtrables por rango de fechas, vendedor y origen de pauta (acquisition_source):
        1. Lead Response Time (LRT) / Speed to Lead.
        2. Win-Rate (Tasa de Cierre Real).
        3. FSM Drop-off (Fuga de Cualificación).
        4. Volumen Activo.
* **RF-14 (Dashboard Vendedor - Gamificación):** Cada vendedor tendrá un panel individual mostrando su Tasa de Cierre (Win-rate), comisiones estimadas y un ranking relativo (Leaderboard) respecto al equipo.
* **RF-14.1 (Módulo de Gamificación y Leaderboard de Ventas):** El sistema desplegará un ranking en tiempo real ("Leaderboard") visible tanto en el Dashboard Gerencial como en la bandeja individual de cada vendedor, ordenados por leads en estado GANADO.
* **RF-15 (Sincronización Reactiva de Bandeja):** La interfaz gráfica del vendedor debe reaccionar de forma cuasi-realtime a los eventos mediante **HTTP Polling** (ej. cada 2-3 segundos). El DOM debe actualizarse inyectando el nuevo payload sin requerir recargas de página completas.

### Módulo F: Auditoría
* **RF-16 (Event Sourcing parcial):** El sistema debe mantener un registro inmutable (Append-Only Log) de todas las mutaciones críticas sobre las entidades ChatSession y Lead.
* **RF-16.1 (Gestión de Expiración y Limpieza de Pipeline):** Tarea programada (GCP Cloud Scheduler) cada 60 minutos. Todo Lead en estado CON_VENDEDOR sin interacción en 48 horas se mueve a PERDIDO_SISTEMA.

### Módulo G: RBAC Multi-tenant
* **RF-18 (RBAC Multi-tenant):** Aislamiento de acciones por Tenant (Automotora). Roles: SystemAdmin, TenantManager y Salesperson.
* **RF-19 (Respuesta Estándar de Error - Fail-Safe):** Middleware global que devuelve JSON estandarizado en lugar de trazas HTML de error 500.
* **RF-20 (Inmutabilidad por Soft-Delete):** Prohibido el uso de SQL DELETE. Se utiliza bandera is_deleted = True en transacciones atómicas.

## 2. Requisitos No Funcionales

* **RNF-01:** Latencia <100ms delegando ruteos pesados a GCP Cloud Tasks.
* **RNF-02:** Validación criptográfica de la firma X-Twilio-Signature.
* **RNF-03 (RES-01):** Uso del MessageSid de Twilio como UNIQUE constraint para asegurar la idempotencia.
* **RNF-04 (RES-02):** Todo avance de la FSM debe ocurrir dentro de transaction.atomic() en Django.
* **RNF-05 (OPT-01):** Índice GIN con jsonb_path_ops sobre el campo fsm_answers (JSONB).
* **RNF-06 (PERF-01):** Optimización de consultas ORM para dashboards utilizando índices nativos en PostgreSQL en lugar de cachés externos en la V1.
* **RNF-07 (Protocolo de Transporte UI):** Se utilizará HTTP Polling (o SSE opcional) para la reactividad del frontend. Queda prohibida la implementación de WebSockets (Django Channels) en la V1 para simplificar el despliegue.
* **RNF-08 (Seguridad Data-at-Rest & Masking):** Enmascaramiento de PII en logs (ej. +569XXXXX1234). A nivel de infraestructura, la base de datos PostgreSQL debe tener habilitado el cifrado en reposo completo (Data-at-Rest Encryption de GCP).
* **RNF-09 (ACID-01):** Upsert Atómico en PostgreSQL (INSERT ... ON CONFLICT) para evitar condiciones de carrera en ingesta.
* **RNF-10 (Resiliencia de Payload):** Acceso seguro a JSON del webhook. Tiempo de respuesta <100ms para el 200 OK síncrono.
* **RNF-11 (Sincronización de Plantillas):** Tarea programada vía GCP Cloud Scheduler para sincronizar plantillas desde la API de Twilio hacia PostgreSQL.
* **RNF-12 (Observability):** X-Correlation-ID único inyectado en logs y Sentry.
* **RNF-13 (Fallback de Contingencia):** Dashboard Lite alojado en **GCP Cloud Storage** conectado a Cloud Functions de solo lectura.
* **RNF-14 (Colas Serverless):** Uso estricto de GCP Cloud Tasks para manejo de asincronía y DLQ nativo, erradicando el uso de Redis/Celery.
* **RNF-15 (Captura de Excepciones):** Integración con Sentry adjuntando Stack Trace y variables locales (enmascaradas).
* **RNF-16 (Métricas RED):** Endpoint /metrics para Prometheus (Rate, Errors, Duration).
* **RNF-17 (Connection Pooling):** Gestión nativa de conexiones mediante CONN_MAX_AGE en Django apoyado por Cloud SQL Auth Proxy.
* **RNF-18 (Circuit Breaker):** Suspensión temporal de intentos de envío tras 5 fallos consecutivos de la API externa.
* **RNF-19 (Aislamiento Defensivo):** Custom Manager en Django para inyectar cláusulas WHERE tenant_id automáticamente (o PostgreSQL RLS).
* **RNF-20 (Índice de Priorización):** urgency_score como entero indexado B-Tree.
* **RNF-22 (Gamificación Dinámica):** Leaderboard calculado al vuelo vía ORM aprovechando los índices de base de datos.
* **RNF-23 (Eficiencia FSM):** Búsquedas en tiempo real <50ms sobre atributos dinámicos.
* **RNF-24 (Transaccionalidad ACID):** Uso de select_for_update() para evitar colisiones en actualizaciones de JSONB.
* **RNF-25 (Tolerancia a Estructura Parcial):** Programación defensiva mediante .get() para acceso a llaves de JSONB.
* **RNF-26 (Entornos y UAT):** Topología estricta de entornos (Staging -> Producción) con Sandbox de Twilio.
* **RNF-27 (Multimedia):** Soporte exclusivo para TEXTO, AUDIO, IMAGEN y DOCUMENTO con persistencia en GCP Cloud Storage y URLs firmadas.
* **RNF-28 (Optimización de Webhook):** Búsqueda de Leads mediante `wa_id_hash` (SHA-256) con índice B-Tree para garantizar latencia <10ms en la fase de ingesta. (El ID crudo del teléfono se guardará en texto plano por ahora).
* **RNF-29 (Zero-Downtime Migrations):** Prohibición operativa de usar comandos `ALTER TABLE` como *rename column* o *add column* con `DEFAULT` en tablas pesadas (ChatSession, Message) para evitar interrupciones de base de datos en producción.
* **RNF-31 (Healthchecks TCP/HTTP):** Provisión obligatoria de `/health/liveness` (Instancia viva) y `/health/readiness` (Conexiones PostgreSQL establecidas) para integrarse con los health-check probes de GCP Cloud Run.
* **RNF-33 (Dead Letter Queue):** GCP Cloud Tasks absorberá todo webhook excedido de reintentos hacia su DLQ interno de forma Serverless, garantizando que el pipeline nunca se bloquee ("Poison Pills").
* **RNF-34 (Alert Routing P1 - Sentry/GCP Logging):** Cualquier subida anormal (arriba del 1% de requests totales) en Webhooks caídos o desbordes en DLQ de Cloud Tasks, enviará notificaciones en tiempo real al Slack de soporte utilizando las reglas nativas de alertas configuradas en GCP Logging y/o Sentry.
* **RNF-35 (Secrets Caching):** Credenciales (DB, Twilio) deben importarse usando **GCP Secret Manager** para no estar "hardcoded" ni accesibles en repositorios estáticos.
* **RNF-36 (Tipado Estricto de Producción):** El pipeline CI/CD rechazará cualquier commit que no pase una validación estática completa de **MyPy**, obligando al uso de genéricos, esquemas Pydantic o typed dictionaries para los objetos anidados como en `fsm_answers`.
* **RNF-37 (Auth Stateless):** El backend operará bajo un modelo de autenticación sin estado (stateless), validando la firma del JWT en cada request sin requerir sesiones persistentes en servidor.
* **RNF-38 (JWT Handshake):** Validación obligatoria de claims `iss` (Issuer), `aud` (Audience) y `exp` (Expiration) en todos los middlewares de autenticación del backend.
* **RNF-39 (Tenant ID / Domain Linkage):** El sistema debe extraer reclamos específicos del JWT (como `tid` para Microsoft o el dominio alojado `hd` para Google) para vincular la sesión del usuario con el aislamiento lógico de datos (`tenant_id`) de forma inequívoca.
* **RNF-40 (Refresh Token Rotation):** Implementación de rotación de Refresh Tokens para mitigar el riesgo de robo de tokens de larga duración.
* **RNF-41 (ID Token Integrity):** El sistema tratará el ID Token como recurso inmutable y autoportante para evitar consultas redundantes a base de datos de usuarios durante la fase de autorización.
* **RNF-42 (Scoped Access):** El acceso a los recursos del Identity Provider debe limitarse a los "Scopes" mínimos necesarios (`openid`, `profile`, `email`).
* **RNF-43 (Autenticación OIDC Nativa & Multi-Issuer):** El backend debe implementar validación OIDC compatible nativamente con **múltiples emisores (Microsoft Entra ID y Google Identity)** mediante la extracción segura del claim `iss` antes de la validación criptográfica contra el JWKS correspondiente.
* **RNF-44 (Paginación Estricta y Optimización de Índices):** Queda estrictamente prohibido ejecutar consultas al historial de mensajes de una sesión sin un límite explícito (limit). Todo endpoint que retorne mensajes debe implementar paginación (preferentemente Cursor Pagination basada en `created_at` o `id`). La base de datos debe contar obligatoriamente con un índice compuesto B-Tree sobre `(session_id, created_at DESC)` en la tabla `Message` para garantizar que la carga inicial de los últimos 10 mensajes se resuelva en tiempo logarítmico (O(log n)) con una latencia <10ms.