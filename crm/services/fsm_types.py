"""
crm/services/fsm_types.py — Definición estricta de tipos para el FSM.

Se utiliza TypedDict para estructurar el campo JSONB `fsm_answers`
en la base de datos y evitar diccionarios genéricos (Regla MyPy).
"""

from enum import StrEnum
from typing import TypedDict


class FSMStep(StrEnum):
    """Pasos posibles de la máquina de estados del Chat (MASTER_SPEC §4)."""

    INITIAL = "INITIAL"
    VEHICLE_TYPE = "VEHICLE_TYPE"
    PAYMENT_METHOD = "PAYMENT_METHOD"
    BUDGET_RANGE = "BUDGET_RANGE"
    PURCHASE_INTENT = "PURCHASE_INTENT"
    QUALIFIED = "QUALIFIED"


class VehicleType(StrEnum):
    CITY_CAR = "CITY_CAR"
    SUV = "SUV"
    SEDAN = "SEDAN"


class PaymentMethod(StrEnum):
    CONTADO = "CONTADO"
    CREDITO = "CREDITO"
    RETOMA = "RETOMA"


class BudgetRange(StrEnum):
    MENOS_6M = "MENOS_6M"
    DE_7M_A_14M = "DE_7M_A_14M"
    MAS_15M = "MAS_15M"


class PurchaseIntent(StrEnum):
    HOY = "HOY"
    ESTA_SEMANA = "ESTA_SEMANA"
    MES_O_MAS = "MES_O_MAS"


class FSMAnswers(TypedDict, total=False):
    """Esquema estricto para el estado e historial extraído durante la iteración del bot."""

    current_step: FSMStep
    vehicle_type: VehicleType
    payment_method: PaymentMethod
    budget_range: BudgetRange
    purchase_intent: PurchaseIntent
    error_count: int
