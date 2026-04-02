"""
crm/tests/test_dashboard_messages.py — Tests para los endpoints del Sprint 6.

Endpoints cubiertos:
- GET /api/dashboard/leads/<id>/messages/
- POST /api/dashboard/leads/<id>/messages/send/
- POST /api/dashboard/leads/<id>/assign/
- PATCH /api/dashboard/leads/<id>/reassign/
- PATCH /api/dashboard/leads/<id>/status/
- GET /api/dashboard/salespeople/
"""

import json
import uuid

import pytest
from django.test import Client, override_settings

from crm.adapters.messaging.twilio_adapter import TwilioMessageProvider
from crm.domain.ports import SendMessageRequest, SendMessageResult
from crm.models import AppUser, ChatSession, Lead, Message, Tenant


class MockMiddleware:
    """Middleware para inyectar el tenant en tests bypassando OIDC."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = Tenant.objects.order_by("created_at").first()
        return self.get_response(request)


@pytest.fixture
def salesperson(db, tenant: Tenant) -> AppUser:
    return AppUser.objects.create(
        email="vendedor@test.cl",
        oidc_sub="sp-sub-001",
        tenant=tenant,
        role=AppUser.Role.SALESPERSON,
        is_active=True,
    )


@pytest.fixture
def con_vendedor_session(
    db, tenant: Tenant, lead: Lead, salesperson: AppUser
) -> ChatSession:
    return ChatSession.objects.create(
        tenant=tenant,
        lead=lead,
        status=ChatSession.Status.CON_VENDEDOR,
        salesperson=salesperson,
    )


@pytest.fixture
def messages_in_session(
    db, tenant: Tenant, con_vendedor_session: ChatSession
) -> list[Message]:
    return [
        Message.objects.create(
            tenant=tenant,
            session=con_vendedor_session,
            provider_message_id=f"SM_INBOUND_{i}",
            direction="INBOUND",
            message_type="TEXT",
            body=f"Mensaje entrante {i}",
        )
        for i in range(1, 4)
    ]


@pytest.fixture
def mock_twilio_send(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_send(self, request: SendMessageRequest) -> SendMessageResult:
        return SendMessageResult(
            provider_message_id="SM_FAKE_OUTBOUND_001",
            success=True,
        )

    monkeypatch.setattr(TwilioMessageProvider, "send_message", fake_send)


OVERM = override_settings(
    MIDDLEWARE=["crm.tests.test_dashboard_messages.MockMiddleware"]
)


# ─────────────────────────────────────────────────────────
# GET /api/dashboard/leads/<id>/messages/
# ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_session_messages_returns_messages_ordered(
    client: Client,
    con_vendedor_session: ChatSession,
    messages_in_session: list[Message],
) -> None:
    with OVERM:
        response = client.get(
            f"/api/dashboard/leads/{con_vendedor_session.id}/messages/"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == str(con_vendedor_session.id)
    assert data["status"] == con_vendedor_session.status
    assert len(data["messages"]) == 3
    assert data["messages"][0]["body"] == "Mensaje entrante 1"
    assert data["messages"][2]["body"] == "Mensaje entrante 3"
    assert data["messages"][0]["direction"] == "INBOUND"


@pytest.mark.django_db
def test_session_messages_not_found(client: Client, tenant: Tenant) -> None:
    fake_id = uuid.uuid4()
    with OVERM:
        response = client.get(f"/api/dashboard/leads/{fake_id}/messages/")

    assert response.status_code == 404
    assert response.json()["error"] == "Sesión no encontrada"


@pytest.mark.django_db
def test_session_messages_invalid_uuid(client: Client) -> None:
    # Django's <uuid:...> URL converter rejects non-UUID patterns before hitting the view.
    # Django returns 404 for unmatched URLs.
    with OVERM:
        response = client.get("/api/dashboard/leads/not-a-uuid/messages/")

    assert response.status_code == 404


# ─────────────────────────────────────────────────────────
# POST /api/dashboard/leads/<id>/messages/send/
# ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_send_message_success(
    client: Client, con_vendedor_session: ChatSession, mock_twilio_send: None
) -> None:
    with OVERM:
        response = client.post(
            f"/api/dashboard/leads/{con_vendedor_session.id}/messages/send/",
            data=json.dumps({"body": "Hola desde el vendedor"}),
            content_type="application/json",
        )

    assert response.status_code == 200
    data = response.json()
    assert data["direction"] == "OUTBOUND"
    assert data["body"] == "Hola desde el vendedor"
    assert data["provider_message_sid"] == "SM_FAKE_OUTBOUND_001"

    msg = Message.objects.get(provider_message_id="SM_FAKE_OUTBOUND_001")
    assert msg.direction == "OUTBOUND"


@pytest.mark.django_db
def test_send_message_empty_body(
    client: Client, con_vendedor_session: ChatSession
) -> None:
    with OVERM:
        response = client.post(
            f"/api/dashboard/leads/{con_vendedor_session.id}/messages/send/",
            data=json.dumps({"body": ""}),
            content_type="application/json",
        )

    assert response.status_code == 400
    assert "body es requerido" in response.json()["error"]


@pytest.mark.django_db
def test_send_message_not_con_vendedor(
    client: Client, active_session: ChatSession
) -> None:
    with OVERM:
        response = client.post(
            f"/api/dashboard/leads/{active_session.id}/messages/send/",
            data=json.dumps({"body": "Hola"}),
            content_type="application/json",
        )

    assert response.status_code == 403
    assert "CON_VENDEDOR" in response.json()["error"]


@pytest.mark.django_db
def test_send_message_invalid_json(
    client: Client, con_vendedor_session: ChatSession
) -> None:
    with OVERM:
        response = client.post(
            f"/api/dashboard/leads/{con_vendedor_session.id}/messages/send/",
            data="not json",
            content_type="application/json",
        )

    assert response.status_code == 400


# ─────────────────────────────────────────────────────────
# POST /api/dashboard/leads/<id>/assign/
# ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_assign_lead_success(
    client: Client, active_session: ChatSession, salesperson: AppUser
) -> None:
    with OVERM:
        response = client.post(
            f"/api/dashboard/leads/{active_session.id}/assign/",
            data=json.dumps({"salesperson_id": str(salesperson.id)}),
            content_type="application/json",
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CON_VENDEDOR"
    assert data["salesperson_id"] == str(salesperson.id)

    active_session.refresh_from_db()
    assert active_session.salesperson_id == salesperson.id
    assert active_session.status == ChatSession.Status.CON_VENDEDOR


@pytest.mark.django_db
def test_assign_lead_salesperson_not_found(
    client: Client, active_session: ChatSession
) -> None:
    fake_id = uuid.uuid4()
    with OVERM:
        response = client.post(
            f"/api/dashboard/leads/{active_session.id}/assign/",
            data=json.dumps({"salesperson_id": str(fake_id)}),
            content_type="application/json",
        )

    assert response.status_code == 404
    assert "Vendedor no encontrado" in response.json()["error"]


@pytest.mark.django_db
def test_assign_lead_session_not_found(client: Client, salesperson: AppUser) -> None:
    fake_id = uuid.uuid4()
    with OVERM:
        response = client.post(
            f"/api/dashboard/leads/{fake_id}/assign/",
            data=json.dumps({"salesperson_id": str(salesperson.id)}),
            content_type="application/json",
        )

    assert response.status_code == 404


# ─────────────────────────────────────────────────────────
# PATCH /api/dashboard/leads/<id>/reassign/
# ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_reassign_lead_to_another(
    client: Client, con_vendedor_session: ChatSession, tenant: Tenant
) -> None:
    new_sp = AppUser.objects.create(
        email="nuevo@test.cl",
        oidc_sub="sp-sub-002",
        tenant=tenant,
        role=AppUser.Role.SALESPERSON,
        is_active=True,
    )

    with OVERM:
        response = client.patch(
            f"/api/dashboard/leads/{con_vendedor_session.id}/reassign/",
            data=json.dumps({"salesperson_id": str(new_sp.id)}),
            content_type="application/json",
        )

    assert response.status_code == 200
    data = response.json()
    assert data["salesperson_id"] == str(new_sp.id)
    assert data["status"] == "CON_VENDEDOR"

    con_vendedor_session.refresh_from_db()
    assert con_vendedor_session.salesperson_id == new_sp.id


@pytest.mark.django_db
def test_unassign_lead(client: Client, con_vendedor_session: ChatSession) -> None:
    with OVERM:
        response = client.patch(
            f"/api/dashboard/leads/{con_vendedor_session.id}/reassign/",
            data=json.dumps({"salesperson_id": None}),
            content_type="application/json",
        )

    assert response.status_code == 200
    data = response.json()
    assert data["salesperson_id"] is None
    assert data["status"] == "PENDING_ASSIGNMENT"

    con_vendedor_session.refresh_from_db()
    assert con_vendedor_session.salesperson_id is None
    assert con_vendedor_session.status == ChatSession.Status.PENDING_ASSIGNMENT


@pytest.mark.django_db
def test_reassign_missing_salesperson_id(
    client: Client, con_vendedor_session: ChatSession
) -> None:
    with OVERM:
        response = client.patch(
            f"/api/dashboard/leads/{con_vendedor_session.id}/reassign/",
            data=json.dumps({}),
            content_type="application/json",
        )

    assert response.status_code == 400
    assert "salesperson_id es requerido" in response.json()["error"]


# ─────────────────────────────────────────────────────────
# PATCH /api/dashboard/leads/<id>/status/
# ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_change_status_to_ganado(
    client: Client, con_vendedor_session: ChatSession
) -> None:
    with OVERM:
        response = client.patch(
            f"/api/dashboard/leads/{con_vendedor_session.id}/status/",
            data=json.dumps({"status": "GANADO"}),
            content_type="application/json",
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "GANADO"

    con_vendedor_session.refresh_from_db()
    assert con_vendedor_session.status == ChatSession.Status.GANADO


@pytest.mark.django_db
def test_change_status_to_perdido(
    client: Client, con_vendedor_session: ChatSession
) -> None:
    with OVERM:
        response = client.patch(
            f"/api/dashboard/leads/{con_vendedor_session.id}/status/",
            data=json.dumps({"status": "PERDIDO"}),
            content_type="application/json",
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PERDIDO"


@pytest.mark.django_db
def test_change_status_invalid(
    client: Client, con_vendedor_session: ChatSession
) -> None:
    with OVERM:
        response = client.patch(
            f"/api/dashboard/leads/{con_vendedor_session.id}/status/",
            data=json.dumps({"status": "BOT"}),
            content_type="application/json",
        )

    assert response.status_code == 400
    assert "Estado no válido" in response.json()["error"]


@pytest.mark.django_db
def test_change_status_session_not_found(client: Client, tenant: Tenant) -> None:
    fake_id = uuid.uuid4()
    with OVERM:
        response = client.patch(
            f"/api/dashboard/leads/{fake_id}/status/",
            data=json.dumps({"status": "GANADO"}),
            content_type="application/json",
        )

    assert response.status_code == 404


# ─────────────────────────────────────────────────────────
# GET /api/dashboard/salespeople/
# ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_salespeople_list(client: Client, tenant: Tenant, salesperson: AppUser) -> None:
    with OVERM:
        response = client.get("/api/dashboard/salespeople/")

    assert response.status_code == 200
    data = response.json()
    assert "salespeople" in data
    assert len(data["salespeople"]) == 1
    assert data["salespeople"][0]["email"] == "vendedor@test.cl"


@pytest.mark.django_db
def test_salespeople_excludes_other_roles(client: Client, tenant: Tenant) -> None:
    AppUser.objects.create(
        email="admin@test.cl",
        oidc_sub="admin-sub",
        tenant=tenant,
        role=AppUser.Role.ADMIN,
        is_active=True,
    )
    AppUser.objects.create(
        email="manager@test.cl",
        oidc_sub="manager-sub",
        tenant=tenant,
        role=AppUser.Role.MANAGER,
        is_active=True,
    )

    with OVERM:
        response = client.get("/api/dashboard/salespeople/")

    assert response.status_code == 200
    data = response.json()
    assert len(data["salespeople"]) == 0


@pytest.mark.django_db
def test_salespeople_excludes_other_tenant(client: Client, tenant: Tenant) -> None:
    other_tenant = Tenant.objects.create(
        phone_number_id="56999999999",
        nombre_legal="Other",
        rut_empresa="9-9",
    )
    AppUser.objects.create(
        email="other@test.cl",
        oidc_sub="other-sub",
        tenant=other_tenant,
        role=AppUser.Role.SALESPERSON,
        is_active=True,
    )

    with OVERM:
        response = client.get("/api/dashboard/salespeople/")

    assert response.status_code == 200
    data = response.json()
    assert len(data["salespeople"]) == 0
