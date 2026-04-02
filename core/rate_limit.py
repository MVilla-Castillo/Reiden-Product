"""
core/rate_limit.py — Rate limiting in-memory (thread-safe) para endpoints sin Redis.

Implementa un sliding window counter simple basado en IP + tenant.
No requiere dependencias externas. Los contadores se limpian automáticamente
cada WINDOW segundos.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any


class _RateLimiter:
    """Singleton thread-safe para rate limiting."""

    _instance: _RateLimiter | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._cleanup_lock = threading.Lock()

    @classmethod
    def instance(cls) -> _RateLimiter:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def is_allowed(self, key: str, max_requests: int = 60, window: int = 60) -> bool:
        """
        Verifica si la clave puede realizar una petición más.

        Args:
            key: Identificador único (ej: IP o tenant_id).
            max_requests: Máximo de peticiones permitidas en la ventana.
            window: Ventana de tiempo en segundos.

        Returns:
            True si la petición está permitida, False si se excedió el límite.
        """
        now = time.time()
        cutoff = now - window

        with self._cleanup_lock:
            timestamps = self._requests[key]
            self._requests[key] = [ts for ts in timestamps if ts > cutoff]
            timestamps = self._requests[key]

        if len(timestamps) >= max_requests:
            return False

        with self._cleanup_lock:
            self._requests[key].append(now)

        return True

    def reset(self) -> None:
        """Limpia todos los contadores. Útil para tests."""
        with self._cleanup_lock:
            self._requests.clear()


def check_rate_limit(key: str, max_requests: int = 60, window: int = 60) -> bool:
    """Función helper para verificar rate limit."""
    return _RateLimiter.instance().is_allowed(key, max_requests, window)
