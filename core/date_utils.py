"""
core/date_utils.py — Utilidades compartidas para parsing de fechas.

Usadas por múltiples vistas y use cases para evitar duplicación.
"""

from __future__ import annotations

from datetime import date, timedelta


def parse_date_param(param: str | None, default: date | None = None) -> date | None:
    """Parsea un string ISO 8601 a date. Retorna default si inválido."""
    if not param:
        return default
    try:
        return date.fromisoformat(param)
    except ValueError:
        return default


def get_date_range_from_filter(
    date_filter: str | None,
) -> tuple[date, date] | None:
    """Retorna (date_from, date_to) basado en filtro rápido."""
    today = date.today()

    if date_filter == "today":
        return (today, today)
    elif date_filter == "week":
        start = today - timedelta(days=today.weekday())
        return (start, today)
    elif date_filter == "month":
        start = date(today.year, today.month, 1)
        return (start, today)
    elif date_filter == "year":
        start = date(today.year, 1, 1)
        return (start, today)
    elif date_filter == "all":
        return (date(1970, 1, 1), date.today())

    return None
