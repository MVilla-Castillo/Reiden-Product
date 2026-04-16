"""
crm/services/fsm_engine.py — Motor de la Máquina de Estados (FSM) puro.

Dominio puro: cero imports de Django, Twilio o GCP.
Recibe un FSMContext (DTO inmutable) y retorna un FSMResult (DTO inmutable).
El caller es responsable de aplicar los cambios al repositorio.

Todos los textos de respuesta están centralizados en constantes para
facilitar i18n y evitar strings hardcodeados dispersos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from crm.services.fsm_types import (
    FSMStep,
    VehicleType,
    PaymentMethod,
    BudgetRange,
    PurchaseIntent,
)

# ─────────────────────────────────────────────────────────
# Constantes de texto (respuestas del bot)
# ─────────────────────────────────────────────────────────

MSG_RESET = "FSM reiniciada"
MSG_MULTIMEDIA_REJECTED = "Por favor, responde usando solo las opciones de texto."
MSG_INVALID_INPUT = (
    "No entendí esa respuesta. Por favor, selecciona una de las opciones."
)
MSG_VEHICLE_TYPE_QUESTION = "¿Qué tipo de auto buscas?"
MSG_VEHICLE_TYPE_RETRY = (
    "Por favor, selecciona una de las opciones para comenzar: ¿Qué tipo de auto buscas?"
)
MSG_PAYMENT_METHOD_QUESTION = "¿Cómo prefieres pagarlo?"
MSG_BUDGET_RANGE_QUESTION = "¿Cuál es tu presupuesto estimado?"
MSG_PURCHASE_INTENT_QUESTION = "¿Para cuándo tienes planificada tu compra?"
MSG_QUALIFIED = (
    "¡Perfecto! Hemos recopilado toda tu información. "
    "Te estamos asignando con un asesor de ventas que te atenderá "
    "a la brevedad en este mismo chat. ¡Gracias por tu interés!"
)

# ─────────────────────────────────────────────────────────
# Constantes de estado (evitar hardcoded strings)
# ─────────────────────────────────────────────────────────

STATUS_PENDING_ASSIGNMENT = "PENDING_ASSIGNMENT"

# ─────────────────────────────────────────────────────────
# Constantes de botones interactivos
# ─────────────────────────────────────────────────────────

BTN_VEHICLE_TYPE = {
    "type": "button",
    "buttons": [
        {"id": "vt_citycar", "title": "City Car"},
        {"id": "vt_suv", "title": "SUV"},
        {"id": "vt_sedan", "title": "Sedán"},
    ],
}

BTN_PAYMENT_METHOD = {
    "type": "button",
    "buttons": [
        {"id": "pm_contado", "title": "Contado"},
        {"id": "pm_credito", "title": "Crédito"},
        {"id": "pm_retoma", "title": "Retoma"},
    ],
}

BTN_BUDGET_RANGE = {
    "type": "button",
    "buttons": [
        {"id": "br_menos6", "title": "Menos de 6 millones"},
        {"id": "br_7a14", "title": "De 7 a 14 millones"},
        {"id": "br_mas15", "title": "Más de 15 millones"},
    ],
}

BTN_PURCHASE_INTENT = {
    "type": "button",
    "buttons": [
        {"id": "pi_hoy", "title": "Hoy"},
        {"id": "pi_semana", "title": "Esta semana"},
        {"id": "pi_mes", "title": "Mes o más"},
    ],
}


@dataclass(frozen=True)
class FSMContext:
    """Estado actual de la sesión conversacional (snapshot inmutable)."""

    current_step: str | None
    fsm_answers: dict[str, Any]
    status: str
    error_count: int = 0


@dataclass(frozen=True)
class FSMResult:
    """Resultado de la evaluación de la FSM."""

    text: str
    interactive: dict[str, Any] | None = None
    next_step: str | None = None
    updated_fsm_answers: dict[str, Any] = field(default_factory=dict)
    new_status: str | None = None
    urgency_score: int = 0
    is_terminal: bool = False


def _clean_input(text: str) -> str:
    return text.strip().lower()


def _match_input(text: str, patterns: list[str | Callable[[str], bool]]) -> bool:
    """Verifica si el texto coincide con cualquiera de los patrones (string o función)."""
    for pattern in patterns:
        if isinstance(pattern, str):
            if pattern == text or pattern in text:
                return True
        elif callable(pattern) and pattern(text):
            return True
    return False


def _invalid_input(
    fsm_answers: dict[str, Any],
    error_count: int,
    current_step: str | None,
) -> FSMResult:
    """Incrementa error_count y retorna respuesta de error o silencio."""
    error_count += 1
    fsm_answers["error_count"] = error_count
    if error_count <= 2:
        return FSMResult(
            text=MSG_INVALID_INPUT,
            next_step=current_step,
            updated_fsm_answers=fsm_answers,
        )
    return FSMResult(
        text="",
        next_step=current_step,
        updated_fsm_answers=fsm_answers,
    )


def advance_fsm(
    context: FSMContext, message_body: str, message_type: str = "TEXT"
) -> FSMResult:
    """
    Avanza la máquina de estados según el mensaje recibido.

    Args:
        context: Snapshot del estado actual de la sesión.
        message_body: Texto o payload enviado por el lead.
        message_type: Tipo de mensaje (TEXT, IMAGE, AUDIO, etc.).

    Returns:
        FSMResult con instrucciones de respuesta y estado actualizado.
    """
    fsm_answers = dict(context.fsm_answers)
    current_step = context.current_step
    error_count = context.error_count
    t_input = _clean_input(message_body)

    # Comando de reseteo manual
    if t_input == "rl":
        return FSMResult(
            text=MSG_RESET,
            next_step=None,
            updated_fsm_answers={},
        )

    # Multimedia no permitida
    if message_type != "TEXT":
        error_count += 1
        fsm_answers["error_count"] = error_count
        if error_count <= 2:
            return FSMResult(
                text=MSG_MULTIMEDIA_REJECTED,
                next_step=current_step,
                updated_fsm_answers=fsm_answers,
            )
        return FSMResult(
            text="",
            next_step=current_step,
            updated_fsm_answers=fsm_answers,
        )

    # Inicialización: Iniciar flujo FSM desde VEHICLE_TYPE
    if not current_step or current_step == FSMStep.INITIAL:
        fsm_answers["current_step"] = FSMStep.VEHICLE_TYPE
        fsm_answers["error_count"] = 0
        return FSMResult(
            text=MSG_VEHICLE_TYPE_QUESTION,
            interactive=BTN_VEHICLE_TYPE,
            next_step=FSMStep.VEHICLE_TYPE,
            updated_fsm_answers=fsm_answers,
        )

    # VEHICLE_TYPE -> PAYMENT_METHOD
    if current_step == FSMStep.VEHICLE_TYPE:
        t = _clean_input(message_body)
        if _match_input(t, ["vt_citycar", "city car", "citycar", "urbano"]):
            fsm_answers["vehicle_type"] = VehicleType.CITY_CAR
        elif _match_input(t, ["vt_suv", "suv", "camioneta"]):
            fsm_answers["vehicle_type"] = VehicleType.SUV
        elif _match_input(t, ["vt_sedan", "sedan", "sedán", "estándar"]):
            fsm_answers["vehicle_type"] = VehicleType.SEDAN
        else:
            fsm_answers["error_count"] = 0
            return FSMResult(
                text=MSG_VEHICLE_TYPE_RETRY,
                interactive=BTN_VEHICLE_TYPE,
                next_step=FSMStep.VEHICLE_TYPE,
                updated_fsm_answers=fsm_answers,
            )

        fsm_answers["current_step"] = FSMStep.PAYMENT_METHOD
        fsm_answers["error_count"] = 0
        return FSMResult(
            text=MSG_PAYMENT_METHOD_QUESTION,
            interactive=BTN_PAYMENT_METHOD,
            next_step=FSMStep.PAYMENT_METHOD,
            updated_fsm_answers=fsm_answers,
        )

    # PAYMENT_METHOD -> BUDGET_RANGE
    if current_step == FSMStep.PAYMENT_METHOD:
        t = _clean_input(message_body)
        if _match_input(t, ["pm_contado", "contado", "efectivo"]):
            fsm_answers["payment_method"] = PaymentMethod.CONTADO
        elif _match_input(t, ["pm_credito", "crédito", "credito", "prestamo"]):
            fsm_answers["payment_method"] = PaymentMethod.CREDITO
        elif _match_input(t, ["pm_retoma", "retoma", "canje"]):
            fsm_answers["payment_method"] = PaymentMethod.RETOMA
        else:
            return _invalid_input(fsm_answers, error_count, current_step)

        fsm_answers["current_step"] = FSMStep.BUDGET_RANGE
        fsm_answers["error_count"] = 0
        return FSMResult(
            text=MSG_BUDGET_RANGE_QUESTION,
            interactive=BTN_BUDGET_RANGE,
            next_step=FSMStep.BUDGET_RANGE,
            updated_fsm_answers=fsm_answers,
        )

    # BUDGET_RANGE -> PURCHASE_INTENT
    if current_step == FSMStep.BUDGET_RANGE:
        t = _clean_input(message_body)
        if _match_input(t, ["br_7a14", "7m a 14m", "de 7 a 14 millones", "medio"]):
            fsm_answers["budget_range"] = BudgetRange.DE_7M_A_14M
        elif _match_input(
            t,
            [
                "br_mas15",
                "15m o más",
                "15m o mas",
                "más de 15 millones",
                "mas de 15 millones",
                "alto",
            ],
        ):
            fsm_answers["budget_range"] = BudgetRange.MAS_15M
        elif _match_input(t, ["br_menos6", "< 6m", "menos de 6 millones", "bajo"]):
            fsm_answers["budget_range"] = BudgetRange.MENOS_6M
        else:
            return _invalid_input(fsm_answers, error_count, current_step)

        fsm_answers["current_step"] = FSMStep.PURCHASE_INTENT
        fsm_answers["error_count"] = 0
        return FSMResult(
            text=MSG_PURCHASE_INTENT_QUESTION,
            interactive=BTN_PURCHASE_INTENT,
            next_step=FSMStep.PURCHASE_INTENT,
            updated_fsm_answers=fsm_answers,
        )

    # PURCHASE_INTENT -> QUALIFIED
    if current_step == FSMStep.PURCHASE_INTENT:
        t = _clean_input(message_body)
        if _match_input(t, ["pi_hoy", "hoy", "inmediato"]):
            fsm_answers["purchase_intent"] = PurchaseIntent.HOY
        elif _match_input(t, ["pi_semana", "esta semana", "proxima semana"]):
            fsm_answers["purchase_intent"] = PurchaseIntent.ESTA_SEMANA
        elif _match_input(
            t,
            [
                "pi_mes",
                "mes o más",
                "mes o mas",
                "este mes o más",
                "este mes o mas",
                "largo plazo",
            ],
        ):
            fsm_answers["purchase_intent"] = PurchaseIntent.MES_O_MAS
        else:
            return _invalid_input(fsm_answers, error_count, current_step)

        fsm_answers["current_step"] = FSMStep.QUALIFIED
        fsm_answers["error_count"] = 0

        score = _calculate_urgency_score(fsm_answers)

        return FSMResult(
            text=MSG_QUALIFIED,
            next_step=FSMStep.QUALIFIED,
            updated_fsm_answers=fsm_answers,
            new_status=STATUS_PENDING_ASSIGNMENT,
            urgency_score=score,
            is_terminal=True,
        )

    # Estado terminal o desconocido
    return FSMResult(
        text="",
        next_step=current_step,
        updated_fsm_answers=fsm_answers,
    )


def _calculate_urgency_score(fsm_answers: dict[str, Any]) -> int:
    score = 0
    pi = fsm_answers.get("purchase_intent")
    bg = fsm_answers.get("budget_range")
    pm = fsm_answers.get("payment_method")

    if pi == PurchaseIntent.HOY:
        score += 100
    elif pi == PurchaseIntent.ESTA_SEMANA:
        score += 20
    elif pi == PurchaseIntent.MES_O_MAS:
        score += 10

    if bg == BudgetRange.MAS_15M:
        score += 40
    elif bg == BudgetRange.DE_7M_A_14M:
        score += 20
    elif bg == BudgetRange.MENOS_6M:
        score += 10

    if pm == PaymentMethod.CREDITO:
        score += 20

    return score
