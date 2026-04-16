import uuid
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from crm.models import Tenant, ChatSession, Message


class Command(BaseCommand):
    help = "Simula secuencia completa de chat (FSM flow test)"

    def handle(self, *args, **options):
        # 0. Limpiar estado anterior para corrida limpia (soft-delete)
        ChatSession.objects.filter(lead__wa_id="56999999999").update(is_deleted=True)
        Message.objects.filter(provider_message_id__startswith="SM_SIM_").update(
            is_deleted=True
        )

        # 1. SETUP: Asegurar que el Tenant local existe
        tenant, _ = Tenant.objects.get_or_create(
            phone_number_id="56912345678",
            defaults={
                "nombre_legal": "Test Enterprise",
                "rut_empresa": "1-1",
                "waba_id": "WABA1",
            },
        )

        # 2. Configuración de URLs y Secretos
        # Nota: Asegúrate de que 'runserver' esté en el puerto 8000
        worker_url = "http://127.0.0.1:8000/api/workers/process-message/"
        secret = settings.CLOUD_TASKS_INTERNAL_SECRET
        phone_lead = "56999999999"

        # 3. Flujo de conversación (Cuerpo del mensaje)
        # Este ciclo recorrerá todos los estados de la FSM
        mensajes = [
            "Quiero info de un auto",  # Paso 1: Activa FSM (Initial -> VEHICLE_TYPE)
            "Una SUV por favor",  # Paso 2: Selección (-> PAYMENT_METHOD)
            "A crédito",  # Paso 3: Condición (-> BUDGET_RANGE)
            "15M o más",  # Paso 4: Presupuesto (-> PURCHASE_INTENT)
            "Hoy mismo",  # Paso 5: Tiempo (-> QUALIFIED con Score Máximo Acumulado)
        ]

        self.stdout.write(
            self.style.SUCCESS(f"\n🚀 Iniciando simulación para Lead: {phone_lead}")
        )
        self.stdout.write("-" * 50)

        for i, body in enumerate(mensajes, 1):
            self.stdout.write(f"\n📥 [PASO {i}] Enviando: '{body}'")

            payload = {
                "MessageSid": f"SM_SIM_{uuid.uuid4().hex[:8]}",
                "From": f"whatsapp:+{phone_lead}",
                "To": "whatsapp:+56912345678",
                "Body": body,
                "WaId": phone_lead,
                "MessageType": "text",
            }

            try:
                # Realizar POST al Worker
                res = requests.post(
                    worker_url,
                    json=payload,
                    headers={"X-Internal-Secret": secret},
                    timeout=5,
                )

                if res.status_code != 200:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Error {res.status_code}: {res.text}")
                    )
                    return

                # 4. Verificar impacto en DB
                # Buscamos la sesión más reciente del lead
                session = ChatSession.objects.filter(lead__wa_id=phone_lead).last()

                if session:
                    # Forzamos refresh interno del objeto
                    session.refresh_from_db()
                    current_step = session.fsm_answers.get("current_step", "INIT")
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ Estado FSM: {current_step}")
                    )
                    self.stdout.write(f"📊 Answers Acumuladas: {session.fsm_answers}")
                    self.stdout.write(f"🔥 Urgency Score: {session.urgency_score}")

                    # Mostrar lo que el bot respondió
                    last_bot_reply = (
                        Message.objects.filter(
                            session=session, direction=Message.Direction.OUTBOUND
                        )
                        .order_by("-created_at")
                        .first()
                    )

                    if last_bot_reply:
                        self.stdout.write(
                            self.style.HTTP_INFO(f"🤖 BOT DICE: {last_bot_reply.body}")
                        )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ Fallo de conexión (¿Está corriendo 'runserver'?): {e}"
                    )
                )
                return

        self.stdout.write(
            self.style.SUCCESS("\n🏁 Simulación completada exitosamente.")
        )
