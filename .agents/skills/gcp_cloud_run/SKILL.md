---
name: GCP Cloud Run (CCRM-SAAS)
description: Patrones y anti-patrones para desplegar Django en Cloud Run con escalado a cero, Dockerfile multi-stage, healthchecks y cloudbuild.yaml.
---

# ☁️ GCP Cloud Run (CCRM-SAAS)

Esta skill cubre el despliegue del backend Django en GCP Cloud Run con `--min-instances 0`. Aplica en el Sprint 6 (Go-Live) y al escribir el `Dockerfile` o `cloudbuild.yaml`.

## 1. Dockerfile Multi-Stage (Django + uv)

```dockerfile
# Stage 1: Builder
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Stage 2: Runtime (imagen mínima)
FROM python:3.12-slim
WORKDIR /app

# Copiar sólo el entorno virtual construido
COPY --from=builder /app/.venv /app/.venv
COPY core/ ./core/
COPY crm/ ./crm/
COPY manage.py ./

# Cloud Run usa PORT env variable (default: 8080)
ENV PORT=8080
ENV PATH="/app/.venv/bin:$PATH"

# Nunca correr como root en producción
RUN useradd --create-home appuser
USER appuser

CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8080", "--workers", "2"]
```

## 2. cloudbuild.yaml (CI/CD Canario)

```yaml
steps:
  # 1. Build de imagen inmutable
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/ccrm-backend:$COMMIT_SHA', '.']

  # 2. Push al registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/ccrm-backend:$COMMIT_SHA']

  # 3. Deploy con 0% de tráfico inicial (Canario)
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - run
      - deploy
      - ccrm-backend
      - --image=gcr.io/$PROJECT_ID/ccrm-backend:$COMMIT_SHA
      - --region=us-central1
      - --no-traffic           # No recibe tráfico hasta validación manual
      - --tag=canary-$COMMIT_SHA
      - --min-instances=0      # OBLIGATORIO: Escalado a cero
      - --max-instances=10
      - --memory=512Mi
      - --set-secrets=TWILIO_AUTH_TOKEN=TWILIO_AUTH_TOKEN:latest
      - --set-secrets=DB_PASSWORD=DB_PASSWORD:latest
```

## 3. Healthchecks Obligatorios

Estos endpoints DEBEN existir antes del despliegue a producción:

```python
# core/urls.py
from django.http import JsonResponse
from django.db import connection

def health_liveness(request):
    """Valida que Django arrancó. Usada por Cloud Run startup probe."""
    return JsonResponse({"status": "ok"})

def health_readiness(request):
    """Valida conexión real a PostgreSQL. Usada para enrutamiento de tráfico."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok", "db": "connected"})
    except Exception:
        return JsonResponse({"status": "error", "db": "unreachable"}, status=503)
```

## 4. Anti-Patterns Críticos de Cloud Run

| ❌ Anti-Pattern                              | ⚠️ Por qué es peligroso                                                  |
|----------------------------------------------|--------------------------------------------------------------------------|
| Escribir archivos grandes a `/tmp`           | `/tmp` es RAM. Causa OOM (Out Of Memory) y mata la instancia.            |
| Tareas de fondo sin Cloud Tasks              | Cloud Run congela la CPU entre requests. Los threads de fondo se detienen.|
| Llamadas a DB fuera del request lifecycle    | Conexiones quedan abiertas y saturan el pool → Connection Pool Exhaustion.|
| `--min-instances > 0` sin justificación      | Costo fijo mensual innecesario. Toleramos cold start de ~2s con Twilio.  |
| Secrets en variables de entorno como texto   | Usar `--set-secrets` en el deploy, nunca `--set-env-vars=API_KEY=xxx`.   |

## 5. Cold Start y Optimización

*   **Tolerancia al Cold Start:** Nuestro acuerdo es tolerar ~2 segundos de cold start porque Twilio reintenta automáticamente si el webhook no responde en 5 segundos. No requiere `--min-instances=1` (costo adicional).
*   **CPU Boost para arranque:** En el `cloudbuild.yaml` agregar `--cpu-boost` para que Cloud Run asigne más CPU durante el arranque del contenedor y reduzca el cold start.
*   **Uvicorn sobre Gunicorn:** Para Django asíncrono, usar `uvicorn core.asgi:application --workers 2` en lugar de gunicorn para aprovechar las vistas async.
