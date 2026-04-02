"""
crm/adapters/messaging/twilio_adapter.py — Adapter de Twilio para el port MessageProvider.

Implementa el protocolo MessageProvider usando el SDK de Twilio.
Incluye también un stub InMemoryMessageProvider para tests sin dependencias externas.

Excepciones de dominio: los errores crudos de la API de Twilio nunca se exponen
al caller. Se traducen a MessagingError o SignatureValidationError.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from django.conf import settings
from twilio.base.exceptions import TwilioRestException
from twilio.http.http_client import TwilioHttpClient
from twilio.request_validator import RequestValidator
from twilio.rest import Client

from crm.domain.ports import (
    MessageProvider,
    SendMessageRequest,
    SendMessageResult,
    SignatureValidationRequest,
    SignatureValidationResult,
)

logger = logging.getLogger(__name__)


class MessagingError(Exception):
    """Error de dominio: fallo al enviar un mensaje vía proveedor externo."""

    def __init__(self, message: str, provider_code: str | None = None) -> None:
        super().__init__(message)
        self.provider_code = provider_code


class SignatureValidationError(Exception):
    """Error de dominio: la firma del webhook no es válida o está ausente."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class TwilioMessageProvider(MessageProvider):
    """Adapter concreto que usa el SDK de Twilio para enviar mensajes y validar firmas."""

    def send_message(self, request: SendMessageRequest) -> SendMessageResult:
        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
            logger.error(
                "Twilio credentials missing. No se puede enviar mensaje.",
                extra={"component_name": "twilio_adapter"},
            )
            raise MessagingError(
                "TWILIO_ACCOUNT_SID o TWILIO_AUTH_TOKEN no configurados"
            )

        http_client = TwilioHttpClient(timeout=5.0)
        client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
            http_client=http_client,
        )

        to_whatsapp = (
            f"whatsapp:+{request.to_number}"
            if not request.to_number.startswith("whatsapp:")
            else request.to_number
        )

        from_number = request.from_number or "14155238886"
        from_whatsapp = (
            f"whatsapp:+{from_number}"
            if not from_number.startswith("whatsapp:")
            else from_number
        )

        params: dict[str, Any] = {
            "from_": from_whatsapp,
            "to": to_whatsapp,
        }

        if request.content_sid:
            params["content_sid"] = request.content_sid
            if request.content_variables:
                params["content_variables"] = request.content_variables
        else:
            body_text = request.text
            if request.interactive_payload:
                options = [
                    btn["title"]
                    for btn in request.interactive_payload.get("buttons", [])
                ]
                if options:
                    body_text += "\n\nOpciones:\n- " + "\n- ".join(options)
            params["body"] = body_text

        try:
            message = client.messages.create(**params)
            logger.info(
                "Mensaje enviado correctamente",
                extra={
                    "message_sid": message.sid,
                    "component_name": "twilio_adapter",
                },
            )
            return SendMessageResult(
                provider_message_id=message.sid,
                success=True,
            )
        except TwilioRestException as e:
            logger.error(
                "Error Twilio al enviar mensaje",
                extra={
                    "twilio_status": e.status,
                    "twilio_code": e.code,
                    "twilio_msg": e.msg,
                    "component_name": "twilio_adapter",
                },
            )
            raise MessagingError(
                message=f"Fallo al enviar mensaje: {e.msg}",
                provider_code=str(e.code) if e.code else None,
            ) from e

    def validate_signature(
        self, request: SignatureValidationRequest
    ) -> SignatureValidationResult:
        auth_token: str = getattr(settings, "TWILIO_AUTH_TOKEN", "")

        if not auth_token:
            logger.error(
                "TWILIO_AUTH_TOKEN no configurado. Rechazando Webhook.",
                extra={"component_name": "twilio_adapter"},
            )
            raise SignatureValidationError("TWILIO_AUTH_TOKEN no configurado")

        validator = RequestValidator(auth_token)
        is_valid = validator.validate(
            request.url,
            request.post_data,
            request.signature,
        )

        if not is_valid:
            logger.warning(
                "Firma X-Twilio-Signature inválida. Posible intento de spoofing.",
                extra={"component_name": "twilio_adapter"},
            )

        return SignatureValidationResult(is_valid=is_valid)


class InMemoryMessageProvider(MessageProvider):
    """
    Stub para tests. Registra mensajes en memoria y acepta todas las firmas.
    No hace llamadas HTTP reales.
    """

    def __init__(self) -> None:
        self._sent_messages: list[SendMessageRequest] = []

    @property
    def sent_messages(self) -> list[SendMessageRequest]:
        return list(self._sent_messages)

    def clear(self) -> None:
        self._sent_messages.clear()

    def send_message(self, request: SendMessageRequest) -> SendMessageResult:
        self._sent_messages.append(request)
        return SendMessageResult(
            provider_message_id=f"SIM_{uuid.uuid4().hex[:8]}",
            success=True,
        )

    def validate_signature(
        self, request: SignatureValidationRequest
    ) -> SignatureValidationResult:
        return SignatureValidationResult(is_valid=True)
