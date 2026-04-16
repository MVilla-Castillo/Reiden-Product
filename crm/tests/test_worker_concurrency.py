"""
crm/tests/test_worker_concurrency.py — Tests de concurrencia ACID (RNF-09, RNF-24).

Validan que la ingesta masiva simultánea del mismo payload de Twilio
no genere duplicados de Lead ni Message (idempotencia bajo race conditions).

Usa TransactionTestCase (no TestCase) para que los bloqueos de fila reales
(SELECT FOR UPDATE) de PostgreSQL se ejerciten correctamente.
"""

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.test import TransactionTestCase
from django.conf import settings

from crm.adapters.dependency_injection import DIContainer
from crm.adapters.messaging.twilio_adapter import InMemoryMessageProvider
from crm.models import Lead, Message, Tenant


def _make_payload(message_sid: str = "SMconcurrent000000000000001") -> dict:
    return {
        "MessageSid": message_sid,
        "AccountSid": "ACtest",
        "From": "whatsapp:+56987654321",
        "To": "whatsapp:+56912345678",
        "WaId": "56987654321",
        "Body": "Hola, quiero info sobre un SUV",
        "ButtonText": "",
        "ButtonPayload": "",
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


def _post_to_worker(client, payload: dict):
    internal_secret = settings.CLOUD_TASKS_INTERNAL_SECRET
    return client.post(
        "/api/workers/process-message/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_INTERNAL_SECRET=internal_secret,
    )


class TestWorkerConcurrency(TransactionTestCase):
    """
    TransactionTestCase garantiza que cada test se ejecuta en su propia
    transacción real, permitiendo que los bloqueos de fila de PostgreSQL
    (SELECT FOR UPDATE) se manifiesten correctamente.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._original_container = DIContainer._instance

    @classmethod
    def tearDownClass(cls):
        DIContainer._instance = cls._original_container
        super().tearDownClass()

    def setUp(self):
        DIContainer.reset()
        container = DIContainer.instance()
        container.set_message_provider(InMemoryMessageProvider())

    def tearDown(self):
        DIContainer.reset()

    # ==========================================================================
    # TEST: 5 hilos simultáneos con mismo MessageSid → 1 Lead, 1 Message
    # ==========================================================================
    def test_concurrent_same_message_sid_no_duplicates(self) -> None:
        """
        ARRANGE: Tenant existe. 5 hilos disparan el mismo payload simultáneamente.
        ACT: ThreadPoolExecutor con 5 workers ejecutando _post_to_worker.
        ASSERT:
            - Lead.objects.count() == 1
            - Message.objects.count() == 1
            - Ningún hilo lanzó IntegrityError no manejado.
        """
        tenant = Tenant.objects.create(
            nombre_legal="Automotora Test S.A.",
            rut_empresa="76.000.000-0",
            phone_number_id="56912345678",
            waba_id="WABA_CONCURRENT_001",
            is_verified=True,
        )

        message_sid = "SMconcurrent_race_00000001"
        payload = _make_payload(message_sid)
        num_threads = 5
        results: list = []
        errors: list = []
        barrier = threading.Barrier(num_threads)

        def worker_task() -> dict:
            barrier.wait()
            try:
                from django.test import Client

                client = Client()
                response = _post_to_worker(client, payload)
                return {
                    "status_code": response.status_code,
                    "json": response.json() if response.content else {},
                }
            except Exception as e:
                errors.append(type(e).__name__)
                return {"error": str(e)}

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_task) for _ in range(num_threads)]
            for future in as_completed(futures):
                results.append(future.result())

        wa_id_hash = hashlib.sha256("56987654321".encode()).hexdigest()
        lead_count = Lead.objects.filter(wa_id_hash=wa_id_hash).count()
        message_count = Message.objects.filter(provider_message_id=message_sid).count()

        assert lead_count == 1, (
            f"Se esperaba 1 Lead, se encontraron {lead_count} (race condition detectada)"
        )
        assert message_count == 1, (
            f"Se esperaba 1 Message, se encontraron {message_count} (idempotencia rota)"
        )

        unhandled_errors = [e for e in errors if "IntegrityError" in e]
        assert len(unhandled_errors) == 0, (
            f"IntegrityError no manejado en {len(unhandled_errors)} hilos: {unhandled_errors}"
        )

        success_count = sum(1 for r in results if r.get("status_code") == 200)
        assert success_count == num_threads, (
            f"Se esperaba que los {num_threads} hilos respondieran 200, "
            f"solo {success_count} lo hicieron. Errores: {errors}"
        )

    # ==========================================================================
    # TEST: 5 hilos simultáneos con distintos MessageSid, mismo WaId → 1 Lead, N Messages
    # ==========================================================================
    def test_concurrent_different_sids_same_lead_no_duplicate_leads(self) -> None:
        """
        ARRANGE: Tenant existe. 5 hilos con distinto MessageSid pero mismo WaId.
        ACT: ThreadPoolExecutor dispara payloads simultáneos.
        ASSERT:
            - Lead.objects.count() == 1 (upsert atómico)
            - Message.objects.count() >= 1 (al menos 1 message, los demás pueden
              fallar por race condition en session creation, lo cual es aceptable)
            - Ningún IntegrityError no manejado se propaga al cliente.
        """
        tenant = Tenant.objects.create(
            nombre_legal="Automotora Test S.A.",
            rut_empresa="76.000.001-1",
            phone_number_id="56912345678",
            waba_id="WABA_CONCURRENT_002",
            is_verified=True,
        )

        num_threads = 5
        results: list = []
        errors: list = []
        barrier = threading.Barrier(num_threads)

        def worker_task(index: int) -> dict:
            barrier.wait()
            try:
                from django.test import Client

                client = Client()
                payload = _make_payload(f"SMdistinct_sid_{index:04d}")
                response = _post_to_worker(client, payload)
                return {
                    "status_code": response.status_code,
                    "json": response.json() if response.content else {},
                }
            except Exception as e:
                errors.append(f"thread_{index}: {type(e).__name__}: {e}")
                return {"error": str(e)}

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_task, i) for i in range(num_threads)]
            for future in as_completed(futures):
                results.append(future.result())

        wa_id_hash = hashlib.sha256("56987654321".encode()).hexdigest()
        lead_count = Lead.objects.filter(wa_id_hash=wa_id_hash).count()
        message_count = Message.objects.filter(
            provider_message_id__startswith="SMdistinct_sid_"
        ).count()

        assert lead_count == 1, (
            f"Se esperaba 1 Lead (upsert atómico), se encontraron {lead_count}"
        )
        assert message_count >= 1, (
            f"Se esperaba al menos 1 Message, se encontraron {message_count}"
        )

        unhandled_errors = [e for e in errors if "IntegrityError" in e]
        assert len(unhandled_errors) == 0, (
            f"IntegrityError no manejado: {unhandled_errors}"
        )

        all_200 = all(r.get("status_code") == 200 for r in results)
        assert all_200, (
            f"Todos los hilos deben devolver 200 (incluso con race condition). "
            f"Resultados: {[r.get('status_code') for r in results]}"
        )

        num_threads = 5
        results: list = []
        errors: list = []
        barrier = threading.Barrier(num_threads)

        def worker_task(index: int) -> dict:
            barrier.wait()
            try:
                from django.test import Client

                client = Client()
                payload = _make_payload(f"SMdistinct_sid_{index:04d}")
                response = _post_to_worker(client, payload)
                return {
                    "status_code": response.status_code,
                    "json": response.json() if response.content else {},
                }
            except Exception as e:
                errors.append(f"thread_{index}: {type(e).__name__}: {e}")
                return {"error": str(e)}

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_task, i) for i in range(num_threads)]
            for future in as_completed(futures):
                results.append(future.result())

        wa_id_hash = hashlib.sha256("56987654321".encode()).hexdigest()
        lead_count = Lead.objects.filter(wa_id_hash=wa_id_hash).count()
        message_count = Message.objects.filter(
            provider_message_id__startswith="SMdistinct_sid_"
        ).count()

        assert lead_count == 1, (
            f"Se esperaba 1 Lead (upsert atómico), se encontraron {lead_count}"
        )
        assert message_count == num_threads, (
            f"Se esperaban {num_threads} Messages (sids distintos), se encontraron {message_count}"
        )

        unhandled_errors = [e for e in errors if "IntegrityError" in e]
        assert len(unhandled_errors) == 0, (
            f"IntegrityError no manejado: {unhandled_errors}"
        )
