"""URL fixture para tests de handler500 — solo usado en tests."""
from django.urls import path
from django.http import HttpResponse

from core.views.errors import handler404 as handler404  # noqa: F401
from core.views.errors import handler500 as handler500  # noqa: F401


def _raise_500(request):
    raise RuntimeError("Error de prueba para test_handler500")


urlpatterns = [
    path("trigger-500/", _raise_500),
]
