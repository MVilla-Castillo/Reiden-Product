# Bitácora de Decisiones y Cambios Arquitectónicos (CCRM-SAAS)

*Nota: El contenido de esta bitácora está pensado para ser una fuente de la verdad técnica y, a su vez, material para futuras publicaciones de valor en redes como LinkedIn y X, detallando nuestro proceso de construcción y las decisiones de ingeniería detrás del CCRM-SAAS. Para esta bitacora.md aplicaremos Open/Closed Principle, se pueden agregar cosas pero no eliminar ni modificar las escrituras anteriores.*

Este documento actúa como un registro histórico (Architecture Decision Record - ADR) y bitácora de los cambios significativos implementados durante el ciclo de vida del desarrollo. Su propósito es documentar el *por qué* detrás de las implementaciones, sirviendo como guía para el equipo técnico presente y futuro.

## Registro de Cambios

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
