"""
crm/tests/test_fsm.py — Tests del Motor FSM (TDD).

Patrón: AAA (Arrange, Act, Assert).
La FSM ahora es dominio puro: usa FSMContext/FSMResult, no modelos Django.
"""

import pytest

from crm.services.fsm_engine import FSMContext, FSMResult, advance_fsm
from crm.services.fsm_types import (
    FSMStep,
    VehicleType,
    PaymentMethod,
    BudgetRange,
    PurchaseIntent,
)


def _make_context(
    current_step: str | None = None,
    fsm_answers: dict | None = None,
    status: str = "BOT",
) -> FSMContext:
    return FSMContext(
        current_step=current_step,
        fsm_answers=fsm_answers or {},
        status=status,
    )


def test_fsm_initial_message_moves_to_vehicle_type() -> None:
    ctx = _make_context()
    result = advance_fsm(ctx, "Quiero info")

    assert result.next_step == FSMStep.VEHICLE_TYPE
    assert "auto buscas" in result.text.lower()


def test_fsm_greeting_restarts_flow_at_start() -> None:
    ctx = _make_context(
        current_step=FSMStep.VEHICLE_TYPE,
        fsm_answers={"current_step": FSMStep.VEHICLE_TYPE},
    )
    result = advance_fsm(ctx, "Hola que tal")

    assert result.next_step == FSMStep.VEHICLE_TYPE
    assert "auto buscas" in result.text.lower()
    assert result.updated_fsm_answers.get("error_count") == 0


def test_fsm_vehicle_type_moves_to_payment_method() -> None:
    ctx = _make_context(
        current_step=FSMStep.VEHICLE_TYPE,
        fsm_answers={"current_step": FSMStep.VEHICLE_TYPE},
    )
    result = advance_fsm(ctx, "vt_suv")

    assert result.next_step == FSMStep.PAYMENT_METHOD
    assert result.updated_fsm_answers.get("vehicle_type") == VehicleType.SUV
    assert "prefieres pagarlo" in result.text.lower()


def test_fsm_payment_method_moves_to_budget() -> None:
    ctx = _make_context(
        current_step=FSMStep.PAYMENT_METHOD,
        fsm_answers={
            "current_step": FSMStep.PAYMENT_METHOD,
            "vehicle_type": VehicleType.SUV,
        },
    )
    result = advance_fsm(ctx, "pm_credito")

    assert result.next_step == FSMStep.BUDGET_RANGE
    assert result.updated_fsm_answers.get("payment_method") == PaymentMethod.CREDITO
    assert "presupuesto estimado" in result.text.lower()


def test_fsm_budget_moves_to_purchase_intent() -> None:
    ctx = _make_context(
        current_step=FSMStep.BUDGET_RANGE,
        fsm_answers={
            "current_step": FSMStep.BUDGET_RANGE,
            "payment_method": PaymentMethod.CREDITO,
        },
    )
    result = advance_fsm(ctx, "br_mas15")

    assert result.next_step == FSMStep.PURCHASE_INTENT
    assert result.updated_fsm_answers.get("budget_range") == BudgetRange.MAS_15M
    assert "tienes planificada" in result.text.lower()


def test_fsm_purchase_intent_completes_qualification_with_accumulated_score() -> None:
    ctx = _make_context(
        current_step=FSMStep.PURCHASE_INTENT,
        fsm_answers={
            "current_step": FSMStep.PURCHASE_INTENT,
            "payment_method": PaymentMethod.CREDITO,
            "budget_range": BudgetRange.MAS_15M,
        },
    )
    result = advance_fsm(ctx, "pi_hoy")

    assert result.next_step == FSMStep.QUALIFIED
    assert result.updated_fsm_answers.get("purchase_intent") == PurchaseIntent.HOY
    assert result.urgency_score == 160
    assert result.new_status == "PENDING_ASSIGNMENT"
    assert "asesor" in result.text.lower()
    assert result.is_terminal is True


def test_fsm_multimedia_is_rejected_with_warning() -> None:
    ctx = _make_context(
        current_step=FSMStep.VEHICLE_TYPE,
        fsm_answers={"current_step": FSMStep.VEHICLE_TYPE},
    )
    reply1 = advance_fsm(ctx, "", "IMAGE")
    assert reply1.updated_fsm_answers.get("error_count") == 1
    assert "texto" in reply1.text.lower()

    ctx2 = FSMContext(
        current_step=FSMStep.VEHICLE_TYPE,
        fsm_answers=reply1.updated_fsm_answers,
        status="BOT",
        error_count=reply1.updated_fsm_answers.get("error_count", 0),
    )
    reply2 = advance_fsm(ctx2, "", "AUDIO")
    assert reply2.updated_fsm_answers.get("error_count") == 2
    assert "texto" in reply2.text.lower()

    ctx3 = FSMContext(
        current_step=FSMStep.VEHICLE_TYPE,
        fsm_answers=reply2.updated_fsm_answers,
        status="BOT",
        error_count=reply2.updated_fsm_answers.get("error_count", 0),
    )
    reply3 = advance_fsm(ctx3, "", "IMAGE")
    assert reply3.updated_fsm_answers.get("error_count") == 3
    assert reply3.text == ""
    assert reply3.interactive is None


def test_fsm_reset_command() -> None:
    ctx = _make_context(
        current_step=FSMStep.PURCHASE_INTENT,
        fsm_answers={"current_step": FSMStep.PURCHASE_INTENT},
    )
    result = advance_fsm(ctx, "rl")

    assert result.updated_fsm_answers == {}
    assert result.text == "FSM reiniciada"
