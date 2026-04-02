# PROMPT DE GESTIÓN DE BITÁCORA PARA APRENDIZAJE SENIOR (ADR-DRIVEN)

**Instrucción Permanente para el Agente:** "Actúa como un Ingeniero de Software Senior documentando para un Arquitecto de Sistemas. Tu misión no es solo registrar qué código se escribió, sino el **proceso de pensamiento ingenieril** detrás. Cada vez que actualices esta `BITACORA.md`, debes seguir estrictamente la estructura de Registro de Decisión Arquitectónica (ADR) para transformar el desarrollo en un recurso de estudio de alto nivel."

---

###  ESTRUCTURA DE CADA ENTRADA

#### 1. Contexto y Decisión (El "Por Qué")
* **Descripción:** Explica el problema técnico y la razón de la solución.
* **Restricción:** Evita descripciones superficiales. Usa terminología de arquitectura (ej: "Aislamiento de dominio", "Consistencia eventual", "Reducción de acoplamiento").

#### 2. Trade-offs (Alternativa A vs. B)
* **Análisis:** Identifica una solución alternativa que se consideró y por qué se descartó. 
* **Impacto:** ¿Qué sacrificamos? (ej: "Simplicidad vs. Escalabilidad", "Latencia vs. Consistencia").

#### 3. Anatomía del Edge Case y Resiliencia
* **Definición:** Detalla los 2 casos de borde (Edge Cases) discutidos en la sesión.
* **Mitigación:** Explica exactamente cómo el código previene el fallo (ej: "Rollback en transacciones atómicas", "Manejo de timeouts en red", "Validación de idempotencia").

#### 4. Concepto de Ingeniería Consolidado
* **Teoría:** Nombra el principio fundamental aplicado (SOLID, ACID, CAP Theorem, Idempotencia, Inyección de Dependencias, etc.).
* **Breve Definición:** Una oración que explique cómo este principio se manifiesta en el código actual.

#### 5. Deuda Técnica o Siguiente Paso (KISS)
* **Evolución:** ¿Qué se simplificó para cumplir con el sprint (V1) que podría requerir refactorización al escalar a 100x usuarios?

---

###  EJEMPLO DE REFERENCIA (Cómo debe lucir una entrada):

#### [FECHA] - Implementación de Ingesta de Webhooks (Twilio)
* **Decisión:** Implementación de flujo asíncrono mediante `GCP Cloud Tasks`.
* **El Por Qué:** Para garantizar que el webhook de Twilio responda con un 200 OK en <200ms, evitando bloqueos por latencia y permitiendo que el procesamiento de la FSM ocurra en un worker independiente.
* **Trade-off:** Se eligió *Escalado a Cero* en Cloud Run sacrificando un *Cold Start* inicial de 2s, priorizando la optimización de costos para el Tenant.
* **Edge Case:** 1. **Mensajes Duplicados:** Mitigado mediante `UniqueConstraint` en `provider_message_id`.
    2. **Fallo de Worker:** Cloud Tasks gestiona el reintento automático (Exponential Backoff).
* **Concepto Senior:** **Idempotencia**. Garantizamos que procesar el mismo mensaje N veces produzca el mismo estado final en la base de datos sin duplicar registros.
* **Siguiente Paso:** Implementar monitoreo de cuotas en Cloud Tasks para prevenir el agotamiento de la tasa de despacho.

## Registro de Cambios

### [10 de Marzo de 2026] Del Diseño a la Realidad: Implementación del Núcleo de Datos en Django

**Contexto:**
Se materializa la arquitectura de datos con la creación de la aplicación `crm` en Django. Este commit representa la traducción directa del Modelo Entidad-Relación (`MER.md`) a modelos de Django concretos, estableciendo el pilar fundamental sobre el cual se construirán todas las funcionalidades del sistema.

**Decisiones de Implementación Destacadas:**

1.  **Modelado Fiel a la Especificación:** Se han creado los modelos `Tenant`, `AppUser`, `Lead`, `ChatSession`, `Message` y `AuditLog`, adhiriéndose estrictamente a los tipos de datos y relaciones definidos. Se utilizan `UUIDField` como llaves primarias para desacoplar la identidad del registro de la implementación de la base de datos.

2.  **Optimización de Performance a Nivel de ORM:** Las decisiones de performance de la especificación se ven reflejadas en el código:
    *   **`GinIndex`:** Se aplica un índice GIN sobre el campo `JSONField` `fsm_answers` en `ChatSession`, preparando el sistema para consultas eficientes sobre la data semi-estructurada de la FSM.
    *   **Índices B-Tree:** Campos críticos para el ordenamiento y la búsqueda rápida como `urgency_score` y `wa_id_hash` han sido correctamente indexados a nivel de base de datos a través del ORM.

