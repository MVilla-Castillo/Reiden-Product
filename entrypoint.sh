#!/bin/bash
set -eo pipefail

# SRE Grade: Pre-flight check - Debug en producción no está permitido
if [ "${ENVIRONMENT:-}" = "production" ]; then
    if [ "${DEBUG:-false}" = "true" ] || [ "${DEBUG:-false}" = "1" ]; then
        echo "[entrypoint] ERROR: DEBUG=true no permitido en producción"
        exit 1
    fi
fi

# Migraciones opt-in. En prod (Railway) se setea RUN_MIGRATIONS_ON_BOOT=false
# y las migraciones corren en un release-job aparte para evitar que N réplicas
# intenten migrar simultáneamente. En dev queda true por default.
if [ "${RUN_MIGRATIONS_ON_BOOT:-true}" = "true" ]; then
    echo "[entrypoint] Iniciando migraciones..."
    /app/.venv/bin/python manage.py migrate --no-input
    echo "[entrypoint] Migraciones completadas."
else
    echo "[entrypoint] Migraciones omitidas (RUN_MIGRATIONS_ON_BOOT=false)."
fi

# collectstatic se ejecuta en build-time (ver Dockerfile). No correr en boot.

exec "$@"