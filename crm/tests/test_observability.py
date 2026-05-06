"""
crm/tests/test_observability.py — Tests de la capa de observabilidad SRE.

Coverage:
- TraceIDMiddleware: X-Trace-ID presente en todas las respuestas
- CORS_EXPOSE_HEADERS: X-Trace-ID accesible por el browser
- handler404/handler500: respuestas JSON con trace_id (no HTML de Django)
- _sentry_before_send: inyecta trace_id y tenant_id en eventos Sentry
- CSRF_TRUSTED_ORIGINS: PATCH desde localhost:4200 no produce 403 CSRF
"""

import pytest
from django.test import Client, override_settings

from core.log_utils import trace_id_var, tenant_id_var
from core.settings import _sentry_before_send


# ==============================================================================
# Fixtures
# ==============================================================================


class _PassthroughMiddleware:
    """Middleware mínimo que no requiere tenant — para tests de infraestructura."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)


# Middleware stack mínimo: conserva TraceIDMiddleware + CorsMiddleware + CSRF,
# pero elimina OIDC para tests de infraestructura.
_INFRA_MIDDLEWARE = [
    "core.log_utils.TraceIDMiddleware",
    "core.metrics.REDMetricsMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

INFRA = override_settings(MIDDLEWARE=_INFRA_MIDDLEWARE)


# ==============================================================================
# TraceIDMiddleware — X-Trace-ID en respuestas
# ==============================================================================


@pytest.mark.django_db
@INFRA
def test_trace_id_header_present_in_response(client: Client) -> None:
    """
    ASSERT: Toda respuesta lleva X-Trace-ID generado por TraceIDMiddleware.
    """
    response = client.get("/health/liveness")
    assert "X-Trace-ID" in response, (
        "X-Trace-ID debe estar en la respuesta — TraceIDMiddleware no está activo"
    )
    trace_id = response["X-Trace-ID"]
    assert trace_id and trace_id != "-", "X-Trace-ID no debe estar vacío o ser '-'"


@pytest.mark.django_db
@INFRA
def test_trace_id_propagated_from_request_header(client: Client) -> None:
    """
    ASSERT: Si el cliente envía X-Trace-ID, el middleware lo usa (no genera uno nuevo).
    """
    custom_trace = "test-trace-abc-123"
    response = client.get("/health/liveness", HTTP_X_TRACE_ID=custom_trace)
    assert response["X-Trace-ID"] == custom_trace, (
        "El middleware debe preservar el X-Trace-ID recibido"
    )


# ==============================================================================
# CORS_EXPOSE_HEADERS — X-Trace-ID accesible por el browser Angular
# ==============================================================================


@pytest.mark.django_db
@INFRA
def test_cors_exposes_trace_id_header(client: Client) -> None:
    """
    ASSERT: X-Trace-ID está en Access-Control-Expose-Headers para que Angular pueda leerlo.
    El browser bloquea headers que no están explícitamente expuestos.
    """
    response = client.get(
        "/health/liveness",
        HTTP_ORIGIN="http://localhost:4200",
    )
    expose = response.get("Access-Control-Expose-Headers", "")
    assert "X-Trace-ID" in expose, (
        f"X-Trace-ID debe estar en Access-Control-Expose-Headers. "
        f"Valor actual: '{expose}'"
    )


# ==============================================================================
# handler404 — JSON con trace_id (no HTML de Django)
# ==============================================================================


@pytest.mark.django_db
@override_settings(
    MIDDLEWARE=_INFRA_MIDDLEWARE,
    DEBUG=False,  # handlers 404/500 solo se activan con DEBUG=False
)
def test_handler404_returns_json_with_trace_id(client: Client) -> None:
    """
    ASSERT: URLs inexistentes devuelven JSON {error, trace_id}, no la página HTML de Django.
    Crítico para APIs — el frontend no puede parsear HTML como JSON.
    """
    response = client.get("/esta-ruta-no-existe-jamas/")
    assert response.status_code == 404
    assert response["Content-Type"].startswith("application/json"), (
        "handler404 debe devolver application/json, no text/html"
    )
    data = response.json()
    assert "trace_id" in data, "La respuesta 404 debe incluir trace_id para debugging"
    assert "error" in data


@pytest.mark.django_db
@override_settings(
    MIDDLEWARE=_INFRA_MIDDLEWARE,
    DEBUG=False,
)
def test_handler404_trace_id_matches_request(client: Client) -> None:
    """
    ASSERT: El trace_id del 404 corresponde al X-Trace-ID del request.
    """
    custom_trace = "trace-404-test-xyz"
    response = client.get(
        "/ruta-inexistente/",
        HTTP_X_TRACE_ID=custom_trace,
    )
    assert response.status_code == 404
    data = response.json()
    assert data["trace_id"] == custom_trace, (
        "El trace_id del 404 debe ser el mismo que el del request"
    )


# ==============================================================================
# handler500 — JSON con trace_id
# ==============================================================================


@pytest.mark.django_db
@override_settings(
    MIDDLEWARE=_INFRA_MIDDLEWARE,
    DEBUG=False,
    ROOT_URLCONF="crm.tests.urls_500_fixture",
)
def test_handler500_returns_json_with_trace_id() -> None:
    """
    ASSERT: Errores internos devuelven JSON {error, trace_id}, no la página HTML de Django.
    Usamos raise_request_exception=False para que Django invoque handler500.
    """
    client = Client(raise_request_exception=False)
    response = client.get("/trigger-500/")
    assert response.status_code == 500
    assert response["Content-Type"].startswith("application/json"), (
        "handler500 debe devolver application/json, no text/html"
    )
    data = response.json()
    assert "trace_id" in data
    assert "error" in data


# ==============================================================================
# _sentry_before_send — inyecta trace_id y tenant_id como tags
# ==============================================================================


def test_sentry_before_send_injects_trace_id() -> None:
    """
    ASSERT: _sentry_before_send añade trace_id a los tags del evento cuando hay trace activo.
    """
    token = trace_id_var.set("my-trace-123")
    try:
        event = {}
        result = _sentry_before_send(event, {})
        assert result["tags"]["trace_id"] == "my-trace-123"
    finally:
        trace_id_var.reset(token)


def test_sentry_before_send_injects_tenant_id() -> None:
    """
    ASSERT: _sentry_before_send añade tenant_id cuando hay tenant activo en el contexto.
    """
    t_token = trace_id_var.set("trace-abc")
    ten_token = tenant_id_var.set("tenant-uuid-999")
    try:
        event = {}
        result = _sentry_before_send(event, {})
        assert result["tags"]["tenant_id"] == "tenant-uuid-999"
    finally:
        trace_id_var.reset(t_token)
        tenant_id_var.reset(ten_token)


def test_sentry_before_send_skips_default_trace() -> None:
    """
    ASSERT: Cuando trace_id es '-' (no hay request activo), no se añade el tag.
    Evita contaminar eventos de background con trace_id vacío.
    """
    event = {}
    result = _sentry_before_send(event, {})
    assert "trace_id" not in result.get("tags", {}), (
        "No debe inyectar trace_id cuando el valor es '-' (fuera de request)"
    )


def test_sentry_before_send_preserves_existing_tags() -> None:
    """
    ASSERT: _sentry_before_send no sobreescribe tags ya existentes en el evento.
    """
    token = trace_id_var.set("new-trace")
    try:
        event = {"tags": {"existing_tag": "value"}}
        result = _sentry_before_send(event, {})
        assert result["tags"]["existing_tag"] == "value"
        assert result["tags"]["trace_id"] == "new-trace"
    finally:
        trace_id_var.reset(token)


def test_sentry_before_send_returns_event() -> None:
    """
    ASSERT: _sentry_before_send siempre retorna el evento (nunca None).
    Retornar None descartaría el evento en Sentry.
    """
    result = _sentry_before_send({}, {})
    assert result is not None


# ==============================================================================
# CSRF_TRUSTED_ORIGINS — PATCH desde localhost:4200 no produce 403
# ==============================================================================


@pytest.mark.django_db
@override_settings(
    MIDDLEWARE=_INFRA_MIDDLEWARE,
    CSRF_TRUSTED_ORIGINS=["http://localhost:4200"],
    DEBUG=True,
)
def test_csrf_trusted_origin_allows_patch_from_angular(client: Client) -> None:
    """
    ASSERT: PATCH desde http://localhost:4200 no produce 403 por CSRF.
    Este es el bug que se reportó: 'Origin checking failed - localhost:4200'.
    El 405 es correcto aquí (la ruta /health/ no acepta PATCH) — lo que importa es que no sea 403.
    """
    response = client.patch(
        "/health/liveness",
        content_type="application/json",
        data="{}",
        HTTP_ORIGIN="http://localhost:4200",
        HTTP_REFERER="http://localhost:4200/dashboard",
    )
    assert response.status_code != 403, (
        f"PATCH desde localhost:4200 no debe producir 403 CSRF. "
        f"Status: {response.status_code}"
    )