3.  **Implementación de la Regla de "Soft-Delete" (Inmutabilidad):** Se ha implementado un `ActiveManager` personalizado en los modelos `Lead` y `ChatSession`. Este manager de Django filtra automáticamente los registros marcados como `is_deleted=True`, haciendo que la política de no borrado físico (`RF-20`) sea el comportamiento por defecto en toda la aplicación y no una ocurrencia tardía. Esta es una manifestación clave de una arquitectura limpia y robusta.

4.  **Usuario Personalizado y RBAC:** Se establece el modelo `AppUser` como el `AUTH_USER_MODEL` del proyecto, sentando las bases para una integración futura con Microsoft Entra ID y la implementación de un sistema de roles (`Role`) y aislamiento por tenant.

**Impacto y Próximos Pasos:**
Con el esquema de la base de datos solidificado en código y la primera migración generada, el "esqueleto" del CCRM está completo. Esta base de datos tipada y optimizada permite ahora el desarrollo de la capa de servicio y los endpoints de la API (`views.py`) con la confianza de que el almacenamiento de datos es robusto, escalable y está alineado con todos los requerimientos de negocio y no funcionales.

### [10 de Marzo de 2026] Cimentando una Arquitectura Robusta, Escalable y Eficiente

**Contexto:**
Tras un análisis exhaustivo de los requerimientos funcionales, no funcionales y el modelo de datos (`REQUERIMIENTOS.md`, `MASTER_SPEC.md`, `MER.md`), hoy se solidifican las decisiones arquitectónicas fundacionales del CCRM. La filosofía es clara: construir sobre pilares **serverless**, **seguros** y **pragmáticos**, priorizando la eficiencia operativa y la velocidad de desarrollo sin sacrificar la calidad.

**Decisiones Arquitectónicas Destacadas:**

1.  **Abrazo a la Arquitectura Serverless (YAGNI en acción):** Se toma la decisión estratégica de **eliminar por completo la necesidad de Redis y Celery**. La gestión de tareas asíncronas, webhooks y procesos diferidos se delega íntegramente a **GCP Cloud Tasks y GCP Cloud Scheduler**. Esta elección no solo simplifica radicalmente la infraestructura (`--min-instances 0` en Cloud Run), sino que nos regala resiliencia nativa (reintentos exponenciales, DLQ) y un modelo de costos puramente basado en el consumo. Menos infraestructura que gestionar, más foco en el producto.

2.  **Diseño de Base de Datos Orientado a Performance:** El MER se ratifica con decisiones clave para el alto rendimiento. El uso de **JSONB con índices GIN** para las respuestas de la FSM (`fsm_answers`) y un **índice B-Tree** para el `urgency_score` son optimizaciones concretas que aseguran consultas ultra-rápidas en los dashboards, incluso cuando los datos crezcan. La indexación del `wa_id_hash` para la ingesta de webhooks es un seguro de baja latencia.

3.  **Seguridad y Autenticación de Grado Empresarial:** Se opta por un modelo **stateless** con **Microsoft Entra ID (Azure AD) como único proveedor de identidad (OIDC)**. La validación de JWT en el backend (Django) en cada request nos permite escalar horizontalmente sin preocuparnos por la gestión de sesiones. El uso de **GCP Secret Manager** es innegociable, eliminando cualquier credencial del código fuente.

4.  **Pragmatismo en la Experiencia de Usuario (KISS):** Para la V1, se descarta la complejidad de WebSockets. La reactividad de la interfaz de vendedor se logrará mediante **HTTP Polling**, una solución robusta y probada que ofrece una experiencia cuasi-realtime sin la sobrecarga de ingeniería de las conexiones persistentes.

5.  **Cultura de Calidad y Cero Downtime:** La obligatoriedad de usar **MyPy para tipado estricto**, junto con una estrategia de **migraciones de "cero downtime"** y un pipeline de CI/CD que utiliza despliegues canarios en **GCP Cloud Run**, establece un estándar de calidad altísimo desde el primer día. Construimos un sistema pensado para no fallar y para desplegarse sin interrumpir el servicio.

**Impacto y Próximos Pasos:**
Con estas decisiones, la base del CCRM-SAAS es moderna, resiliente y extremadamente eficiente. Se ha logrado un equilibrio perfecto entre el uso de tecnología de punta y la simplicidad operativa. El camino está despejado para comenzar a traducir estas especificaciones en código de alta calidad, sabiendo que la estructura que lo soportará es sólida como una roca.

### [11 de Marzo de 2026] Blindaje SRE y Alineación Serverless: Completando el Cimiento

