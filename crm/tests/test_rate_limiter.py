"""
crm/tests/test_rate_limiter.py — Tests para rate limiter DB-based del webhook.

Valida:
- Rate limiting por tenant + wa_id_hash
- Ventana de tiempo (60s)
- Cleanup de registros antiguos
- Concurrencia (no duplica contadores)
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

import pytest
from django.test import TransactionTestCase
from django.utils import timezone

from crm.models import Tenant, WebhookRateLimit
from crm.services.rate_limiter import (
    RateLimitExceeded,
    check_rate_limit,
    cleanup_old_rate_limits,
)


@pytest.mark.django_db
def test_check_rate_limit_allows_under_max(tenant: Tenant) -> None:
    """Un solo request debe ser permitido."""
    assert check_rate_limit(tenant.id, "56912345678", max_requests=5) is True


@pytest.mark.django_db
def test_check_rate_limit_blocks_over_max(tenant: Tenant) -> None:
    """Despues de N requests en la ventana, debe lanzar RateLimitExceeded."""
    max_req = 3
    for _ in range(max_req):
        check_rate_limit(tenant.id, "56912345678", max_requests=max_req)

    with pytest.raises(RateLimitExceeded) as exc_info:
        check_rate_limit(tenant.id, "56912345678", max_requests=max_req)

    assert exc_info.value.retry_after > 0


@pytest.mark.django_db
def test_check_rate_limit_different_wa_id_independent(tenant: Tenant) -> None:
    """Rate limits son independientes por wa_id_hash."""
    max_req = 3
    for _ in range(max_req):
        check_rate_limit(tenant.id, "56911111111", max_requests=max_req)

    assert check_rate_limit(tenant.id, "56922222222", max_requests=max_req) is True


@pytest.mark.django_db
def test_check_rate_limit_different_tenant_independent(tenant: Tenant) -> None:
    """Rate limits son independientes por tenant."""
    tenant2 = Tenant.objects.create(
        nombre_legal="Tenant B",
        rut_empresa="99.999.999-9",
        phone_number_id="56999999999",
        waba_id="WABA_TENANT_B",
        is_verified=True,
    )
    max_req = 3
    for _ in range(max_req):
        check_rate_limit(tenant.id, "56912345678", max_requests=max_req)

    assert check_rate_limit(tenant2.id, "56912345678", max_requests=max_req) is True


@pytest.mark.django_db
def test_cleanup_old_rate_limits(tenant: Tenant) -> None:
    """Registros antiguos deben ser eliminados."""
    old = WebhookRateLimit.objects.create(
        tenant=tenant,
        wa_id_hash="hash_old",
        window_start=timezone.now() - timedelta(hours=2),
        request_count=10,
    )
    new = WebhookRateLimit.objects.create(
        tenant=tenant,
        wa_id_hash="hash_new",
        window_start=timezone.now(),
        request_count=5,
    )

    deleted = cleanup_old_rate_limits(hours=1)

    assert deleted == 1
    assert WebhookRateLimit.objects.filter(id=old.id).exists() is False
    assert WebhookRateLimit.objects.filter(id=new.id).exists() is True


class TestRateLimitConcurrency(TransactionTestCase):
    """Tests de concurrencia para rate limiter."""

    def test_concurrent_requests_same_wa_id_no_overcount(self) -> None:
        """
        10 hilos simultaneos con mismo wa_id no deben generar
        contadores inconsistentes.
        """
        tenant = Tenant.objects.create(
            nombre_legal="Concurrent Tenant",
            rut_empresa="77.777.777-7",
            phone_number_id="56977777777",
            waba_id="WABA_CONCURRENT_RATE",
            is_verified=True,
        )

        barrier = threading.Barrier(10)
        results = []
        errors = []

        def worker(index: int) -> str:
            barrier.wait()
            try:
                check_rate_limit(tenant.id, "56912345678", max_requests=20)
                return "allowed"
            except RateLimitExceeded:
                return "blocked"
            except Exception as e:
                errors.append(str(e))
                return "error"

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, i) for i in range(10)]
            for future in as_completed(futures):
                results.append(future.result())

        allowed = sum(1 for r in results if r == "allowed")
        blocked = sum(1 for r in results if r == "blocked")

        assert allowed + blocked == 10
        assert allowed == 10
        assert len(errors) == 0

        from django.db.models import Sum

        total_count = WebhookRateLimit.objects.filter(
            tenant_id=tenant.id,
        ).aggregate(total=Sum("request_count"))["total"]
        assert total_count == 10

    def test_concurrent_requests_exceeding_max_block_exactly_the_excess(self) -> None:
        """
        50 hilos simultáneos con max_requests=30 deben permitir EXACTAMENTE 30 y
        bloquear EXACTAMENTE 20. Antes del fix A3, la race condition permitía
        que algunos requests sobrantes pasaran (overcount).
        """
        tenant = Tenant.objects.create(
            nombre_legal="Overflow Tenant",
            rut_empresa="55.555.555-5",
            phone_number_id="56955555555",
            waba_id="WABA_OVERFLOW_RATE",
            is_verified=True,
        )

        n_threads = 50
        max_req = 30
        barrier = threading.Barrier(n_threads)
        results: list[str] = []
        errors: list[str] = []
        lock = threading.Lock()

        def worker() -> None:
            barrier.wait()
            try:
                check_rate_limit(tenant.id, "56912345678", max_requests=max_req)
                outcome = "allowed"
            except RateLimitExceeded:
                outcome = "blocked"
            except Exception as e:
                with lock:
                    errors.append(str(e))
                outcome = "error"
            with lock:
                results.append(outcome)

        with ThreadPoolExecutor(max_workers=n_threads) as executor:
            futures = [executor.submit(worker) for _ in range(n_threads)]
            for future in as_completed(futures):
                future.result()

        allowed = sum(1 for r in results if r == "allowed")
        blocked = sum(1 for r in results if r == "blocked")

        # Crítico: el contador de la DB no puede superar el límite tras los rollbacks.
        from django.db.models import Sum

        total_count = (
            WebhookRateLimit.objects.filter(tenant_id=tenant.id).aggregate(
                total=Sum("request_count")
            )["total"]
            or 0
        )

        assert errors == []
        assert allowed + blocked == n_threads
        assert allowed == max_req, f"esperaba {max_req} allowed, obtuvo {allowed}"
        assert blocked == n_threads - max_req
        assert total_count == max_req
