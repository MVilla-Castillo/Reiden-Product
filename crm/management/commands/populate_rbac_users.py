from django.core.management.base import BaseCommand
from django.db import transaction
from crm.models import Tenant, AppUser


class Command(BaseCommand):
    help = "Pobla datos de prueba para RBAC (empleados: vendedores y gerente)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Limpia usuarios de prueba antes de crear",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clean"]:
            self.stdout.write("🧹 Limpiando usuarios de prueba existentes...")
            AppUser.objects.filter(email__endswith="@test.com").delete()
            Tenant.objects.filter(rut_empresa="11.111.111-1").delete()

        tenant, created = Tenant.objects.get_or_create(
            rut_empresa="11.111.111-1",
            defaults={
                "nombre_legal": "Automotora Test RBAC",
                "phone_number_id": "test_phone_rbac",
                "waba_id": "test_waba_rbac",
            },
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(f"✅ Tenant creado: {tenant.nombre_legal}")
            )
        else:
            self.stdout.write(f"ℹ️  Usando Tenant existente: {tenant.nombre_legal}")

        usuarios = [
            {
                "email": "gerente@test.com",
                "role": AppUser.Role.MANAGER,
                "is_staff": True,
                "oidc_sub": "test_sub_gerente",
                "oidc_issuer": "test_issuer",
            },
            {
                "email": "vendedor1@test.com",
                "role": AppUser.Role.SALESPERSON,
                "is_staff": False,
                "oidc_sub": "test_sub_vendedor1",
                "oidc_issuer": "test_issuer",
            },
            {
                "email": "vendedor2@test.com",
                "role": AppUser.Role.SALESPERSON,
                "is_staff": False,
                "oidc_sub": "test_sub_vendedor2",
                "oidc_issuer": "test_issuer",
            },
        ]

        self.stdout.write("\n📋 Creando usuarios RBAC:\n")
        self.stdout.write("-" * 60)

        for datos in usuarios:
            user, created = AppUser.objects.update_or_create(
                email=datos["email"],
                defaults={
                    "tenant": tenant,
                    "role": datos["role"],
                    "is_staff": datos["is_staff"],
                    "is_active": True,
                    "oidc_sub": datos["oidc_sub"],
                    "oidc_issuer": datos["oidc_issuer"],
                },
            )
            status = "✅ CREADO" if created else "🔄 ACTUALIZADO"
            self.stdout.write(f"{status} | {user.role:12} | {user.email}")

        self.stdout.write("-" * 60)
        self.stdout.write(
            self.style.SUCCESS("\n✅ Poblamiento completado exitosamente!")
        )
        self.stdout.write(
            self.style.WARNING(
                "\n⚠️  Para login OIDC real, necesitas configurar Google Workspace."
            )
        )
        self.stdout.write("   Los usuarios creados usan autenticación OIDC simulada.\n")
