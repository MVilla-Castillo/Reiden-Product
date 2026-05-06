#!/usr/bin/env bash
# scripts/backup_db.sh — Backup PostgreSQL para CCRM-SAAS.
#
# Variables:
#   DATABASE_URL              postgres:// URL completa (requerida)
#   BACKUP_DIR                directorio local (default /var/backups/ccrm)
#   GCS_BACKUP_BUCKET         si está seteada, sube el dump a gs://<bucket>/backups/
#   BACKUP_RETENTION_DAYS     días a retener localmente (default 14)
#
# Salida: log JSON a stdout. Exit 0 OK, !=0 falla.
# Pensado para Cloud Scheduler / Railway cron / systemd timer.

set -euo pipefail

# NUNCA habilitar `set -x` aquí — DATABASE_URL contiene credenciales.

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo '{"event":"backup_error","detail":"DATABASE_URL no seteada"}' >&2
    exit 1
fi

TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/ccrm}"
GCS_BUCKET="${GCS_BACKUP_BUCKET:-}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

DUMP_TMP="${BACKUP_DIR}/ccrm_${TS}.dump.tmp"
DUMP_FINAL="${BACKUP_DIR}/ccrm_${TS}.dump"

# pg_dump custom format — comprimido, restaurable selectivamente con pg_restore.
if ! pg_dump --no-owner --no-acl --format=custom \
        --file="$DUMP_TMP" "$DATABASE_URL"; then
    rm -f "$DUMP_TMP"
    echo '{"event":"backup_error","detail":"pg_dump falló"}' >&2
    exit 2
fi

mv -f "$DUMP_TMP" "$DUMP_FINAL"
chmod 0640 "$DUMP_FINAL"

if [[ ! -s "$DUMP_FINAL" ]]; then
    echo '{"event":"backup_error","detail":"dump vacío"}' >&2
    rm -f "$DUMP_FINAL"
    exit 3
fi

SIZE="$(stat -c%s "$DUMP_FINAL" 2>/dev/null || stat -f%z "$DUMP_FINAL")"
GCS_PATH=""

if [[ -n "$GCS_BUCKET" ]]; then
    GCS_PATH="gs://${GCS_BUCKET}/backups/ccrm_${TS}.dump"
    if ! gsutil cp "$DUMP_FINAL" "$GCS_PATH" >/dev/null 2>&1; then
        echo "{\"event\":\"backup_error\",\"detail\":\"gsutil cp falló\",\"path\":\"${DUMP_FINAL}\"}" >&2
        exit 4
    fi
fi

# Retención local (errores no abortan el run, solo loguean).
find "$BACKUP_DIR" -maxdepth 1 -name 'ccrm_*.dump' -mtime "+${RETENTION_DAYS}" -delete \
    2>/dev/null || true

printf '{"event":"backup_ok","ts":"%s","path":"%s","size":%s,"gcs":"%s"}\n' \
    "$TS" "$DUMP_FINAL" "$SIZE" "$GCS_PATH"
