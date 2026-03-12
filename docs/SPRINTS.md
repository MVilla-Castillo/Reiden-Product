# 📅 SPRINTS.md - CCRM SAAS (Fase de Ignición)

## 👤 Equipo & Capacidad
- **Dev A + Dev B:** 4 horas/día totales (potenciadas por Agentes).
- **Metodología:** Docs-as-Code / AI-Driven Development.
- **Estado Global:** 🟢 Fase 1 - Cimientos.

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
- [x] Implementación de `OIDCStatelessMiddleware` con soporte JWT Multi-Issuer (Microsoft Entra ID & Google Workspace).
- [x] Mecanismo de re-fetch dinámico de JWKS para rotación de llaves resiliente.
- [ ] Registro de App en Azure Portal / Google Cloud Console y configuración de Scopes.
- [ ] Interceptor en Angular para manejo de `Access` y `Refresh Tokens`.
- [ ] UI de Login en Angular con MSAL / Google Identity Services.
- [ ] **Hito:** Login funcional con cuenta corporativa (@empresa.cl o @gmail) validando JWT sin sesiones en BD.

---

## 🧠 Etapa 2: El Cerebro Conversacional (4 Semanas)

### Sprint 3: Ingesta Asíncrona (1 Semana) - 🟢 "High Concurrency"
*Objetivo: Responder a Twilio en milisegundos sin sobrecargar infraestructura.*
- [ ] Endpoint de Webhook con validación de firma `X-Twilio-Signature`.
- [ ] Lógica de encolamiento directo a **GCP Cloud Tasks** (o emulador local).
- [ ] Respuesta `200 OK` inmediata a Twilio (< 500ms).
- [ ] **Hito:** Webhook Serverless que aísla la ingesta masiva de la lógica de negocio.

### Sprint 4: Máquina de Estados (FSM) y Transaccionalidad (3 Semanas) - 🔴 "Business Logic"
*Objetivo: El bot que califica leads solo con botones (ACID).*
- [ ] Implementación del Worker asíncrono para consumir Cloud Tasks (Upsert Atómico).
- [ ] Motor FSM (Estados de perfilamiento obligando entrada estructurada).
- [ ] Generador de mensajes `INTERACTIVE` (Lists y Buttons) para WhatsApp API.
- [ ] Lógica de `urgency_score` basada en el JSONB `fsm_answers` (`transaction.atomic()`).
- [ ] **Hito:** Lead calificado de inicio a fin sin intervención humana, con tests unitarios (>90%).

---

## 💻 Etapa 3: Interfaz y Despliegue Cloud (5 Semanas)

### Sprint 5: Dashboard de Ventas (2 Semanas) - 🔴 "Real-Time UI"
*Objetivo: Bandeja de entrada ágil (Pragmatismo V1).*
- [ ] Desarrollo de endpoints de listado y lectura (filtrados por Tenant).
- [ ] Frontend Angular 18+ con **RxJS (HTTP Polling)** para el stream de mensajes en cuasi-tiempo real.
- [ ] UI de "Ficha de Cliente" basada en las respuestas de la FSM (JSONB).
- [ ] Toggle de ruteo Gerencial (Manual/Auto).
- [ ] **Hito:** Vendedor recibe notificación y lead en tiempo real con 0 fricción operativa.

### Sprint 6: SRE, Cloud & Go-Live (3 Semanas) - 🔴 "Production Readiness"
*Objetivo: Estabilidad total, escalado a cero y monitoreo de nivel Big Tech.*
- [ ] Configuración de GCP Secret Manager e inyección (Cloud Run / Django).
- [ ] Configuración de **GCP Cloud Scheduler** para cierre automático de sesiones inactivas (>48h).
- [ ] Setup de deploy directo en GCP Cloud Run y Firebase Hosting (canario diferido a multi-tenant).
- [ ] Configuración de alertas en Sentry y GCP Logging (1% error threshold).
- [ ] **Hito:** Despliegue en dominio de producción con tráfico real operando a `--min-instances 0`.

---

## 📋 Backlog Pendiente (V2)
- [ ] Módulo de Gamificación avanzado.
- [ ] Exportación de reportes analíticos a PDF/Excel.
- [ ] Integración con Microsoft Graph para lectura de calendario.