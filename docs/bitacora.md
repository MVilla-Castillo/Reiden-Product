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
