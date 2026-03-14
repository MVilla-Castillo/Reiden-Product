# 📅 SPRINTS.md - CCRM SAAS (Fase de Ignición)

## 👤 Equipo & Capacidad
- **Dev A (Backend/Infra) + Dev B (Frontend/UI):** 4 horas/día totales (potenciadas por Agentes).
- **Metodología:** Docs-as-Code / AI-Driven Development / Zero Merge Conflicts.
- **Estado Global:** 🟢 Fase 1 - Cimientos (En progreso).

---

## 🚀 Etapa 1: Cimientos e Identidad (2 Semanas)

### Sprint 1: Setup & Data Core (1 Semana) - 🟢 "The Fast Start"
*Objetivo: Tener el entorno listo y la base de datos blindada.*
- [x] Init del repo con `uv` y estructura de carpetas `backend/` y `frontend/`.
- [x] Definición de modelos Django: `Tenant`, `AppUser`, `Lead`, `ChatSession`, `Message`, `AuditLog`.
- [x] Implementación de Soft-Delete (`ActiveManager`) e Inmutabilidad.
- [x] Configuración de `Docker Compose` (PostgreSQL local, sin extras YAGNI).
- [x] Implementación de RLS (Row/Tenant Level Security) vía Custom Managers en Django.
- [x] **Hito:** Base de datos con aislamiento multi-tenant verificada.

### Sprint 2: OIDC Stateless Identity (Microsoft & Google) (1 Semana) - 🔴 "Deep Security"
*Objetivo: Login corporativo real sin contraseñas locales (Stateless Multi-Issuer).*
- [x] Refactor del modelo `AppUser` a estándares agnósticos (`oidc_sub`, `oidc_issuer`).
- [x] Implementación de `OIDCStatelessMiddleware` con soporte JWT Multi-Issuer (Microsoft Entra ID & Google Workspace) y `leeway=30`.
- [x] Mecanismo de re-fetch dinámico de JWKS para rotación de llaves resiliente.
- [ ] **(Dev A - Infra):** Registro de App en Azure Portal / Google Cloud Console y configuración de Scopes.
- [ ] **(Dev B - Front):** Interceptor en Angular para inyección de JWT en cabeceras de autorización.
- [ ] **(Dev B - Front):** UI de Login en Angular con MSAL / Google Identity Services (Botones de SSO).
- [ ] **Hito:** Login funcional validando JWT sin sesiones en BD, devolviendo un 401 limpio si el token expira o falla.

---

## 🧠 Etapa 2: El Cerebro Conversacional (4 Semanas)

### Sprint 3: Ingesta Asíncrona (1 Semana) - 🟢 "High Concurrency"
*Objetivo: Responder a Twilio en milisegundos sin sobrecargar infraestructura.*
- [ ] **(Dev A - Back):** Endpoint de Webhook con validación de firma `X-Twilio-Signature`.
- [ ] **(Dev A - Back):** Lógica de encolamiento directo a **GCP Cloud Tasks** (o emulador local).
- [ ] **(Dev A - Back):** Respuesta `200 OK` inmediata a Twilio (< 500ms).
- [ ] **Hito:** Webhook Serverless que aísla la ingesta masiva de la lógica de negocio.

### Sprint 4: Máquina de Estados (FSM) y Transaccionalidad (3 Semanas) - 🔴 "Business Logic"
*Objetivo: El bot que califica leads solo con botones (ACID).*
- [ ] **(Dev B - Back/Services):** Worker asíncrono para consumir Cloud Tasks con Idempotencia (validando `twilio_sid`).
- [ ] **(Dev A - Back/Domain):** Motor FSM con `select_for_update()` para evitar Race Conditions (Upsert Atómico).
- [ ] **(Dev A - Back/Integrations):** Generador de mensajes `INTERACTIVE` (Lists/Buttons) para WhatsApp API.
- [ ] **(Dev A - Back/Domain):** Lógica de `urgency_score` guardada en JSONB (con índice GIN en la DB).
- [ ] **Hito:** Lead calificado de inicio a fin sin intervención humana, con tests unitarios (>90%).

---

## 💻 Etapa 3: Interfaz y Despliegue Cloud (5 Semanas)

### Sprint 5: Dashboard de Ventas (2 Semanas) - 🔴 "Real-Time UI"
*Objetivo: Bandeja de entrada ágil (Pragmatismo V1).*
- [ ] **(Dev A - Back/API):** Desarrollo de endpoints GET de listado y lectura (filtrados por Tenant, sin queries N+1).
- [ ] **(Dev B - Front):** Frontend Angular 18+ con **RxJS (HTTP Polling + Backoff)** simulando datos con JSON Server hasta que la API esté lista.
- [ ] **(Dev B - Front):** UI de "Ficha de Cliente" basada en las respuestas de la FSM (JSONB).
- [ ] **(Dev B - Front):** Toggle de ruteo Gerencial (Manual/Auto).
- [ ] **Hito:** Vendedor recibe notificación y lead en tiempo real con 0 fricción operativa.

### Sprint 6: SRE, Cloud & Go-Live (3 Semanas) - 🔴 "Production Readiness"
*Objetivo: Estabilidad total, escalado a cero y monitoreo de nivel Big Tech.*
- [ ] **(Dev A - Infra):** Configuración de GCP Secret Manager e inyección (Cloud Run / Django).
- [ ] **(Dev B - Infra/Front):** Deploy en Firebase Hosting y Configuración de **GCP Cloud Scheduler** para cierre de sesiones inactivas.
- [ ] **(Dev A - Infra):** Setup de deploy directo en GCP Cloud Run (Scale to Zero, concurrencia ajustada).
- [ ] **(Dev A - Infra):** Configuración de alertas en Sentry y GCP Logging (1% error threshold).
- [ ] **Hito:** Despliegue en dominio de producción con tráfico real.