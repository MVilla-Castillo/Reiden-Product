"""
crm/services/rate_limiter.py — Rate limiter DB-based para webhook Twilio.

Sin Redis: usa PostgreSQL con INSERT ... ON CONFLICT DO UPDATE atómico.
Ventana deslizante de 60 segundos por tenant + wa_id_hash.

Diseño anti race-condition (A3 del audit pre-prod):
  1. Dentro de transaction.atomic(), primero hacemos el UPSERT que incrementa
     el contador. Ese INSERT/UPDATE adquiere row-lock en la fila del
     (tenant_id, wa_id_hash, window_start) → cualquier request concurrente
     del mismo remitente espera nuestro commit antes de tocar la misma fila.
  2. Después del UPSERT leemos el total real de la ventana con SUM().
  3. Si el total excede el límite, hacemos `raise RateLimitExceeded` para que
     el `transaction.atomic()` se aborte y el UPSERT se revierta. Así nunca
     contamos un request por encima del límite.

Esto reemplaza el patrón anterior (read-then-write) que tenía un gap entre
el aggregate() inicial y el INSERT, permitiendo que dos requests concurrentes
del mismo remitente pasaran ambos la validación con count=N-1 y resultaran
en N+1 inserts totales.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta

from django.db import connection, models, transaction
from django.utils import timezone

from crm.models import WebhookRateLimit

_RATE_LIMIT_TABLE = WebhookRateLimit._meta.db_table


class RateLimitExceeded(Exception):
    """El remitente excedió el limite de requests por ventana."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s")


def check_rate_limit(
    tenant_id: uuid.UUID,
    wa_id_raw: str,
    max_requests: int = 30,
    window_seconds: int = 60,
) -> bool:
    """
    Verifica y registra un request de rate limit de forma atómica.

    Args:
        tenant_id: UUID del tenant.
        wa_id_raw: WaId crudo del remitente (se hashea internamente).
        max_requests: Maximo requests por ventana (default 30/min).
        window_seconds: Duración de la ventana en segundos (default 60).

    Returns:
        True si el request está permitido (y ya se contabilizó).

    Raises:
        RateLimitExceeded: Si se excedió el limite (y el incremento se revierte).
    """
    wa_id_hash = hashlib.sha256(wa_id_raw.encode()).hexdigest()
    now = timezone.now()
    current_window = now.replace(microsecond=0)
    window_start_cutoff = now - timedelta(seconds=window_seconds)

    table = _RATE_LIMIT_TABLE

    with transaction.atomic():
        # 1) UPSERT primero: incrementa de forma atómica y toma row-lock en
        # la fila (tenant_id, wa_id_hash, current_window). Cualquier request
        # concurrente con el mismo remitente queda bloqueado hasta que esta
        # transacción commitee o haga rollback.
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {table}
                    (tenant_id, wa_id_hash, window_start, request_count)
                VALUES (%s, %s, %s, 1)
                ON CONFLICT (tenant_id, wa_id_hash, window_start)
                DO UPDATE SET request_count = {table}.request_count + 1
                """,
                [str(tenant_id), wa_id_hash, current_window],
            )

        # 2) Releemos el total real de la ventana DESPUÉS del incremento.
        # Como el UPSERT mantiene row-lock, otros requests concurrentes están
        # bloqueados y el SUM refleja el estado consistente.
        count = (
            WebhookRateLimit.objects.filter(
                tenant_id=tenant_id,
                wa_id_hash=wa_id_hash,
                window_start__gte=window_start_cutoff,
            ).aggregate(total=models.Sum("request_count"))["total"]
            or 0
        )

        # 3) Si excedió, raise → atomic rollback → el UPSERT se revierte.
        if count > max_requests:
            oldest = (
                WebhookRateLimit.objects.filter(
                    tenant_id=tenant_id,
                    wa_id_hash=wa_id_hash,
                    window_start__gte=window_start_cutoff,
                )
                .order_by("window_start")
                .first()
            )

            if oldest is not None:
                retry_after = (
                    int(
                        (
                            oldest.window_start
                            + timedelta(seconds=window_seconds)
                            - now
                        ).total_seconds()
                    )
                    + 1
                )
            else:
                retry_after = window_seconds

            raise RateLimitExceeded(retry_after=max(retry_after, 1))

    return True


def cleanup_old_rate_limits(hours: int = 1) -> int:
    """Elimina registros de rate limit más antiguos que `hours`."""
    cutoff = timezone.now() - timedelta(hours=hours)
    deleted, _ = WebhookRateLimit.objects.filter(window_start__lt=cutoff).delete()
    return deleted