**Contexto:**
Hoy se cierra la fase de "Cimientos" del Sprint 1, elevando la vara de calidad técnica mediante la implementación de defensas de Site Reliability Engineering (SRE) y la limpieza absoluta de la arquitectura para cumplir con el paradigma Serverless definido en el `MASTER_SPEC.md`.

**Decisiones de Implementación Destacadas:**

1.  **Aislamiento Multi-Tenant de Nivel Profesional (RLS Lógico):**
    *   Se implementó el `TenantManager` y `ActiveTenantManager` en el core de Django. Esta abstracción obliga a que cualquier consulta de datos transaccionales (`Lead`, `ChatSession`, `Message`) deba pasar por un filtro explícito de `tenant_id`, eliminando el riesgo de fuga de datos entre empresas por error humano en las Vistas.

2.  **Solución al "Thundering Herd" vía Base de Datos:**
    *   **Problema:** Al escalar a cero en Cloud Run, múltiples webhooks simultáneos podrían disparar contenedores paralelos intentando crear la misma sesión.
    *   **Solución:** Se implementó un `UniqueConstraint` parcial en PostgreSQL sobre `ChatSession`. La regla garantiza que un Lead solo puede tener **una** sesión cuya fase no sea terminal. Esto delega la resolución de conflictos de concurrencia a la atomicidad nativa de la base de datos, capturando el `IntegrityError` en la aplicación para redirigir el tráfico al registro ganador.

3.  **Prevención de Deadlocks y Corrupción de JSONB:**
    *   Se estableció la regla innegociable de usar `select_for_update()` dentro de bloques `transaction.atomic()` para cualquier actualización del estado de la FSM. Esto asegura un Row-Level Lock en PostgreSQL, previniendo que actualizaciones concurrentes sobre el campo `fsm_answers` se pisen entre sí.

4.  **Consolidación del Roadmap y Stack:**
    *   Se sincronizó el `SPRINTS.md` eliminando dependencias heredadas como Redis/Celery y WebSockets. Se inicializó formalmente el proyecto **Angular 18+** en la carpeta `frontend/`, ratificando el uso de HTTP Polling reactivo con RxJS para la V1.

**Impacto y Próximos Pasos:**
El Sprint 1 se declara **Exitoso y Finalizado**. El sistema cuenta hoy con una base de datos blindada contra fallos de concurrencia y un aislamiento multi-tenant robusto. El camino queda despejado para el **Sprint 2**, donde implementaremos la Identidad Stateless con Microsoft Entra ID, conectando este núcleo de datos con la autenticación empresarial real.

### [11 de Marzo de 2026] Identidad Stateless Multi-Issuer: Soporte para Google y Microsoft

**Contexto:**
Ante el requerimiento de soportar identidades de diversos ecosistemas (Gerencia en Microsoft @hotmail y Vendedores en Google @gmail), se decidió evolucionar la arquitectura de autenticación hacia un modelo **OIDC Multi-Issuer Stateless**. Esto garantiza que el sistema sea agnóstico al proveedor, manteniendo la seguridad perimetral delegada en las Big Tech.

**Decisiones de Implementación Destacadas:**

1.  **Refactor del Modelo de Usuario (Agnosticismo OIDC):**
    *   Se eliminaron los campos acoplados a Azure (`azure_oid`, `microsoft_tenant_id`) en `AppUser`.
    *   Se implementaron campos estándar de la industria: `oidc_sub` (Subject ID) y `oidc_issuer`, permitiendo que un mismo sistema identifique usuarios de Microsoft Entra ID y Google Identity de forma nativa.

2.  **Middleware Maestro de Identidad (`OIDCStatelessMiddleware`):**
    *   Se desarrolló un middleware en Django que inspecciona el emisor (`iss`) del JWT sin verificarlo aún, para luego descargar dinámicamente el JWKS (JSON Web Key Set) correspondiente de Google o Microsoft.
    *   **Resiliencia SRE:** El middleware incluye lógica de re-fetch automático ante fallos de `kid` (Key ID), mitigando riesgos por rotación de llaves silenciosa en los proveedores.

3.  **Seguridad y Área de Ataque:**
    *   Se ratifica el modelo Stateless: el backend no guarda contraseñas ni sesiones locales. La "guerra cibernética" (Brute force, MFA, detección de anomalías) se delega a Google y Microsoft, reduciendo drásticamente el área de ataque del CRM.

4.  **Higiene del Repositorio (`.gitignore`):**
    *   Se implementó un `.gitignore` de grado profesional para evitar la fuga de secretos (`.env`), carpetas de entorno virtual (`.venv`) y basura de sistemas operativos o IDEs, asegurando un repositorio limpio y seguro.

