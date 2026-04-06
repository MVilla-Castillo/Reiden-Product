"""
crm/tests/test_metrics.py — Tests para endpoint de métricas del dashboard.

Coverage:
- metrics_api: Métricas agregadas (funnel, FSM distribution, time metrics, performance)

Nota: Tests deshabilitados temporalmente - requieren middleware override en pytest setup.
"""

import pytest


@pytest.mark.skip(reason="Requiere override de MIDDLEWARE en conftest.py")
class TestMetricsApi:
    """Tests para metrics_api endpoint."""

    pass


@pytest.mark.skip(reason="Requiere override de MIDDLEWARE en conftest.py")
class TestMetricsFunnelData:
    """Tests para datos del funnel en métricas."""

    pass


@pytest.mark.skip(reason="Requiere override de MIDDLEWARE en conftest.py")
class TestMetricsSalespersonPerformance:
    """Tests para performance de vendedores."""

    pass
