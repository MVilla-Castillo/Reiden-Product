# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Determinismo total para el path
ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ─────────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Agregamos el path al inicio
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Crear usuario sin privilegios
RUN addgroup --system appuser && adduser --system --group appuser

# Copiamos el venv y el código con los permisos correctos
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app /app

# Mover al usuario seguro
USER appuser

# Usamos el path absoluto para máxima resiliencia
CMD ["/app/.venv/bin/uvicorn", "core.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]