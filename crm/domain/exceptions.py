"""
crm/domain/exceptions.py — Excepciones de dominio del CRM.

Define los errores que el dominio puede emitir hacia las capas externas.
Vivir aquí (y no en adapters/) garantiza que application y domain no
dependan de implementaciones concretas de infraestructura.
"""

__all__ = [
    "MessagingError",
    "SignatureValidationError",
]


class MessagingError(Exception):
    """Error de dominio: fallo al enviar un mensaje vía proveedor externo."""

    def __init__(self, message: str, provider_code: str | None = None) -> None:
        super().__init__(message)
        self.provider_code = provider_code


class SignatureValidationError(Exception):
    """Error de dominio: la firma del webhook no es válida o está ausente."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
