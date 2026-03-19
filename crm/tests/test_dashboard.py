import pytest
from django.test import Client
from crm.models import ChatSession, Lead

class MockMiddleware:
    """Middleware para inyectar el tenant en tests unitarios bypassando Auth."""
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        from crm.models import Tenant
        # Asume que el primer tenant creado (más antiguo) es el inyectado.
        request.tenant = Tenant.objects.order_by('created_at').first()
        return self.get_response(request)

@pytest.mark.django_db
def test_dashboard_leads_ordering_and_access(client: Client, active_session: ChatSession) -> None:
    # 1. ARRANGE
    tenant = active_session.tenant
    
    # Lead 1: Urgencia alta (Sesión activa)
    active_session.urgency_score = 100
    active_session.save()
    
    # Lead 2: Urgencia media
    lead_medium = Lead.objects.create(tenant=tenant, wa_id="56922222222", wa_id_hash="hash2")
    session_medium = ChatSession.objects.create(tenant=tenant, lead=lead_medium, status=ChatSession.Status.BOT, urgency_score=50)
    session_medium.fsm_answers = {'current_step': 'ASK_BUDGET'}
    session_medium.save()
    
    # Lead 3: De otro tenant (No debe aparecer)
    from crm.models import Tenant
    other_tenant = Tenant.objects.create(phone_number_id="56933333333", nombre_legal="Other", rut_empresa="2-2")
    lead_other = Lead.objects.create(tenant=other_tenant, wa_id="56944444444", wa_id_hash="hash3")
    ChatSession.objects.create(tenant=other_tenant, lead=lead_other, status=ChatSession.Status.BOT, urgency_score=100)

    # 2. ACT
    from django.urls import path
    from django.test import override_settings

    with override_settings(MIDDLEWARE=['crm.tests.test_dashboard.MockMiddleware']):
        response = client.get('/api/dashboard/leads/')

    # 3. ASSERT
    assert response.status_code == 200
    data = response.json()
    assert "leads" in data
    
    leads = data["leads"]
    assert len(leads) == 2 # Solo los del tenant principal
    
    # Validar que el de mayor urgency_score (100) va primero
    assert leads[0]["urgency_score"] == 100
    assert leads[1]["urgency_score"] == 50
    assert leads[0]["lead_phone"] == active_session.lead.wa_id