**Impacto y Próximos Pasos:**
El backend está técnicamente preparado para recibir y validar tokens de casi cualquier proveedor OIDC. Con esto, el **Sprint 2** avanza firmemente. Lo siguiente será la implementación del frontend en Angular para orquestar los flujos de login (MSAL / Google Identity) y el cierre de este sprint con el login funcional.
### [18 de Marzo de 2026] Sprint 3: Ingesta Asíncrona Resiliente con Twilio y GCP Cloud Tasks

**Contexto:**
Se implementa el pipeline de entrada de mensajes (Ingestion Pipeline) para garantizar que el sistema pueda escalar a miles de mensajes concurrentes sin degradar la experiencia del usuario final ni agotar los recursos de la base de datos. La arquitectura separa la *Ingesta* (rápida, pública) del *Procesamiento* (lento, privado, transaccional).

#### 1. Decisión y Proceso Crítico: Validación de Firma HMAC-SHA1
*   **Decisión:** Uso estricto de `twilio.request_validator.RequestValidator` antes de cualquier procesamiento.
*   **El "Por Qué":** El endpoint del webhook es público por necesidad. Validar la firma `X-Twilio-Signature` garantiza que el mensaje fue enviado por Twilio y que el payload no ha sido alterado (Integridad).
*   **Alternativas Consideradas:**
    1.  **IP Whitelisting (Descartado):** Twilio publica sus rangos de IP, pero mantener esa lista sincronizada en firewalls de GCP es frágil y añade latencia de red.
    2.  **Secret Token en URL (Descartado):** Usar algo como `/webhook/?token=secreto`. Aunque es simple, el token viaja en logs de acceso y es propenso a ataques de *replay*.
*   **Elección:** La validación criptográfica HMAC-SHA1 es el estándar de oro (Industry Standard), no depende de la red y es inmune a ataques de interceptación.

#### 2. Decisión y Proceso Crítico: Ingesta Asíncrona (Buffered Inpust)
*   **Decisión:** La vista del webhook solo valida la firma y encola en `GCP Cloud Tasks` respondiendo en <100ms.
*   **El "Por Qué":** Twilio exige respuestas rápidas o cancela el webhook. Además, esto nos protege contra el *Thundering Herd Problem* (avalancha de peticiones).
*   **Alternativas Consideradas:**
    1.  **Procesamiento In-Process (Descartado):** Ejecutar la lógica de la FSM y guardado en DB dentro del mismo request. Riesgo: Si la DB está lenta (>5s), Twilio cierra la conexión y perdemos el mensaje.
    2.  **Redis + Celery (Descartado):** Viola la restricción de infraestructura *Zero-Idle-Cost*. Celery requiere un Worker encendido 24/7. Cloud Tasks es *Serverless* y escala a cero.
*   **Elección:** `GCP Cloud Tasks` actúa como un buffer de suavizado de tráfico (Traffic Smoothing) con reintentos automáticos y DLQ nativo.

#### 3. Decisión y Proceso Crítico: Idempotencia y Concurrencia (Worker Logic)
*   **Decisión:** Uso de `MessageSid` como llave única, chequeo temprano de existencia y `select_for_update()` en la sesión.
*   **El "Por Qué":** Los webhooks pueden llegar duplicados o desordenados. Necesitamos que procesar el mensaje 2 o 3 veces resulte en un único registro en la DB (Consistencia).
*   **Alternativas Consideradas:**
    1.  **get_or_create simple (Descartado):** En alta concurrencia, dos hilos pueden fallar el chequeo de "no existe" simultáneamente e intentar insertar, causando un `IntegrityError` ruidoso.
    2.  **Distributed Lock en Redis (Descartado):** Demasiada complejidad para nuestra escala.
*   **Elección:** El patrón `transaction.atomic()` + `select_for_update()` en Django aprovecha el bloqueo de filas nativo de PostgreSQL, garantizando orden sin añadir piezas móviles externas.

#### 4. Concepto de Ingeniería Consolidado: Desacoplamiento (Decoupling)
*   Se manifiesta al separar físicamente la entrada del mensaje (Webhook) de su efecto en el sistema (Worker), permitiendo que el sistema sea resiliente ante fallos parciales de la infraestructura.

#### 5. Deuda Técnica (KISS)
*   **Seguridad del Worker:** Actualmente se usa un `X-Internal-Secret`. Al escalar a alta sensibilidad, deberíamos migrar a validación OIDC nativa de Google (Service-to-Service auth), eliminando el secreto compartido.

### [21 de Marzo de 2026] Resolución de Bloqueos de Ingesta y Resiliencia en Desarrollo

**Contexto:**
Se completa con éxito el ciclo de ingesta de mensajes de Twilio a través de túneles `ngrok`. La sesión se enfocó en superar los desafíos de seguridad de red y las dependencias de infraestructura en la nube que impedían las pruebas funcionales.

