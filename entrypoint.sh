#!/bin/bash
set -eo pipefail

# SRE Grade: Pre-flight check - Debug en producción no está permitido
if [ "${ENVIRONMENT:-}" = "production" ]; then
    if [ "${DEBUG:-false}" = "true" ] || [ "${DEBUG:-false}" = "1" ]; then
        echo "[entrypoint] ERROR: DEBUG=true no permitido en producción"
        exit 1
    fi
fi

echo "[entrypoint] Iniciando migraciones..."
python manage.py migrate --no-input
echo "[entrypoint] Migraciones completadas."

echo "[entrypoint] Recopilando archivos estáticos..."
python manage.py collectstatic --no-input --quiet
echo "[entrypoint] Estáticos listos."

exec "$@"