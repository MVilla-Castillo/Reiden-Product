"""
crm/tests/test_fsm.py — Tests del Motor FSM (TDD).

Patrón: AAA (Arrange, Act, Assert).
Validamos el nuevo flujo estricto (MASTER_SPEC):
1. INITIAL -> VEHICLE_TYPE
2. VEHICLE_TYPE -> PAYMENT_METHOD
3. PAYMENT_METHOD -> BUDGET_RANGE
4. BUDGET_RANGE -> PURCHASE_INTENT
5. PURCHASE_INTENT -> QUALIFIED (Score acumulativo)
"""
import pytest
from crm.models import ChatSession
from crm.services.fsm_engine import advance_fsm
from crm.services.fsm_types import (
    FSMStep, VehicleType, PaymentMethod, BudgetRange, PurchaseIntent
)

@pytest.mark.django_db
def test_fsm_initial_message_moves_to_vehicle_type(active_session: ChatSession) -> None:
    assert active_session.fsm_answers == {}
    reply = advance_fsm(active_session, "Quiero info")

    assert active_session.fsm_answers.get('current_step') == FSMStep.VEHICLE_TYPE
    assert "auto buscas" in reply.get('text', '').lower()

@pytest.mark.django_db
def test_fsm_vehicle_type_moves_to_payment_method(active_session: ChatSession) -> None:
    active_session.fsm_answers = {'current_step': FSMStep.VEHICLE_TYPE}
    reply = advance_fsm(active_session, "Una SUV")

    assert active_session.fsm_answers.get('current_step') == FSMStep.PAYMENT_METHOD
    assert active_session.fsm_answers.get('vehicle_type') == VehicleType.SUV
    assert "prefieres pagarlo" in reply.get('text', '').lower()

@pytest.mark.django_db
def test_fsm_payment_method_moves_to_budget(active_session: ChatSession) -> None:
    active_session.fsm_answers = {
        'current_step': FSMStep.PAYMENT_METHOD,
        'vehicle_type': VehicleType.SUV
    }
    reply = advance_fsm(active_session, "A crédito por favor")

    assert active_session.fsm_answers.get('current_step') == FSMStep.BUDGET_RANGE
    assert active_session.fsm_answers.get('payment_method') == PaymentMethod.CREDITO
    assert "presupuesto estimado" in reply.get('text', '').lower()

@pytest.mark.django_db
def test_fsm_budget_moves_to_purchase_intent(active_session: ChatSession) -> None:
    active_session.fsm_answers = {
        'current_step': FSMStep.BUDGET_RANGE,
        'payment_method': PaymentMethod.CREDITO
    }
    reply = advance_fsm(active_session, "15m o más")

    assert active_session.fsm_answers.get('current_step') == FSMStep.PURCHASE_INTENT
    assert active_session.fsm_answers.get('budget_range') == BudgetRange.MAS_15M
    assert "tienes planificada" in reply.get('text', '').lower()

@pytest.mark.django_db
def test_fsm_purchase_intent_completes_qualification_with_accumulated_score(active_session: ChatSession) -> None:
    active_session.fsm_answers = {
        'current_step': FSMStep.PURCHASE_INTENT,
        'payment_method': PaymentMethod.CREDITO,
        'budget_range': BudgetRange.MAS_15M
    }
    reply = advance_fsm(active_session, "Hoy")

    assert active_session.fsm_answers.get('current_step') == FSMStep.QUALIFIED
    assert active_session.fsm_answers.get('purchase_intent') == PurchaseIntent.HOY
    # El requerimiento explícito: Score = 100 (Hoy) + 20 (Crédito) + 40 (15M+) = 160
    assert active_session.urgency_score == 160
    assert "asesor" in reply.get('text', '').lower()

from crm.models import ChatSession, Message

# ... existing code ...

@pytest.mark.django_db
def test_fsm_multimedia_is_rejected_with_warning(active_session: ChatSession) -> None:
    active_session.fsm_answers = {'current_step': FSMStep.VEHICLE_TYPE}
    # Enviar una imagen
    reply1 = advance_fsm(active_session, "", Message.Type.IMAGE)
    assert active_session.fsm_answers.get('error_count') == 1
    assert "texto" in reply1.get('text', '').lower()
    
    # Segunda imagen
    reply2 = advance_fsm(active_session, "", Message.Type.AUDIO)
    assert active_session.fsm_answers.get('error_count') == 2
    assert "texto" in reply2.get('text', '').lower()

    # Tercer error consecutivo de multimedia, se queda en silencio absoluto
    reply3 = advance_fsm(active_session, "", Message.Type.IMAGE)
    assert active_session.fsm_answers.get('error_count') == 3
    assert getattr(reply3, 'text', None) is None
