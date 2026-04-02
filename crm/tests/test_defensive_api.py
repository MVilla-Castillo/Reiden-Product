"""
crm/tests/test_defensive_api.py — Tests defensivos (RNF-44, RNF-25).

Validan:
1. Paginación estricta: rechazar requests sin limit o con limit excesivo.
2. Tolerancia a esquemas FSM corruptos: .get() con defaults, sin HTTP 500.
3. Validación de UUIDs malformados.
4. Payloads vacíos o incompletos.
"""

import json
import uuid

import pytest
from django.test import Client, override_settings

from crm.adapters.dependency_injection import DIContainer
from crm.adapters.messaging.twilio_adapter import InMemoryMessageProvider
from crm.models import AppUser, ChatSession, Lead, Message, Tenant
from core.crypto import encrypt


class MockMiddleware:
    """Middleware para inyectar el tenant en tests bypassando OIDC."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = Tenant.objects.order_by("created_at").first()
        return self.get_response(request)


OVERM = override_settings(MIDDLEWARE=["crm.tests.test_defensive_api.MockMiddleware"])


@pytest.fixture(autouse=True)
def _setup_di_for_defensive():
    DIContainer.reset()
    DIContainer.instance().set_message_provider(InMemoryMessageProvider())
    yield
    DIContainer.reset()


# ==============================================================================
# TEST: Paginación Rota — Sin parámetro limit → 400 Bad Request
# ==============================================================================
@pytest.mark.django_db
def test_messages_endpoint_rejects_missing_limit(
    client: Client, tenant: Tenant
) -> None:
    """
    ARRANGE: Sesión válida con mensajes.
    ACT: GET al historial de mensajes SIN parámetro limit.
    ASSERT: HTTP 400 Bad Request (no cargar toda la tabla en RAM).
    """
    lead = Lead.objects.create(
        tenant=tenant,
        wa_id=encrypt("56987654321"),
        wa_id_hash="def_hash_001",
    )
    session = ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.CON_VENDEDOR,
    )
    Message.objects.create(
        tenant=tenant,
        session=session,
        provider_message_id="SM_def_001",
        direction="INBOUND",
        message_type="TEXT",
        body="Hola",
    )

    with OVERM:
        response = client.get(f"/api/dashboard/leads/{session.id}/messages/")

    assert response.status_code == 400, (
        f"Se esperaba 400 sin parámetro limit, se obtuvo {response.status_code}"
    )


# ==============================================================================
# TEST: Paginación Rota — limit=10000 → 400 Bad Request
# ==============================================================================
@pytest.mark.django_db
def test_messages_endpoint_rejects_excessive_limit(
    client: Client, tenant: Tenant
) -> None:
    """
    ARRANGE: Sesión válida con mensajes.
    ACT: GET al historial con limit=10000 (excesivo).
    ASSERT: HTTP 400 Bad Request.
    """
    lead = Lead.objects.create(
        tenant=tenant,
        wa_id=encrypt("56987654321"),
        wa_id_hash="def_hash_002",
    )
    session = ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.CON_VENDEDOR,
    )

    with OVERM:
        response = client.get(
            f"/api/dashboard/leads/{session.id}/messages/?limit=10000"
        )

    assert response.status_code == 400, (
        f"Se esperaba 400 con limit=10000, se obtuvo {response.status_code}"
    )


# ==============================================================================
# TEST: Paginación Válida — limit=20 → 200 OK
# ==============================================================================
@pytest.mark.django_db
def test_messages_endpoint_accepts_valid_limit(client: Client, tenant: Tenant) -> None:
    """
    ARRANGE: Sesión con 5 mensajes.
    ACT: GET con limit=20.
    ASSERT: 200 OK con los 5 mensajes.
    """
    lead = Lead.objects.create(
        tenant=tenant,
        wa_id=encrypt("56987654321"),
        wa_id_hash="def_hash_003",
    )
    session = ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.CON_VENDEDOR,
    )
    for i in range(5):
        Message.objects.create(
            tenant=tenant,
            session=session,
            provider_message_id=f"SM_def_valid_{i}",
            direction="INBOUND",
            message_type="TEXT",
            body=f"Mensaje {i}",
        )

    with OVERM:
        response = client.get(f"/api/dashboard/leads/{session.id}/messages/?limit=20")

    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) == 5


# ==============================================================================
# TEST: Esquema FSM Corrupto — fsm_answers con llaves faltantes
# ==============================================================================
@pytest.mark.django_db
def test_scoring_handles_corrupt_fsm_answers_gracefully(
    tenant: Tenant,
) -> None:
    """
    ARRANGE: Sesión con fsm_answers corrupto (falta llave 'purchase_intent').
    ACT: Disparar procesamiento de mensaje que ejecuta FSM scoring.
    ASSERT: No lanza HTTP 500. Usa .get() con valor por defecto.
    """
    wa_id = "56987654321"
    lead = Lead.objects.create(
        tenant=tenant,
        wa_id=encrypt(wa_id),
        wa_id_hash="def_hash_fsm_corrupt",
    )
    ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.BOT,
        fsm_answers={
            "current_step": "PURCHASE_INTENT",
            "budget_range": "MAS_15M",
        },
    )

    client = Client()
    payload = {
        "MessageSid": "SMfsm_corrupt_001",
        "AccountSid": "ACtest",
        "From": "whatsapp:+56987654321",
        "To": "whatsapp:+56912345678",
        "WaId": "56987654321",
        "Body": "hoy",
        "ButtonText": "",
        "ButtonPayload": "pi_hoy",
        "MessageType": "text",
        "NumMedia": "0",
        "MediaUrl0": "",
        "MediaContentType0": "",
        "ListId": "",
        "ListTitle": "",
        "ReferralNumMedia": "0",
        "ReferralSourceType": "",
        "ReferralSourceUrl": "",
        "Timestamp": "2026-03-18T15:00:00Z",
    }

    response = client.post(
        "/api/workers/process-message/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_INTERNAL_SECRET="dev-internal-secret-change-in-prod",
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "processed", (
        "FSM scoring debe manejar llaves faltantes con .get() sin lanzar 500"
    )


# ==============================================================================
# TEST: Esquema FSM Vacío — fsm_answers = {} → No crash
# ==============================================================================
@pytest.mark.django_db
def test_scoring_handles_empty_fsm_answers(
    tenant: Tenant,
) -> None:
    """
    ARRANGE: Sesión con fsm_answers completamente vacío.
    ACT: Disparar procesamiento de mensaje.
    ASSERT: No lanza HTTP 500.
    """
    wa_id = "56987654321"
    lead = Lead.objects.create(
        tenant=tenant,
        wa_id=encrypt(wa_id),
        wa_id_hash="def_hash_empty_fsm",
    )
    ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.BOT,
        fsm_answers={},
    )

    client = Client()
    payload = {
        "MessageSid": "SMfsm_empty_001",
        "AccountSid": "ACtest",
        "From": "whatsapp:+56987654321",
        "To": "whatsapp:+56912345678",
        "WaId": "56987654321",
        "Body": "vt_suv",
        "ButtonText": "",
        "ButtonPayload": "vt_suv",
        "MessageType": "text",
        "NumMedia": "0",
        "MediaUrl0": "",
        "MediaContentType0": "",
        "ListId": "",
        "ListTitle": "",
        "ReferralNumMedia": "0",
        "ReferralSourceType": "",
        "ReferralSourceUrl": "",
        "Timestamp": "2026-03-18T15:00:00Z",
    }

    response = client.post(
        "/api/workers/process-message/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_INTERNAL_SECRET="dev-internal-secret-change-in-prod",
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "processed"


# ==============================================================================
# TEST: UUID Inválido en endpoint de mensajes → 404
# ==============================================================================
@pytest.mark.django_db
def test_invalid_uuid_in_messages_endpoint(client: Client) -> None:
    """
    ARRANGE: UUID malformado en la URL.
    ACT: GET al endpoint de mensajes.
    ASSERT: 404 (Django URL converter rechaza antes de llegar a la vista).
    """
    with OVERM:
        response = client.get("/api/dashboard/leads/not-a-uuid-hack/messages/")

    assert response.status_code == 404


# ==============================================================================
# TEST: Session no encontrada → 404
# ==============================================================================
@pytest.mark.django_db
def test_messages_session_not_found(client: Client, tenant: Tenant) -> None:
    """
    ARRANGE: UUID válido pero sesión inexistente.
    ACT: GET al endpoint de mensajes.
    ASSERT: 404.
    """
    fake_id = uuid.uuid4()
    with OVERM:
        response = client.get(f"/api/dashboard/leads/{fake_id}/messages/?limit=20")

    assert response.status_code == 404


# ==============================================================================
# TEST: Payload worker sin MessageSid → 400
# ==============================================================================
@pytest.mark.django_db
def test_worker_rejects_missing_message_sid() -> None:
    """
    ARRANGE: Payload JSON sin campo MessageSid.
    ACT: POST al worker.
    ASSERT: 400 Bad Request.
    """
    client = Client()
    payload = {
        "AccountSid": "ACtest",
        "From": "whatsapp:+56987654321",
        "To": "whatsapp:+56912345678",
        "Body": "Hola",
    }

    response = client.post(
        "/api/workers/process-message/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_INTERNAL_SECRET="dev-internal-secret-change-in-prod",
    )

    assert response.status_code == 400


# ==============================================================================
# TEST: JSON inválido al worker → 400
# ==============================================================================
@pytest.mark.django_db
def test_worker_rejects_invalid_json() -> None:
    """
    ARRANGE: Body no-JSON.
    ACT: POST al worker.
    ASSERT: 400 Bad Request.
    """
    client = Client()

    response = client.post(
        "/api/workers/process-message/",
        data="esto no es json {{{",
        content_type="application/json",
        HTTP_X_INTERNAL_SECRET="dev-internal-secret-change-in-prod",
    )

    assert response.status_code == 400
