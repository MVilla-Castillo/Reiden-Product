"""
crm/domain/exceptions.py — Excepciones de dominio del CRM.

Define los errores que el dominio puede emitir hacia las capas externas.
Vivir aquí (y no en adapters/) garantiza que application y domain no
dependan de implementaciones concretas de infraestructura.

Convención: cada excepción es un tipo concreto para que las vistas puedan
mapear `tipo → status HTTP` sin depender del texto del mensaje. Reemplaza
patrones frágiles tipo `if "no encontrado" in str(e).lower(): return 404`.
"""

__all__ = [
    "MessagingError",
    "SignatureValidationError",
    "DomainNotFoundError",
    "DomainValidationError",
    "SessionNotFoundError",
    "SalespersonNotFoundError",
    "SalespersonUnavailableError",
    "RoutingNotEnabledError",
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


class DomainNotFoundError(Exception):
    """Recurso no encontrado en el dominio. Mapea a HTTP 404."""


class DomainValidationError(Exception):
    """Violación de regla de validación de dominio. Mapea a HTTP 400."""


class SessionNotFoundError(DomainNotFoundError):
    """La ChatSession solicitada no existe en el tenant."""


class SalespersonNotFoundError(DomainNotFoundError):
    """El vendedor solicitado no existe en el tenant."""


class SalespersonUnavailableError(DomainNotFoundError):
    """No hay vendedores activos disponibles para routing automático."""


class RoutingNotEnabledError(DomainValidationError):
    """El tenant no tiene routing AUTO habilitado."""
