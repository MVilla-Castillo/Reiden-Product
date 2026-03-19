"""
crm/views/worker.py

Vista privada: POST /api/workers/process-message/
Responsabilidad: procesar el payload encolado por Cloud Tasks.

REGLAS CLAVE (SKILL: high_concurrency + event_sourcing):
- Autenticado por `X-Internal-Secret`, NO por OIDC.
- IDEMPOTENTE: si el MessageSid ya existe en DB, retorna 200 OK sin fallar.
- Toda escritura a DB ocurre dentro de transaction.atomic() con select_for_update().
- Prohibido hacer llamadas HTTP externas DENTRO de transaction.atomic().
"""
import hashlib
import json
import logging
from typing import Any

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from crm.models import ChatSession, Lead, Message, Tenant

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def process_message_worker_view(request: HttpRequest) -> JsonResponse:
    """
    Worker de procesamiento de mensajes de WhatsApp.

    Invocado por GCP Cloud Tasks con el payload del Webhook de Twilio.
    Garantiza idempotencia mediante el MessageSid como UNIQUE key en DB.

    Flujo:
    1. Autenticar request via header X-Internal-Secret.
    2. Parsear body JSON.
    3. Idempotencia: verificar si el Message ya existe → 200 OK inmediato.
    4. Dentro de transaction.atomic():
       a. Upsert Lead (wa_id_hash como llave única → evitar duplicados).
       b. Obtener o crear ChatSession activa.
       c. Crear Message (INSERT ... ON CONFLICT DO NOTHING mediante get_or_create).
    """
    # PASO 1: Autenticación del Worker (X-Internal-Secret)
    internal_secret: str = getattr(settings, 'CLOUD_TASKS_INTERNAL_SECRET', '')
    incoming_secret: str = request.headers.get('X-Internal-Secret', '')

    if not internal_secret or incoming_secret != internal_secret:
        logger.warning(
            "Worker: secreto interno inválido. Acceso denegado.",
            extra={"component_name": "process_message_worker"},
        )
        return JsonResponse({"error": "Forbidden"}, status=403)

    # PASO 2: Parsear Body JSON
    try:
        payload: dict[str, Any] = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        logger.error(
            "Worker: body no es JSON válido.",
            extra={"component_name": "process_message_worker"},
        )
        return JsonResponse({"error": "Bad Request: JSON inválido"}, status=400)

    message_sid: str = payload.get('MessageSid', '')
    if not message_sid:
        return JsonResponse({"error": "Bad Request: MessageSid requerido"}, status=400)

    # PASO 3: Idempotencia - El cheque temprano fuera de la transacción (RNF-03)
    # Si el mensaje ya existe, respondemos 200 sin abrir ni una transacción.
    if Message.objects.filter(provider_message_id=message_sid).exists():
        logger.info(
            "Worker: MessageSid duplicado. Ignorando (idempotencia).",
            extra={
                "component_name": "process_message_worker",
                "message_sid": message_sid,
            },
        )
        return JsonResponse({"status": "duplicate_ignored"}, status=200)

    # PASO 4: Procesamiento dentro de transaction.atomic() (SKILL high_concurrency §6)
    try:
        with transaction.atomic():
            # 4a. Obtener el Tenant via WaId del número de destino (To)
            to_number: str = (
                payload.get('To', '')
                .replace('whatsapp:', '')
                .lstrip('+')  # El phone_number_id en Tenant no incluye el '+'
            )

            try:
                tenant: Tenant = Tenant.objects.get(phone_number_id=to_number)
            except Tenant.DoesNotExist:
                # Si no hay Tenant, el mensaje es para un número no registrado.
                logger.error(
                    "Worker: Tenant no encontrado para el número.",
                    extra={
                        "component_name": "process_message_worker",
                        "to_number": to_number,
                    },
                )
                # Retornamos 200 para que Cloud Tasks no reintente (es un error de config, no transitorio)
                return JsonResponse({"error": "Tenant not found"}, status=200)

            # 4b. Upsert atómico del Lead (wa_id_hash como llave única → anti-duplicado)
            # Prohibido get_or_create en webhooks masivos → usamos update_or_create
            # con wa_id_hash para garantizar ACID (RNF-09, AGENTS.md §4)
            wa_id_raw: str = payload.get('WaId', '') or payload.get('From', '').replace('whatsapp:', '')
            wa_id_clean: str = wa_id_raw[:50]
            wa_id_hash: str = hashlib.sha256(wa_id_clean.encode()).hexdigest()

            lead, _ = Lead.objects.update_or_create(
                wa_id_hash=wa_id_hash,
                defaults={
                    "tenant": tenant,
                    "wa_id": wa_id_clean,
                },
            )

            # 4c. Obtener o crear la ChatSession activa para este Lead
            # select_for_update() previene race conditions si dos webhooks del mismo
            # lead llegan simultáneamente (SKILL high_concurrency §6)
            active_statuses = [
                ChatSession.Status.BOT,
                ChatSession.Status.PENDING_ASSIGNMENT,
                ChatSession.Status.CON_VENDEDOR,
            ]
            session = (
                ChatSession.objects
                .select_for_update()
                .filter(lead=lead, tenant=tenant, status__in=active_statuses, is_deleted=False)
                .order_by('-created_at')
                .first()
            )

            if session is None:
                # Primera vez o sesión previa en estado terminal → crear nueva
                session = ChatSession.objects.create(
                    tenant=tenant,
                    lead=lead,
                    status=ChatSession.Status.BOT,
                )
                logger.info(
                    "Worker: Nueva ChatSession creada.",
                    extra={
                        "component_name": "process_message_worker",
                        "tenant_id": str(tenant.id),
                        "lead_id": str(lead.id),
                        "session_id": str(session.id),
                    },
                )

            # 4d. Crear el Message (idempotencia de último recurso via unique constraint)
            # porque estamos dentro del atomic() con el lead bloqueado.
            _direction = (
                Message.Direction.INBOUND
                if payload.get('From', '').startswith('whatsapp:')
                else Message.Direction.OUTBOUND
            )

            _message_type_map = {
                'image': Message.Type.IMAGE,
                'audio': Message.Type.AUDIO,
                'document': Message.Type.DOCUMENTO,
            }
            _raw_type = payload.get('MessageType', 'text').lower()
            _message_type = _message_type_map.get(_raw_type, Message.Type.TEXT)

            _body = payload.get('Body', '') or payload.get('ButtonText', '') or payload.get('MediaUrl0', '')
            
            # 4e. Idempotencia y Guardado de Mensaje Entrante
            message, created = Message.objects.get_or_create(
                provider_message_id=message_sid,
                defaults={
                    'tenant': tenant,
                    'session': session,
                    'direction': Message.Direction.INBOUND,
                    'message_type': _message_type,
                    'body': _body,
                }
            )
            if not created:
                logger.info(
                    "Worker: Mensaje duplicado ignorado (Idempotencia).",
                    extra={"component_name": "process_message_worker", "message_sid": message_sid}
                )
                return JsonResponse({"status": "duplicate_ignored"}, status=200)

            # =====================================================================
            # CORE BUSINESS LOGIC (FSM): Evaluación del estado conversacional.
            # Se ejecuta dentro del atomic() para aprovechar el select_for_update.
            # =====================================================================
            from crm.services.fsm_engine import advance_fsm
            
            # Avanzamos la FSM pasando el tipo y cuerpo del mensaje
            reply_instructions = advance_fsm(session, _body, _message_type)

            # Persistimos la mutación generada por la FSM en memoria hacia la base de datos
            session.save()
            lead.save()

        # =====================================================================
        # SIDE-EFFECTS DE RED: Llamada a API Externa (Twilio).
        # STRICT RULE: Siempre FUERA del bloque transaction.atomic()
        # =====================================================================
        if reply_instructions:
            from crm.services.twilio_client import send_whatsapp_message
            outbound_msg_sid = send_whatsapp_message(
                to_number=to_number,
                text=reply_instructions.get('text', ''),
                interactive_payload=reply_instructions.get('interactive')
            )
            
            # Guardamos el mensaje saliente en la base de datos (nueva mini-transacción rápida)
            if outbound_msg_sid:
                Message.objects.create(
                    provider_message_id=outbound_msg_sid,
                    tenant=tenant,
                    session=session,
                    direction=Message.Direction.OUTBOUND,
                    message_type=Message.Type.TEXT,
                    body=reply_instructions.get('text', ''),
                )

        logger.info(
            "Worker: Mensaje procesado exitosamente y respondido.",
            extra={
                "component_name": "process_message_worker",
                "message_sid": message_sid,
                "lead_id": str(lead.id),
                "session_id": str(session.id),
                "msg_created": created,
            },
        )

        return JsonResponse({"status": "processed", "created": created}, status=200)

    except Exception:
        logger.exception(
            "Worker: Error no controlado en transaction.atomic(). Rollback ejecutado.",
            extra={
                "component_name": "process_message_worker",
                "message_sid": message_sid,
                "tenant_id": "unknown",
            },
        )
        # Cloud Tasks reintentará automáticamente al recibir un 5xx
        return JsonResponse({"error": "internal_error"}, status=500)