#### 1. Decisión: Trust Automático de ngrok (DEBUG=True)
*   **Decisión:** Inyección dinámica de subdominios `.ngrok-free.dev` en `ALLOWED_HOSTS`.
*   **El "Por Qué":** Django bloquea peticiones de hosts desconocidos por seguridad. Automatizar este trust en modo `DEBUG` permite que el desarrollador reciba webhooks de la Sandbox de Twilio sin modificar constantemente el `.env`.
*   **Trade-off:** Se acepta una superficie de ataque ligeramente más amplia en local a cambio de una velocidad de desarrollo exponencialmente mayor.

#### 2. Decisión: Mock Local de Cloud Tasks (Graceful Degradation)
*   **Decisión:** Implementación de un bloque `try/except` robusto en el cliente de `google-cloud-tasks`.
*   **El "Por Qué":** La autenticación local con GCP (`gcloud`) puede presentar fallos de consentimiento o red. El sistema ahora detecta la falta de credenciales y, en modo `DEBUG`, emite un `WARNING` y continúa simulando el encolamiento (`mock-task-id`).
*   **Impacto:** Permite validar la lógica de ingesta y validación de firma sin depender de una cuenta de Google Cloud activa, desacoplando el desarrollo de la infraestructura.

#### 3. Anatomía del Edge Case: Fallo de Credenciales Cloud
*   **Definición:** El desarrollador no tiene sesión de GCP o el proyecto no existe.
*   **Mitigación:** Captura de `DefaultCredentialsError` y retorno de un task ID sintético. El webhook de Twilio recibe un `200 OK` (éxito en la ingesta) independientemente del estado de la cola en la nube.

#### 4. Concepto de Ingeniería Consolidado: Fault Tolerance / Graceful Degradation
*   **Teoría:** Capacidad de un sistema para mantener su funcionalidad principal (ingesta de mensajes) incluso cuando componentes secundarios (el sistema de colas real) fallan o no están disponibles en el entorno actual.

#### 5. Siguiente Paso (KISS)
*   Implementar el primer **Worker** (`/api/workers/process-message/`) para persistir la data del webhook en la base de datos de forma asíncrona, cerrando el "Vertical Slice" del Sprint 3.

#### ⚠️ Lista de Control: Código de Desarrollo (A limpiar antes de Prod)
Para evitar que la lógica de "bypass" llegue a producción, se deben auditar estos componentes:
*   **`core/settings.py`**: El bloque `if DEBUG` que añade dominios de ngrok a `ALLOWED_HOSTS`.
*   **`crm/services/cloud_tasks.py`**: Los bloques `try/except` en `enqueue_webhook_payload` que capturan fallos de GCP para retornar un `mock-task-id`.
*   **`.env`**: Las credenciales de la Sandbox de Twilio y la `DATABASE_URL` local. Asegurar migración a Secret Manager en GCP.
### [22 de Marzo de 2026] Sprint 5: Integración End-to-End, Despacho Local y Telemetría (AuditLog)

**Contexto:**
Se ha logrado cerrar el ciclo de vida completo del mensaje en el entorno de desarrollo. Hasta ahora, el sistema recibía el mensaje pero este moría en un mock silencioso ("black hole") del servicio de colas. La sesión se centró en "desbloquear" el flujo localmente y añadir la capa de observabilidad obligatoria mediante el `AuditLog`.

#### 1. Decisión y Proceso Crítico: Local Dispatcher via HTTP Loopback
*   **Decisión:** Refactorización de `crm/services/cloud_tasks.py` para que, en modo `DEBUG=True`, realice un POST HTTP real al endpoint del worker local (`/api/workers/process-message/`).
*   **El "Por Qué":** Para validar la lógica del worker (autenticación `X-Internal-Secret`, idempotencia y FSM) sin depender de la infraestructura de GCP. El uso de `requests` simula fielmente la naturaleza "Push" de Cloud Tasks.
*   **Trade-off:** Se eligió **Fidelidad vs. Simplicidad**. Podríamos haber llamado a la función del worker directamente en Python, pero eso ocultaría errores de serialización JSON o fallos en los headers de seguridad que solo aparecen en una comunicación HTTP real.

#### 2. Decisión y Proceso Crítico: Registro Inmutable de Eventos (AuditLog)
*   **Decisión:** Inserción de registros de auditoría para los eventos `SESSION_START` y `MSG_RECEIVED` dentro de la transacción atómica del worker.
*   **El "Por Qué":** Cumplimiento del requerimiento de telemetría exacta. El `AuditLog` actúa como la "caja negra" del CRM, permitiendo reconstruir por qué una FSM avanzó a cierto estado o detectar anomalías en la comunicación.
*   **Impacto:** Se garantiza la consistencia (ACID) entre el mensaje guardado y su registro de auditoría. Si uno de los dos falla, el `transaction.atomic()` hace rollback de ambos, evitando estados corruptos.

