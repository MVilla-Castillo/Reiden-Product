import jwt
from datetime import datetime, timedelta
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST


def _get_or_create_dev_users():
    """Crea usuarios de prueba si no existen."""
    from crm.models import Tenant, AppUser

    tenant, _ = Tenant.objects.get_or_create(
        rut_empresa="12345678-9",
        defaults={
            "nombre_legal": "Reidenbach Demo",
            "phone_number_id": "+14155238886",
            "waba_id": "WH_REIDENBACH_001",
        },
    )

    manager, created = AppUser.objects.get_or_create(
        email="manager@reidenbach.com",
        defaults={
            "tenant": tenant,
            "role": AppUser.Role.MANAGER,
            "oidc_sub": "dev-manager-sub",
            "oidc_issuer": "dev.local",
            "is_active": True,
        },
    )

    salesperson, created = AppUser.objects.get_or_create(
        email="seller@reidenbach.com",
        defaults={
            "tenant": tenant,
            "role": AppUser.Role.SALESPERSON,
            "oidc_sub": "dev-salesperson-sub",
            "oidc_issuer": "dev.local",
            "is_active": True,
        },
    )

    return tenant, manager, salesperson


def _generate_dev_jwt(user, role: str) -> str:
    """Genera un JWT válido para desarrollo local."""
    payload = {
        "sub": user.oidc_sub,
        "iss": "dev.local",
        "aud": "dev-client-id",
        "email": user.email,
        "role": role,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=7),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


@csrf_exempt
@require_GET
def dev_login_manager(request):
    """
    Endpoint bypass para desarrollo local.
    GET /api/auth/dev/login/manager/
    Retorna: { token: "eyJ...", user: { email, role, name } }
    """
    tenant, manager, _ = _get_or_create_dev_users()
    token = _generate_dev_jwt(manager, "MANAGER")

    return JsonResponse(
        {
            "token": token,
            "user": {
                "id": str(manager.id),
                "email": manager.email,
                "role": "manager",
                "name": "Javier Reidenbach",
            },
            "tenant_id": str(tenant.id),
        }
    )


@csrf_exempt
@require_GET
def dev_login_salesperson(request):
    """
    Endpoint bypass para desarrollo local.
    GET /api/auth/dev/login/salesperson/
    Retorna: { token: "eyJ...", user: { email, role, name } }
    """
    tenant, _, salesperson = _get_or_create_dev_users()
    token = _generate_dev_jwt(salesperson, "SALESPERSON")

    return JsonResponse(
        {
            "token": token,
            "user": {
                "id": str(salesperson.id),
                "email": salesperson.email,
                "role": "agent",
                "name": "Carlos Vendedor",
            },
            "tenant_id": str(tenant.id),
        }
    )
