# CCRM-SAAS

CRM multi-tenant para concesionarios automotrices con calificación automática de leads vía WhatsApp Business API (Twilio) y máquina de estados conversacional.

Stack: Django 5 + Postgres 15 + Uvicorn (ASGI) + Supabase Auth (OIDC ES256) + Twilio + Sentry · Gestionado con `uv` · Hexagonal/Ports & Adapters.

---

## Setup local

Requisitos: Python 3.12, Docker, [`uv`](https://docs.astral.sh/uv/).

```bash
# 1. Clonar dependencias y crear venv
uv sync

# 2. Copiar variables de entorno y completarlas
cp .env.example .env

# 3. Levantar Postgres
docker compose up -d db

# 4. Migraciones + estáticos
uv run python manage.py migrate
uv run python manage.py collectstatic --no-input

# 5. Servidor de desarrollo (con --reload via override)
docker compose up web
# o local:
uv run uvicorn core.asgi:application --host 0.0.0.0 --port 8000 --reload
```

`docker-compose.override.yml` añade `--reload` al servicio `web` solo en local; en producción se ignora.

---

## Variables de entorno

Todas listadas en `.env.example`. Críticas en producción:

| Variable | Generación |
|----------|-----------|
| `SECRET_KEY` | `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `INTERNAL_SECRET` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `WA_ID_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ENVIRONMENT` | `production` activa el fail-fast en `entrypoint.sh` (aborta si `DEBUG=true`) |
| `SUPABASE_URL`, `SUPABASE_JWT_SECRET` | desde el dashboard de Supabase |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | desde Twilio Console |
| `DATABASE_URL` | `postgres://user:pass@host:5432/db` (con `?sslmode=require` en prod) |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` | dominios reales del frontend |

En Railway estas variables se inyectan desde **Variables**; el `.env` solo se usa en local.

---

## Tests

```bash
# Suite completa con coverage (mínimo 80%)
uv run pytest

# Test específico de aislamiento multi-tenant
uv run pytest crm/tests/test_tenant_isolation.py -v
```

Config en `pyproject.toml > [tool.pytest.ini_options]`. Ver `crm/tests/CLAUDE.md` (si existe) para el ciclo TDD del proyecto.

---

## Lint y tipos

```bash
uv run ruff check .
uv run ruff format .
uv run mypy crm core
```

Mypy en modo `strict` (excluye `migrations/` y `tests/`).

---

## Pre-commit

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

Hooks: `gitleaks` (secretos), `ruff` (lint + format), `mypy` (tipos).

---

## Deploy

Imagen Docker (multi-stage uv → python slim). El `Dockerfile` corre como `appuser` (UID/GID 1001) y expone `/health/readiness` como healthcheck.

```bash
docker build -t ccrm:latest .
```

En Railway:
1. Conectar el repo, branch `main`.
2. Definir las variables de entorno listadas arriba.
3. El `entrypoint.sh` corre migraciones + collectstatic antes de arrancar Uvicorn.
4. Healthcheck path: `/health/readiness` (ejecuta `SELECT 1` contra la BD).

---

## CI

`.github/workflows/ci.yml` corre en cada push a `main` y `preproduccion/**` y en PRs a `main`:

1. **lint-typecheck** — ruff + mypy.
2. **test** — pytest con Postgres 15.5 como servicio, coverage ≥80%.
3. **security** — gitleaks + pip-audit (`--strict`) sobre el lockfile exportado.

---

## Documentación adicional

- [`AGENTS.md`](AGENTS.md) — guía operativa para Claude Code y otros agentes.
- [`docs/MASTER_SPEC.md`](docs/MASTER_SPEC.md) — especificación funcional.
- [`docs/MER.md`](docs/MER.md) — modelo entidad–relación.
- [`docs/API_CONTRACT_FRONTEND.md`](docs/API_CONTRACT_FRONTEND.md) — contrato con el frontend Angular.
- [`docs/SPRINTS.md`](docs/SPRINTS.md) — backlog priorizado.
- [`docs/casos_de_uso.md`](docs/casos_de_uso.md) — flujos end-to-end.