#### 3. Anatomía del Edge Case y Resiliencia
*   1. **Fallo de Red Local (Worker Apagado):** El dispatcher captura `requests.ConnectionError` y propaga el fallo al Webhook. Esto devuelve un `500` a Twilio, activando su mecanismo nativo de reintentos.
*   2. **Data Masking en Logs:** Se implementó una política estricta donde el `wa_id` y el `Body` del mensaje **nunca** se guardan en el `AuditLog` (solo metadatos como `body_length`), protegiendo la privacidad de los leads según `AGENTS.md §7`.

#### 4. Concepto de Ingeniería Consolidado: Event Sourcing / Audit Trail
*   **Teoría:** Registro de hechos históricos inmutables que describen cambios de estado en el sistema.
*   **Definición:** Cada interacción del usuario deja una huella digital no modificable en el `AuditLog`, facilitando el soporte técnico y la auditoría de seguridad sin comprometer la performance.

#### 5. Siguiente Paso (Sprint 6)
*   Implementación del **Dashboard de Ventas** en Angular. Usaremos RxJS para realizar HTTP Polling sobre la data que el worker ya está persistiendo exitosamente en PostgreSQL, permitiendo que el vendedor vea los mensajes en "tiempo real" simulado.

---

### [28 de Marzo de 2026] Hardening de Seguridad SRE y Blindaje de Producción

**Contexto:**
Con el "Cerebro Conversacional" (FSM) estabilizado, el sistema entra en su fase de preparación para despliegue en la nube (Production Readiness). Se requiere blindar la aplicación contra ataques de red comunes (Man-in-the-Middle, XSS, Host Poisoning) y asegurar que la comunicación con la base de datos en GCP sea cifrada y privada.

**Decisiones de Implementación Destacadas:**

1.  **Blindaje de Transporte (HTTPS/SSL & HSTS):**
    *   **Decisión:** Activación de `SECURE_SSL_REDIRECT` y `SECURE_HSTS_SECONDS` (1 año).
    *   **El Por Qué:** Forzamos a que cualquier navegador o cliente (incluyendo Twilio) use estrictamente canales cifrados. HSTS garantiza que el navegador del usuario "recuerde" esta preferencia, eliminando ataques de downgrade a HTTP.

2.  **Aislamiento de Perímetro (Allowed Hosts Dinámicos):**
    *   **Decisión:** Implementación de un filtro dinámico basado en `DEBUG`.
    *   **El Por Qué:** En local permitimos subdominios de `ngrok` para pruebas, pero en producción el servidor solo responderá a la lista blanca oficial definida en el `.env`, mitigando ataques de *HTTP Host Header Poisoning*.

3.  **Higiene y Protección del Navegador (Security Headers):**
    *   **Decisión:** Implementación de `X-Content-Type-Options: nosniff` y `X-XSS-Protection`.
    *   **El Por Qué:** Previene que el navegador ejecute scripts malintencionados disfrazados de otros tipos de archivo y activa filtros nativos contra Inyección de Código (XSS).

4.  **Seguridad de Datos en Tránsito (Database SSL Enforce):**
    *   **Decisión:** Configuración de `sslmode='verify-ca'` en el ORM utilizando la variable de entorno `DATABASE_SSL_CA` para la ruta del certificado.
    *   **El Por Qué:** Aseguramos que la conexión a Cloud SQL sea cifrada y verificada contra un certificado CA oficial. Si el tráfico intentara salir por IP pública sin SSL, la conexión fallará preventivamente, protegiendo las credenciales.

**Trade-offs (Simplicidad vs. Blindaje):**
*   Se decidió mantener estas reglas **desactivadas en desarrollo (`if DEBUG`)** para no obligar al equipo a gestionar certificados SSL locales o túneles complejos fuera de ngrok, manteniendo la agilidad de desarrollo.

**Concepto de Ingeniería Consolidado: Defense in Depth (Defensa en Profundidad)**
*   **Definición:** Aplicación de múltiples capas de seguridad (Red, Aplicación, Base de Datos) donde el fallo de una no compromete la integridad del sistema total.

**Siguiente Paso (Sprint 6):**
*   Inicio del desarrollo del Dashboard de Ventas en Angular 18, ahora con el canal de comunicación backend ya blindado para manejar tokens de identidad y perfiles de leads.

---

