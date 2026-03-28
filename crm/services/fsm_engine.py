"""
crm/services/fsm_engine.py — Motor de la Máquina de Estados (FSM)

Recibe un ChatSession y el texto/payload del Lead.
Aplica reglas puras: muta la sesión en memoria y retorna las instrucciones.
Prohibido llamar a Twilio aquí (Regla High Concurrency).
"""
import re
from crm.models import ChatSession, Message
from crm.services.fsm_types import (
    FSMStep, FSMAnswers, VehicleType, PaymentMethod, BudgetRange, PurchaseIntent
)


def _increase_error(session: ChatSession) -> int:
    """Sube la cuenta de errores y retorna el total."""
    count = session.fsm_answers.get('error_count', 0) + 1
    session.fsm_answers['error_count'] = count
    return count

def _clean_input(text: str) -> str:
    """Quita espacios extra y pasa a minusculas."""
    return text.strip().lower()

def advance_fsm(session: ChatSession, message_body: str, message_type: str = None) -> dict:
    """
    Avanza la máquina de estados según el mensaje recibido.

    Args:
        session: Instancia de ChatSession (manejada dentro de atomic() en el caller).
        message_body: El texto o payload enviado por el lead.
        message_type: El tipo de mensaje (TEXT, IMAGE, AUDIO, etc.).

    Returns:
        dict: Instrucciones de respuesta (ej. {'text': 'Hola...', 'interactive': {...}})
    """
    if message_type is None:
        message_type = Message.Type.TEXT
    if not session.fsm_answers:
        session.fsm_answers = {}

    current_step = session.fsm_answers.get('current_step')
    
    # -------------------------------------------------------------------------
    # Regla: Multimedia o audios no permitidos. Validación por Message.Type
    # -------------------------------------------------------------------------
    if message_type != Message.Type.TEXT:
        err_count = _increase_error(session)
        if err_count <= 2:
            return {"text": "⚠️ Por favor, responde usando solo las opciones de texto."}
        else:
            return {}  # Espera pasiva y silenciosa
            
    # Función lambda para simplificar el flujo de error de parseo (cuando escribe cualquier cosa)
    def _invalid_input():
        err = _increase_error(session)
        if err <= 2:
            return {"text": "⚠️ No entendí esa respuesta. Por favor, selecciona una de las opciones."}
        return {}
        
    # -------------------------------------------------------------------------
    # Inicialización del flujo: Cualquier texto inicia el Paso 1
    # -------------------------------------------------------------------------
    if not current_step or current_step == FSMStep.INITIAL:
        session.fsm_answers['current_step'] = FSMStep.VEHICLE_TYPE
        session.fsm_answers['error_count'] = 0
        return {
            "text": "¿Qué tipo de auto buscas?",
            "interactive": {
                "type": "button",
                "buttons": [
                    {"id": "vt_citycar", "title": "City Car"},
                    {"id": "vt_suv", "title": "SUV"},
                    {"id": "vt_sedan", "title": "Sedán"},
                ]
            }
        }

    # Transición: VEHICLE_TYPE -> PAYMENT_METHOD
    if current_step == FSMStep.VEHICLE_TYPE:
        t = _clean_input(message_body)
        if t == "vt_citycar": session.fsm_answers['vehicle_type'] = VehicleType.CITY_CAR
        elif t == "vt_suv": session.fsm_answers['vehicle_type'] = VehicleType.SUV
        elif t == "vt_sedan": session.fsm_answers['vehicle_type'] = VehicleType.SEDAN
        else:
            # Si estamos en el primer paso y el lead escribe texto libre en lugar de presionar 
            # el botón, simplemente repetimos la pregunta inicial de forma amigable.
            session.fsm_answers['error_count'] = 0 # Reseteamos errores para no silenciarlo
            return {
                "text": "Por favor, selecciona una de las opciones para comenzar: ¿Qué tipo de auto buscas?",
                "interactive": {
                    "type": "button",
                    "buttons": [
                        {"id": "vt_citycar", "title": "City Car"},
                        {"id": "vt_suv", "title": "SUV"},
                        {"id": "vt_sedan", "title": "Sedán"},
                    ]
                }
            }

        session.fsm_answers['current_step'] = FSMStep.PAYMENT_METHOD
        session.fsm_answers['error_count'] = 0
        return {
            "text": "¿Cómo prefieres pagarlo?",
            "interactive": {
                "type": "button",
                "buttons": [
                    {"id": "pm_contado", "title": "Contado"},
                    {"id": "pm_credito", "title": "Crédito"},
                    {"id": "pm_retoma", "title": "Retoma"},
                ]
            }
        }

    # Transición: PAYMENT_METHOD -> BUDGET_RANGE
    if current_step == FSMStep.PAYMENT_METHOD:
        t = _clean_input(message_body)
        if t == "pm_contado": session.fsm_answers['payment_method'] = PaymentMethod.CONTADO
        elif t == "pm_credito": session.fsm_answers['payment_method'] = PaymentMethod.CREDITO
        elif t == "pm_retoma": session.fsm_answers['payment_method'] = PaymentMethod.RETOMA
        else:
            return _invalid_input()

        session.fsm_answers['current_step'] = FSMStep.BUDGET_RANGE
        session.fsm_answers['error_count'] = 0
        return {
            "text": "¿Cuál es tu presupuesto estimado?",
            "interactive": {
                "type": "button",
                "buttons": [
                    {"id": "br_menos6", "title": "< 6M"},
                    {"id": "br_7a14", "title": "7M a 14M"},
                    {"id": "br_mas15", "title": "15M o más"},
                ]
            }
        }

    # Transición: BUDGET_RANGE -> PURCHASE_INTENT
    if current_step == FSMStep.BUDGET_RANGE:
        t = _clean_input(message_body)
        if t == "br_7a14": session.fsm_answers['budget_range'] = BudgetRange.DE_7M_A_14M
        elif t == "br_mas15": session.fsm_answers['budget_range'] = BudgetRange.MAS_15M
        elif t == "br_menos6": session.fsm_answers['budget_range'] = BudgetRange.MENOS_6M
        else:
            return _invalid_input()

        session.fsm_answers['current_step'] = FSMStep.PURCHASE_INTENT
        session.fsm_answers['error_count'] = 0
        return {
            "text": "¿Para cuándo tienes planificada tu compra?",
            "interactive": {
                "type": "button",
                "buttons": [
                    {"id": "pi_hoy", "title": "Hoy"},
                    {"id": "pi_semana", "title": "Esta semana"},
                    {"id": "pi_mes", "title": "Mes o más"},
                ]
            }
        }

    # Transición: PURCHASE_INTENT -> QUALIFIED (Con lógica de Puntuación)
    if current_step == FSMStep.PURCHASE_INTENT:
        t = _clean_input(message_body)
        if t == "pi_hoy":
            session.fsm_answers['purchase_intent'] = PurchaseIntent.HOY
        elif t == "pi_semana":
            session.fsm_answers['purchase_intent'] = PurchaseIntent.ESTA_SEMANA
        elif t == "pi_mes":
            session.fsm_answers['purchase_intent'] = PurchaseIntent.MES_O_MAS
        else:
            return _invalid_input()

        session.fsm_answers['current_step'] = FSMStep.QUALIFIED
        session.fsm_answers['error_count'] = 0
        
        # Hito de Finalización: El bot terminó su trabajo, el lead pasa a cola de asignación
        session.status = ChatSession.Status.PENDING_ASSIGNMENT
        
        # ================================
        # Lógica matemática de Urgency Score
        # ================================
        score = 0
        pi = session.fsm_answers.get('purchase_intent')
        bg = session.fsm_answers.get('budget_range')
        pm = session.fsm_answers.get('payment_method')
        
        # Prioridad máxima absoluta si es para Hoy.
        if pi == PurchaseIntent.HOY:
            score += 100
        elif pi == PurchaseIntent.ESTA_SEMANA:
            score += 20
        elif pi == PurchaseIntent.MES_O_MAS:
            score += 10
            
        # Bonos por presupuesto
        if bg == BudgetRange.MAS_15M: score += 40
        elif bg == BudgetRange.DE_7M_A_14M: score += 20
        elif bg == BudgetRange.MENOS_6M: score += 10
            
        # Bonos por método de pago
        if pm == PaymentMethod.CREDITO: score += 20
            
        session.urgency_score = score
        
        return {
            "text": "¡Perfecto! Un asesor de ventas te contactará a la brevedad con las mejores opciones."
        }
    
    # Si FSM llega acá, está terminal o un error raro
    return {}



