#!/bin/bash
set -eo pipefail

echo "[entrypoint] Iniciando migraciones..."
python manage.py migrate --no-input
echo "[entrypoint] Migraciones completadas."

echo "[entrypoint] Recopilando archivos estáticos..."
python manage.py collectstatic --no-input --quiet
echo "[entrypoint] Estáticos listos."

exec "$@"