### [1 de Abril de 2026] Hardening de FSM: Resiliencia de Botones en Content Templates de Twilio

**Contexto:**
Al probar el flujo E2E con la Sandbox de Twilio usando Content Templates (botones interactivos), se detectó que la FSM volvía a preguntar infinitamente en los pasos `PAYMENT_METHOD` y `PURCHASE_INTENT`. El sistema leía correctamente el click del botón pero rechazaba la respuesta.

#### 1. Decisión: Body-first input extraction
*   **Decisión:** Reordenar la extracción del input del webhook para priorizar el campo `Body` por sobre `ButtonPayload`.
*   **El Por Qué:** Twilio Content Templates envían el título del botón en `Body` (ej: `"Retoma"`) y el ID técnico en `ButtonPayload` (ej: `"mp_retoma"`). El sistema procesaba `ButtonPayload` primero, pero la FSM esperaba el título legible.
*   **Trade-off:** `Body` puede contener texto libre inesperado. Se mitiga con el matching flexible (aliases) en cada paso de la FSM.

#### 2. Anatomía del Edge Case: Loop Infinito de FSM
*   **Caso 1 — Mismatch de IDs:** El Content Template de Twilio tiene `id="mp_retoma"` pero la FSM buscaba `"pm_retoma"`. Solución: se normalizó la extracción a `Body` que siempre trae el título en texto claro.
*   **Caso 2 — Alias faltante:** El botón enviado decía `"Este mes o más"` pero el código solo tenía `"mes o más"` en el tuple de matching. Solución: se agregaron todos los alias necesarios.

#### 3. Concepto de Ingeniería: Defensive Input Matching
Las FSMs de producción deben ser resilientes a variaciones de texto. Se establece el patrón: **siempre incluir el ID técnico + el título completo + variantes con/sin tildes y con/sin artículo inicial**.

#### 4. Deuda Técnica
Los textos de botones están hardcodeados en `fsm_engine.py`. Al escalar a múltiples idiomas, deberán externalizarse a un archivo de configuración o tabla de base de datos.

---

### [1 de Abril de 2026] Arquitectura Hexagonal: Aislamiento Total del Dominio de Negocio

**Contexto:**
`worker.py` había crecido a ~315 líneas mezclando autenticación, consultas ORM, lógica FSM y llamadas a Twilio en una sola función. Esto violaba el principio de Responsabilidad Única y hacía el testing prácticamente imposible sin levantar toda la infraestructura.

#### 1. Decisión: Ports & Adapters (Arquitectura Hexagonal)
*   **Decisión:** Separación en 4 capas: `domain/` (puro) → `adapters/` (ORM, Twilio, GCP) → `application/` (use cases) → `views/` (HTTP thin layer).
*   **El Por Qué:** Inversión de Dependencias (DIP). El dominio no conoce Django ni Twilio. Esto hace que el `ProcessMessageUseCase` sea testeable con stubs en memoria sin base de datos ni red.
*   **Alternativa descartada:** Mantener el worker monolítico con mocks parciales. Descartado porque los mocks deben reemplazar Django ORM entero, no solo partes.

#### 2. Componentes creados
| Archivo | Responsabilidad |
|:---|:---|
| `crm/domain/entities.py` | Dataclasses puras: `LeadEntity`, `SessionEntity`, `MessageEntity` |
| `crm/domain/ports.py` | Protocolos (interfaces): `LeadRepository`, `SessionRepository`, `MessageProvider`, `TaskQueue`, `AuditLogger` |
| `crm/adapters/database/repositories.py` | Implementación Django ORM de cada port de repositorio |
| `crm/adapters/messaging/twilio_adapter.py` | `TwilioMessageProvider` + `InMemoryMessageProvider` (stub para tests) |
| `crm/adapters/task_queue/gcp_tasks_adapter.py` | `GcpCloudTasksQueue` + `HttpDispatchQueue` (fallback local) |
| `crm/adapters/dependency_injection.py` | `DIContainer` singleton que resuelve las implementaciones concretas |
| `crm/application/use_cases/process_message.py` | `ProcessMessageUseCase`: orquesta el flujo completo |
| `crm/views/worker.py` | Vista delgada: autenticar → parsear → delegar → responder (≤72 líneas) |

#### 3. Regla SRE crítica: Red fuera de transacción
*   El `transaction.atomic()` cubre solo las escrituras a DB (lead, session, message, audit).
*   El `send_message()` de Twilio ocurre **después** del commit, nunca dentro. Esto evita que un timeout de red fuerce un rollback de datos ya válidos.

