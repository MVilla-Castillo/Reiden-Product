"""crm/views/_validation.py — Helpers tipados para parseo y validación de JSON.

Reemplazan el patrón disperso `body = json.loads(request.body)` seguido de
`body.get("campo", "").strip()`. Centralizan el manejo de:
  - JSON malformado o cuerpo no-objeto.
  - Campos requeridos ausentes o con tipo incorrecto.
  - Truncado/normalización mínima de strings.

Convención: cada helper retorna `(valor, error_response | None)`. Cuando
`error_response` es `None` el valor es válido. Esto permite a las vistas
hacer `value, err = require_str_field(...); if err: return err` sin repetir
el manejo de errores.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from django.http import HttpRequest, JsonResponse


def parse_json_body(
    request: HttpRequest,
) -> tuple[dict[str, Any] | None, JsonResponse | None]:
    """Decodifica `request.body` como JSON dict.

    Retorna (body, None) si parseo OK y es un objeto JSON.
    Retorna (None, 400 response) si falla.
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return None, JsonResponse({"error": "JSON inválido"}, status=400)
    if not isinstance(body, dict):
        return None, JsonResponse(
            {"error": "El cuerpo debe ser un objeto JSON"}, status=400
        )
    return body, None


def require_str_field(
    body: dict[str, Any],
    field: str,
    *,
    max_length: int | None = None,
    allow_empty: bool = False,
) -> tuple[str | None, JsonResponse | None]:
    """Extrae un campo string requerido, con .strip() y validación de tipo/longitud."""
    value = body.get(field)
    if value is None:
        return None, JsonResponse({"error": f"{field} es requerido"}, status=400)
    if not isinstance(value, str):
        return None, JsonResponse({"error": f"{field} debe ser un string"}, status=400)
    value = value.strip()
    if not allow_empty and not value:
        return None, JsonResponse(
            {"error": f"{field} es requerido y no puede estar vacío"}, status=400
        )
    if max_length is not None and len(value) > max_length:
        return None, JsonResponse(
            {"error": f"{field} excede el máximo de {max_length} caracteres"},
            status=400,
        )
    return value, None


def optional_str_field(
    body: dict[str, Any],
    field: str,
    *,
    max_length: int | None = None,
) -> tuple[str | None, JsonResponse | None]:
    """Extrae un campo string opcional. Retorna None si ausente o vacío tras strip()."""
    value = body.get(field)
    if value is None:
        return None, None
    if not isinstance(value, str):
        return None, JsonResponse({"error": f"{field} debe ser un string"}, status=400)
    value = value.strip()
    if not value:
        return None, None
    if max_length is not None and len(value) > max_length:
        return None, JsonResponse(
            {"error": f"{field} excede el máximo de {max_length} caracteres"},
            status=400,
        )
    return value, None


def optional_uuid_field(
    body: dict[str, Any],
    field: str,
) -> tuple[UUID | None, JsonResponse | None]:
    """Extrae un campo UUID opcional. Retorna None si la clave está ausente o es null."""
    if field not in body or body[field] is None:
        return None, None
    raw = body[field]
    if not isinstance(raw, str):
        return None, JsonResponse({"error": f"{field} inválido"}, status=400)
    try:
        return UUID(raw), None
    except ValueError:
        return None, JsonResponse({"error": f"{field} inválido"}, status=400)
