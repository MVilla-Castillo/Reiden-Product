# 📅 SPRINTS.md - CCRM SAAS (Fase de Ignición)

## 👤 Equipo & Capacidad
- **Dev A & Dev B:** 4 horas/día totales (potenciadas por Agentes).
- **Metodología:** Docs-as-Code / Vertical Slicing (DDD) / Zero Merge Conflicts.
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

### Sprint 2: OIDC Stateless Identity (1 Semana) - 🔴 "Deep Security"
*Objetivo: Login corporativo real sin contraseñas locales. (Dueño: Dev A)*
- [x] Refactor del modelo `AppUser` a estándares agnósticos (`oidc_sub`, `oidc_issuer`).
- [x] Implementación de `OIDCStatelessMiddleware` con JWT Multi-Issuer y `leeway=30`.
- [x] Mecanismo de re-fetch dinámico de JWKS.
- [ ] **(Dev A - Dominio Identidad / Infra):** Registro de App en Azure/GCP y configuración de Scopes.
- [ ] **(Dev A - Dominio Identidad / Front):** UI de Login Angular con SDKs y configuración de Interceptor HTTP para JWT.
- [ ] **Hito:** Login funcional End-to-End. Dev A entrega el módulo de autenticación cerrado.

---

## 🧠 Etapa 2: El Cerebro Conversacional (4 Semanas)

### Sprint 3: Ingesta Asíncrona & Workers (1 Semana) - 🟢 "High Concurrency"
*Objetivo: Responder a Twilio en milisegundos. (Dueño: Dev B)*
- [ ] **(Dev B - Dominio Infra Chat / Back):** Endpoint de Webhook (firma `X-Twilio-Signature`) y encolamiento a GCP Cloud Tasks.
- [ ] **(Dev B - Dominio Infra Chat / Back):** Worker asíncrono para consumir tareas validando idempotencia (`twilio_sid`).
- [ ] **Hito:** Ingesta serverless robusta. Dev B garantiza que ningún mensaje se pierda o duplique.

### Sprint 4: Máquina de Estados (FSM) (3 Semanas) - 🔴 "Business Logic"
*Objetivo: El bot que califica leads. (Dueño: Dev A)*
- [ ] **(Dev A - Dominio Lógica Chat / Back):** Motor FSM con `select_for_update()` para evitar Race Conditions (Upsert Atómico).
- [ ] **(Dev A - Dominio Lógica Chat / Back):** Integración API WhatsApp (Mensajes Interactivos).
- [ ] **(Dev A - Dominio Lógica Chat / Back):** Lógica `urgency_score` en DB (asegurando índice GIN en JSONB).
- [ ] **Hito:** Lead calificado automáticamente. Dev A cierra el flujo de negocio del bot.

---

## 💻 Etapa 3: Interfaz y Despliegue Cloud (5 Semanas)

### Sprint 5: Dashboard de Ventas (2 Semanas) - 🔴 "Real-Time UI"
*Objetivo: Bandeja de entrada ágil.*
- [ ] **(Dev B - Dominio Tiempo Real / Fullstack):** Endpoints GET (Listado optimizado sin N+1) + Front Angular RxJS (HTTP Polling + Backoff).
- [ ] **(Dev A - Dominio Gestión / Fullstack):** Endpoints GET/POST (Detalle de Lead) + Front Angular "Ficha de Cliente" y Toggle de ruteo Gerencial.
- [ ] **Hito:** Dashboard operativo. Dev B hace la vista general, Dev A hace la vista de detalle.

### Sprint 6: SRE, Cloud & Go-Live (3 Semanas) - 🔴 "Production Readiness"
*Objetivo: Despliegue Big Tech.*
- [ ] **(Dev A - Infra Cloud):** GCP Secret Manager + Deploy en Cloud Run (Scale to Zero).
- [ ] **(Dev B - Infra Front/Ops):** Deploy Firebase Hosting + GCP Cloud Scheduler + Sentry.
- [ ] **Hito:** Producción estable.