#### 4. Concepto: Inversión de Dependencias (DIP — SOLID)
*   El `ProcessMessageUseCase` depende de **abstracciones** (`LeadRepository`, `MessageProvider`) no de **implementaciones** (`DjangoLeadRepository`, `TwilioMessageProvider`). Esto permite cambiar Twilio por Meta WA o PostgreSQL por DynamoDB tocando solo un Adapter.

#### 5. Deuda Técnica
*   `SignatureValidationError` y `TaskQueueError` están definidas en los adapters concretos. Deberían vivir en `domain/ports.py` como excepciones de contrato para no acoplar la vista con detalles de implementación.

---

### [1 de Abril de 2026] Admin Local — Bypass del Middleware OIDC para `/admin/`

**Contexto:**
El `OIDCStatelessMiddleware` bloqueaba el acceso a `/admin/` de Django con `401 Unauthorized` porque buscaba un Bearer Token que el navegador no envía en requests normales al admin.

#### 1. Decisión: Whitelist de rutas públicas
*   **Decisión:** Agregar `/admin/` a `PUBLIC_PATH_PREFIXES` en el middleware.
*   **El Por Qué:** El admin de Django usa su propio sistema de sesiones (cookies), incompatible con OIDC stateless. En desarrollo local, el admin es la herramienta principal de inspección de datos.
*   **Riesgo controlado:** En producción, el admin seguirá protegido por la autenticación de Django (`is_staff=True`) y por el hecho de que no está expuesto públicamente (solo VPN o IP privada).

---

### [1 de Abril de 2026] Observabilidad SRE: Sentry + Métricas RED

**Contexto:**
El sistema ya tenía logging JSON estructurado con `trace_id` y `tenant_id`, pero carecía de alertas proactivas ante errores no controlados y de métricas agregadas de performance.

#### 1. Sentry SDK (`settings.py`)
*   **Decisión:** Integración de `sentry-sdk`. Se inicializa solo si `SENTRY_DSN` está definida en el `.env`.
*   **El Por Qué:** Los `logger.exception()` en los workers son reactivos (los buscas cuando ya sabes que algo falló). Sentry es proactivo: te alerta cuando ocurre una excepción no controlada en producción, con el stack trace completo y el contexto del request.
*   **Configuración zero-impact:** Si `SENTRY_DSN` está vacío (desarrollo local), Sentry no se inicializa. Sin overhead ni dependencias de red en local.

#### 2. Middleware de Métricas RED (`core/metrics.py`)
*   **Decisión:** Creación de `REDMetricsMiddleware` que emite un log JSON por cada request al logger dedicado `metrics.red`.
*   **Campos emitidos:** `path_pattern` (para evitar cardinalidad infinita por IDs en URL), `status_code`, `duration_ms`, `tenant_id`, `http_method`.
*   **Por Qué `path_pattern` y no `path_raw`:** Si la URL es `/api/leads/uuid-123/messages/`, usar el path raw genera infinitas series únicas en el dashboard. El patrón `api/leads/<uuid>/messages/` las agrupa en una sola métrica.
*   **Logger aislado:** `metrics.red` tiene `propagate: False` para que las métricas no contaminen los logs de negocio. Se puede enrutar a un sink diferente (BigQuery, GCP Log-based Metrics) sin modificar el resto del sistema.

#### 3. Concepto: Pillars of Observability — Logs + Metrics
*   **Logs** → ¿Qué pasó exactamente? (nivel de evento individual)
*   **Metrics RED** → ¿Cómo está el sistema en general? (Rate, Errors, Duration agregados)
*   Ambos son complementarios. Sin métricas, no sabes si hay un problema sistémico. Sin logs, no sabes por qué ocurrió.

---

### [1 de Abril de 2026] Contrato de API para el Dev de Frontend

**Contexto:**
Se inicia el desarrollo paralelo del frontend en Angular 18. Para que un segundo dev pueda trabajar de forma independiente sin depender del backend, se define el contrato de API como documento versionado.

#### Endpoints documentados en `docs/API_CONTRACT_FRONTEND.md`
| Endpoint | Método | Estado |
|:---|:---|:---|
| `/api/dashboard/leads/` | GET | ✅ Implementado |
| `/api/dashboard/leads/<id>/messages/` | GET | ❌ Pendiente |
| `/api/dashboard/leads/<id>/assign/` | POST | ❌ Pendiente |

#### Decisión de Polling vs WebSocket (V1)
*   **Polling RxJS cada 10 segundos** es suficiente para V1. Los leads no necesitan actualización en tiempo real sub-segundo.
*   WebSockets quedan como deuda técnica para V2 cuando el volumen supere los 50 leads activos simultáneos por vendedor.

#### Pendiente crítico antes del sprint de frontend
*   Instalar `django-cors-headers` para que Angular en `localhost:4200` pueda llamar al backend en `localhost:8000` sin errores CORS.

