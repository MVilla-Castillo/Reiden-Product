"""
core/crypto.py — Cifrado Fernet (AES-128-CBC + HMAC-SHA256) para datos sensibles (PII).

La clave se inyecta vía GCP Secret Manager (env var WA_ID_ENCRYPTION_KEY).
Si la key no está configurada, las operaciones FALLAN explícitamente.
Nunca se retorna plaintext silenciosamente.
"""

from __future__ import annotations

import logging

from cryptography.fernet import Fernet, InvalidToken

__all__ = [
    "encrypt",
    "decrypt",
    "generate_key",
    "EncryptionKeyMissingError",
    "reset_fernet",
]

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


class EncryptionKeyMissingError(Exception):
    """La clave de cifrado no está configurada. Error de infraestructura."""


def _get_fernet() -> Fernet:
    """Lazy initialization. Lanza EncryptionKeyMissingError si no hay key."""
    global _fernet
    if _fernet is not None:
        return _fernet

    from django.conf import settings

    key = getattr(settings, "WA_ID_ENCRYPTION_KEY", "")
    if not key:
        raise EncryptionKeyMissingError(
            "WA_ID_ENCRYPTION_KEY no configurada. "
            "Genera una con: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )

    try:
        _fernet = Fernet(key.encode("utf-8"))
        return _fernet
    except Exception as exc:
        logger.exception("Error al inicializar Fernet. Key inválida.")
        raise EncryptionKeyMissingError(f"Key de cifrado inválida: {exc}") from exc


def encrypt(plaintext: str) -> str:
    """Cifra un string. Lanza EncryptionKeyMissingError si no hay key."""
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """Descifra un string. Lanza EncryptionKeyMissingError si no hay key."""
    fernet = _get_fernet()
    try:
        return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.warning(
            "Token inválido al descifrar. Posible dato no cifrado o key cambiada.",
            extra={"component_name": "crypto"},
        )
        raise


def generate_key() -> str:
    """Genera una nueva clave Fernet. Usar solo en scripts de setup."""
    return Fernet.generate_key().decode("utf-8")


def reset_fernet() -> None:
    """Limpia el caché del cifrador. Útil para tests con override_settings."""
    global _fernet
    _fernet = None
