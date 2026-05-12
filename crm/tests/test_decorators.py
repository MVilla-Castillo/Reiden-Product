"""crm/tests/test_decorators.py — Tests AAA para decoradores transversales."""

from __future__ import annotations

from types import SimpleNamespace

from django.http import JsonResponse

from crm.views._decorators import require_tenant


def _make_view(captured: dict):
    """Mini view que registra la request recibida."""

    def view(request, *args, **kwargs):
        captured["called"] = True
        captured["tenant"] = getattr(request, "tenant", None)
        captured["args"] = args
        captured["kwargs"] = kwargs
        return JsonResponse({"ok": True}, status=200)

    return view


class TestRequireTenant:
    def test_returns_403_when_tenant_missing(self):
        # Arrange
        request = SimpleNamespace()  # sin atributo tenant
        captured: dict = {}
        view = require_tenant(_make_view(captured))

        # Act
        response = view(request)

        # Assert
        assert response.status_code == 403
        assert response.headers["Content-Type"].startswith("application/json")
        assert "Tenant" in response.content.decode()
        assert captured.get("called") is not True

    def test_returns_403_when_tenant_is_none(self):
        # Arrange
        request = SimpleNamespace(tenant=None)
        captured: dict = {}
        view = require_tenant(_make_view(captured))

        # Act
        response = view(request)

        # Assert
        assert response.status_code == 403
        assert captured.get("called") is not True

    def test_passthrough_when_tenant_present(self):
        # Arrange
        fake_tenant = object()
        request = SimpleNamespace(tenant=fake_tenant)
        captured: dict = {}
        view = require_tenant(_make_view(captured))

        # Act
        response = view(request, 42, kw="value")

        # Assert
        assert response.status_code == 200
        assert captured["called"] is True
        assert captured["tenant"] is fake_tenant
        assert captured["args"] == (42,)
        assert captured["kwargs"] == {"kw": "value"}

    def test_preserves_view_metadata(self):
        # Arrange — el decorator usa @wraps; el wrapper debe conservar __name__.
        def underlying(request):
            return JsonResponse({}, status=200)

        underlying.__name__ = "my_view"

        # Act
        wrapped = require_tenant(underlying)

        # Assert
        assert wrapped.__name__ == "my_view"
        assert wrapped.__wrapped__ is underlying
