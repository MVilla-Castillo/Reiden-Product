# AGENTS.md (CCRM-SAAS)

Este archivo es la **fuente de la verdad** operativa y arquitectónica para cualquier agente de IA (Claude, Gemini, Cursor, Copilot, etc.) que trabaje en este proyecto. **Debes leer y asimilar estas reglas antes de ejecutar cualquier cambio en el código.**

---

## 🏗️ 1. Resumen del Proyecto y Arquitectura Core
**Proyecto:** CCRM-SAAS (Customer Conversational Relationship Management).
**Objetivo:** Un CRM transaccional y conversacional (WhatsApp/Twilio) para Automotoras, gobernado por un motor de estados finitos (FSM) inquebrantable y telemetría exacta (AuditLog).

**Stack Tecnológico Infranqueable:**
- **Backend:** `Django 5.1` (Python Asíncrono).
- **Frontend:** `Angular 18+` (RxJS HTTP Polling).
- **Base de Datos:** `PostgreSQL 15+` (JSONB, Índices GIN y B-Tree).
- **Infra / Workers:** Todo serverless. `GCP Cloud Run` (Escalado a cero) + `GCP Cloud Tasks`. Prohibido Redis o Celery.
- **Autenticación:** OIDC Stateless Multi-Issuer (Microsoft Entra ID / Google Workspace). Prohibido guardar sesiones o contraseñas en DB.

---

## 💻 2. Tooling y Comandos del Entorno (Local)

**Gestión de Dependencias:** Únicamente `uv`. Prohibido usar `pip install`, `virtualenv` o `requirements.txt`.
```bash
# Sincronizar entorno
uv sync

# Añadir paquete
uv add <paquete>

# Ejecutar commands (ej. migraciones)
uv run python manage.py migrate
```

**Levantar el Entorno:**
Todo el ecosistema local se corre nativamente sobre Docker.
```bash
docker-compose up -d
```

**Testing:**
Uso riguroso de `pytest`. Prohibido el módulo `unittest` nativo de Django.
```bash
uv run pytest
```

---

## 📐 3. Convenciones de Código y Arquitectura (Skills)
Antes de modificar vistas (`views.py`) o modelos (`models.py`), el agente DEBE consultar y aplicar estrictamente las reglas definidas en la carpeta:
👉 **`.agents/skills/`**

**Reglas Críticas Resumidas:**
1. **Clean Architecture Lógica:** Cero lógica de negocio en las Vistas. Las Vistas desempaquetan el JSON y llaman a una función de servicio o de modelo.
2. **Multi-Tenancy por Diseño (RLS Lógica):** Prohibido usar `Model.objects.all()`. El filtro de privacidad empresarial es la regla número uno. Todo acceso a datos debe hacerse a través de Managers customizados que exijan el Tenant (ej. `Lead.tenant_objects.for_tenant(tenant)`).
3. **Inmutabilidad (Soft-Delete):** Estrictamente prohibido el método `.delete()` en la base de datos para entidades Core. Modifica el flag (`is_deleted = True`) y respáldalo con `ActiveManager`.
4. **Tipado Estricto (MyPy):** Código Python sin Tipado Moderno será rechazado de inmediato. 

---

## 🔒 4. Seguridad, Concurrencia y SRE (Site Reliability Engineering)

1. **Deadlocks y Thundering Herd:**
   * Al recibir Webhooks masivos y asíncronos (Cloud Tasks), debes apoyarte 100% en el bloqueo transaccional a nivel de fila de PostgreSQL. Las actualizaciones críticas del estado de la FSM DEBEN ir enrutadas dentro de bloques `transaction.atomic()` usando explícitamente `select_for_update()`.
   * Prohibido crear bloqueos o mutex lógicos a nivel de aplicación (ej. en memoria de Python o Redis inexistente).

2. **Aislamiento de API de Terceros:**
   * En los Webhooks de Twilio: **Prohibido el `get_or_create`**. Úsese Upsert Atómico (`INSERT ... ON CONFLICT DO NOTHING`).
   * Tests Unitarios: **Prohibido hacer llamadas HTTP reales a Twilio**. Usa `mock` rigurosamente.

3. **Inyección de Secretos:**
   * Prohibido hardcodear certificados o API Keys. Todo secreto proviene de `GCP Secret Manager` (Serverless) o del archivo `.env` (Local), inyectado a través del archivo de configuración global `core/settings.py`.

---

## 🔄 5. Flujo de Control de LLMs y Agentes
Si detectas un conflicto entre tu conocimiento base y lo descrito aquí (o en `docs/MASTER_SPEC.md` / `MER.md`), **estas instrucciones tienen prioridad absoluta.**

> **Alineación Final:** Eres un Agente SRE/Arquitecto Senior. No tomes atajos (como usar SQLite, o quitar tipado para ir más rápido). Nuestro objetivo prioritario es resiliencia transaccional y escalabilidad lineal a costo cero (Serverless).
