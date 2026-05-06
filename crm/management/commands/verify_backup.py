"""
crm/management/commands/verify_backup.py — Verifica que existe un backup
PostgreSQL reciente y no vacío.

Pensado para correr en cron (Cloud Scheduler / systemd timer) tras backup_db.sh.
Exit 0 si todo OK, !=0 si no hay backups, están vacíos o son obsoletos.
La salida es JSON línea-única para integración con alerting.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


_GSUTIL_LINE_RE = re.compile(
    r"^\s*(?P<size>\d+)\s+(?P<ts>\S+T\S+Z)\s+(?P<uri>gs://\S+)\s*$"
)


class Command(BaseCommand):
    help = "Verifica que existe un backup reciente y no vacío (local o GCS)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-age-hours",
            type=int,
            default=26,
            help="Edad máxima permitida del último backup, en horas (default 26).",
        )
        parser.add_argument(
            "--backup-dir",
            type=str,
            default="/var/backups/ccrm",
            help="Directorio local de backups (default /var/backups/ccrm).",
        )
        parser.add_argument(
            "--gcs-bucket",
            type=str,
            default=os.environ.get("GCS_BACKUP_BUCKET", ""),
            help="Bucket GCS (sin gs://). Si está vacío usa filesystem local.",
        )

    def handle(self, *args, **options):
        max_age_hours: int = options["max_age_hours"]
        backup_dir: str = options["backup_dir"]
        gcs_bucket: str = options["gcs_bucket"]

        if gcs_bucket:
            last = self._latest_from_gcs(gcs_bucket)
        else:
            last = self._latest_from_fs(backup_dir)

        if last is None:
            raise CommandError("Sin backups disponibles")

        path, size_bytes, last_modified = last
        if size_bytes <= 0:
            raise CommandError(f"Último backup vacío: {path}")

        now = datetime.now(timezone.utc)
        age = now - last_modified
        age_hours = age.total_seconds() / 3600.0

        if age_hours > max_age_hours:
            raise CommandError(
                f"Último backup tiene {age_hours:.1f}h, excede {max_age_hours}h ({path})"
            )

        self.stdout.write(
            json.dumps(
                {
                    "status": "ok",
                    "last_backup": path,
                    "age_hours": round(age_hours, 2),
                    "size_bytes": size_bytes,
                }
            )
        )

    def _latest_from_fs(self, backup_dir: str) -> tuple[str, int, datetime] | None:
        directory = Path(backup_dir)
        if not directory.is_dir():
            return None
        candidates = sorted(
            directory.glob("ccrm_*.dump"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return None
        latest = candidates[0]
        stat = latest.stat()
        last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        return str(latest), stat.st_size, last_modified

    def _latest_from_gcs(self, bucket: str) -> tuple[str, int, datetime] | None:
        prefix = f"gs://{bucket}/backups/"
        try:
            result = subprocess.run(
                ["gsutil", "ls", "-l", prefix],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
        except FileNotFoundError as exc:
            raise CommandError("gsutil no está instalado en el PATH") from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            raise CommandError(f"gsutil ls falló: {stderr or exc.returncode}") from exc

        latest: tuple[str, int, datetime] | None = None
        for line in result.stdout.splitlines():
            match = _GSUTIL_LINE_RE.match(line)
            if not match:
                continue
            size = int(match.group("size"))
            ts = match.group("ts").replace("Z", "+00:00")
            try:
                modified = datetime.fromisoformat(ts)
            except ValueError:
                continue
            uri = match.group("uri")
            if latest is None or modified > latest[2]:
                latest = (uri, size, modified)
        return latest
