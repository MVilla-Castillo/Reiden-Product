"""
crm/tests/test_dashboard_performance.py — Tests de rendimiento ORM (RNF-06, RF-10).

Validan que los endpoints del Dashboard no sufran de queries N+1
cuando la automotora tenga miles de registros.

Filtro Anti-Junior: assertNumQueries(2) — 1 para obtener sesiones
con JOIN a Lead via select_related, 0 adicionales al serializar.
"""

from django.test import Client, override_settings, TestCase

from crm.models import AppUser, ChatSession, Lead, Tenant
from core.crypto import encrypt


class MockMiddleware:
    """Middleware para inyectar el tenant en tests bypassando OIDC."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = Tenant.objects.order_by("created_at").first()
        return self.get_response(request)


OVERM = override_settings(
    MIDDLEWARE=["crm.tests.test_dashboard_performance.MockMiddleware"]
)


class TestDashboardPerformance(TestCase):
    """
    Tests de rendimiento para el endpoint GET /api/dashboard/leads/.

    Usa TestCase de Django (no pytest) para poder usar assertNumQueries.
    El endpoint debe usar select_related('lead') para evitar N+1
    al acceder a lead.id durante la serialización.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tenant = Tenant.objects.create(
            nombre_legal="Automotora Performance S.A.",
            rut_empresa="76.100.000-0",
            phone_number_id="56912345678",
            waba_id="WABA_PERF_001",
            is_verified=True,
        )

    def _create_bulk_sessions(self, count: int = 50) -> None:
        """Inserta `count` ChatSessions, cada una con un Lead distinto."""
        leads_to_create = []
        for i in range(count):
            wa_id_plain = f"56999{10000 + i:05d}"
            leads_to_create.append(
                Lead(
                    tenant=self.tenant,
                    wa_id=encrypt(wa_id_plain),
                    wa_id_hash=f"perf_hash_{i:05d}",
                )
            )

        created_leads = Lead.objects.bulk_create(leads_to_create)

        sessions_to_create = []
        for lead in created_leads:
            sessions_to_create.append(
                ChatSession(
                    tenant=self.tenant,
                    lead=lead,
                    status=ChatSession.Status.BOT,
                    urgency_score=0,
                )
            )

        ChatSession.objects.bulk_create(sessions_to_create)

    def test_dashboard_queries_do_not_scale_with_data(self) -> None:
        """
        ARRANGE: 50 ChatSession activas con 50 Leads distintos, mismo tenant.
        ACT: GET al dashboard endpoint con DEBUG=True (para capturar queries).
        ASSERT: No más de 2 queries a PostgreSQL.
        """
        AppUser.objects.create(
            email="vendedor@test.cl",
            oidc_sub="sp-perf-001",
            tenant=self.tenant,
            role=AppUser.Role.SALESPERSON,
            is_active=True,
        )
        self._create_bulk_sessions(count=50)

        with override_settings(DEBUG=True):
            with self.assertNumQueries(2):
                client = Client()
                with OVERM:
                    response = client.get("/api/dashboard/leads/")

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("leads", data)
            self.assertEqual(len(data["leads"]), 50)

    def test_dashboard_returns_correct_ordering(self) -> None:
        """
        ARRANGE: 5 sesiones con urgency_score distinto.
        ACT: GET al dashboard.
        ASSERT: Ordenadas por urgency_score DESC, updated_at DESC.
        """
        for i in range(5):
            lead = Lead.objects.create(
                tenant=self.tenant,
                wa_id=encrypt(f"56988{i:05d}"),
                wa_id_hash=f"order_hash_{i}",
            )
            ChatSession.objects.create(
                tenant=self.tenant,
                lead=lead,
                status=ChatSession.Status.BOT,
                urgency_score=(i + 1) * 20,
            )

        client = Client()
        with OVERM:
            with self.assertNumQueries(2):
                response = client.get("/api/dashboard/leads/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        scores = [lead["urgency_score"] for lead in data["leads"]]
        self.assertEqual(
            scores,
            sorted(scores, reverse=True),
            f"Esperado orden DESC por urgency_score, obtenido: {scores}",
        )

    def test_dashboard_excludes_other_tenant_sessions(self) -> None:
        """
        ARRANGE: 10 sesiones en tenant principal, 10 en otro tenant.
        ACT: GET al dashboard del tenant principal.
        ASSERT: Solo aparecen las 10 del tenant principal. Max 2 queries.
        """
        self._create_bulk_sessions(count=10)

        other_tenant = Tenant.objects.create(
            nombre_legal="Other Automotora",
            rut_empresa="99.999.999-9",
            phone_number_id="56999999999",
            waba_id="WABA_OTHER_PERF",
            is_verified=True,
        )
        for i in range(10):
            lead = Lead.objects.create(
                tenant=other_tenant,
                wa_id=encrypt(f"56977{i:05d}"),
                wa_id_hash=f"other_hash_{i:05d}",
            )
            ChatSession.objects.create(
                tenant=other_tenant,
                lead=lead,
                status=ChatSession.Status.BOT,
            )

        client = Client()
        with OVERM:
            with self.assertNumQueries(2):
                response = client.get("/api/dashboard/leads/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            len(data["leads"]),
            10,
            "Se esperaban solo 10 sesiones del tenant principal",
        )

    def test_dashboard_max_limit_50(self) -> None:
        """
        ARRANGE: 60 sesiones en el tenant (más que el límite de 50).
        ACT: GET al dashboard.
        ASSERT: Máximo 50 sesiones retornadas. Max 2 queries.
        """
        self._create_bulk_sessions(count=60)

        client = Client()
        with OVERM:
            with self.assertNumQueries(2):
                response = client.get("/api/dashboard/leads/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            len(data["leads"]),
            50,
            "El dashboard debe limitar a 50 sesiones máximo",
        )
