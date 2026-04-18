import uuid
from typing import Any

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.db.models import JSONField
from django.contrib.postgres.indexes import GinIndex


class ActiveManager(models.Manager):
    """
    Manager Customizado para excluir registros eliminados por Soft-Delete.
    Haciendo cumplir la regla Clean Architecture.
    """

    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().filter(is_deleted=False)


class TenantManager(models.Manager):
    """
    Manager base para enforzar el aislamiento (RLS Lógico).
    Requiere pasar el tenant_id actual explícitamente.
    Ej: Lead.tenant_objects.for_tenant(tenant)
    """

    def for_tenant(self, tenant_id: uuid.UUID) -> models.QuerySet:
        return self.get_queryset().filter(tenant_id=tenant_id)


class ActiveTenantManager(TenantManager):
    """
    Combina el aislamiento de Tenant con el Soft-Delete.
    """

    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().filter(is_deleted=False)


class AppUserManager(BaseUserManager):
    """Manager requerido por Django para usuarios customizados."""

    def create_user(
        self, email: str, password: str = None, **extra_fields: Any
    ) -> "AppUser":
        if not email:
            raise ValueError("El email debe estar configurado")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, email: str, password: str = None, **extra_fields: Any
    ) -> "AppUser":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(email, password, **extra_fields)


class Tenant(models.Model):
    """La raíz de aislamiento de datos y configuración del negocio."""

    class RoutingMode(models.TextChoices):
        MANUAL = "MANUAL", "Manual"
        AUTO = "AUTO", "Auto"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre_legal = models.CharField(max_length=255, verbose_name="Nombre legal")
    rut_empresa = models.CharField(
        max_length=50, unique=True, verbose_name="RUT empresa"
    )
    phone_number_id = models.CharField(
        max_length=100, unique=True, verbose_name="Phone Number ID"
    )
    waba_id = models.CharField(
        max_length=100, unique=True, db_index=True, verbose_name="WABA ID"
    )
    routing_mode = models.CharField(
        max_length=10,
        choices=RoutingMode.choices,
        default=RoutingMode.MANUAL,
        verbose_name="Modo de enrutamiento",
    )
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return str(self.nombre_legal)


class AppUser(AbstractBaseUser, PermissionsMixin):
    """Implementación del RBAC y Gamificación vía Google Workspace (OIDC Stateless)."""

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        MANAGER = "MANAGER", "Manager"
        SALESPERSON = "SALESPERSON", "Salesperson"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Aceptamos null=True temporalmente si usamos createsuperuser, pero en OIDC no será nulo.
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="users", null=True, blank=True
    )
    oidc_sub = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text="Google Subject ID (sub)",
    )
    oidc_issuer = models.CharField(
        max_length=100,
        db_index=True,
        null=True,
        blank=True,
        help_text="Origen del Subject (ej. accounts.google.com)",
    )
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.SALESPERSON
    )
    email = models.EmailField(unique=True)

    # Flags required by Django Admin
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = AppUserManager()
    tenant_objects = TenantManager()  # Para listar usuarios del mismo Tenant

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self) -> str:
        return str(self.email)


class Lead(models.Model):
    """Identidad del prospecto con privacidad garantizada."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="leads")
    wa_id_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Hash SHA-256 para búsqueda O(1) en webhooks",
    )
    wa_id = models.CharField(
        max_length=255,
        help_text="ID de WhatsApp cifrado con AES-256 (privacidad PII)",
    )
    first_name = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Nombre"
    )
    last_interaction = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    objects = TenantManager()
    active_objects = ActiveManager()
    tenant_objects = TenantManager()

    def __str__(self) -> str:
        return f"Lead-{self.id.hex[:8]}"


class ChatSession(models.Model):
    """Entidad de alta concurrencia. Contiene la FSM y base para métricas."""

    class Status(models.TextChoices):
        BOT = "BOT", "Bot"
        PENDING_ASSIGNMENT = "PENDING_ASSIGNMENT", "Pending Assignment"
        CON_VENDEDOR = "CON_VENDEDOR", "Con Vendedor"
        GANADO = "GANADO", "Ganado"
        PERDIDO = "PERDIDO", "Perdido"
        ABANDONO_BOT = "ABANDONO_BOT", "Abandono Bot"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="chat_sessions"
    )
    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name="chat_sessions"
    )
    salesperson = models.ForeignKey(
        AppUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_sessions",
        verbose_name="Vendedor",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.BOT, verbose_name="Estado"
    )
    fsm_answers = JSONField(default=dict, help_text="Ficha del Cliente (respuestas)")
    urgency_score = models.IntegerField(default=0, db_index=True)
    last_fsm_step = models.CharField(max_length=100, blank=True, null=True)
    last_client_message_at = models.DateTimeField(blank=True, null=True)
    last_message_timestamp = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Timestamp nativo de Twilio del último mensaje procesado (RNF-03)",
    )
    lost_reason = models.CharField(max_length=255, blank=True, null=True)
    assigned_at = models.DateTimeField(
        blank=True, null=True, help_text="Timestamp de asignación a vendedor"
    )
    pending_assignment_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Timestamp cuando el lead completó el FSM y quedó en PENDING_ASSIGNMENT",
    )
    first_response_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Timestamp del primer mensaje OUTBOUND del vendedor",
    )
    closed_at = models.DateTimeField(
        blank=True, null=True, help_text="Timestamp de cierre (GANADO/PERDIDO/ABANDONO)"
    )
    acquisition_source = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Fuente de adquisición (ad, referral, organic)",
    )
    utm_metadata = JSONField(
        default=dict,
        blank=True,
        help_text="Metadatos UTM del referral (utm_source, utm_medium, etc.)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    objects = models.Manager()
    active_objects = ActiveManager()
    tenant_objects = ActiveTenantManager()

    class Meta:
        indexes = [
            GinIndex(fields=["fsm_answers"]),
            models.Index(
                fields=["tenant", "lead", "is_deleted", "status"],
                name="idx_chat_sess_active",
            ),
            models.Index(
                fields=["tenant", "status", "assigned_at"],
                name="idx_chat_sess_assigned",
            ),
            models.Index(
                fields=["tenant", "status", "closed_at"],
                name="idx_chat_sess_closed",
            ),
            models.Index(
                fields=["tenant", "created_at"],
                name="idx_chat_sess_created",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "lead"],
                condition=~models.Q(status__in=["GANADO", "PERDIDO", "ABANDONO_BOT"])
                & models.Q(is_deleted=False),
                name="unique_active_session_per_lead",
            )
        ]

    def __str__(self) -> str:
        return f"Session-{self.id.hex[:8]} - {self.status}"


class Message(models.Model):
    """Registro inmutable de la conversación. (Idempotencia y Trazabilidad)"""

    class Direction(models.TextChoices):
        INBOUND = "INBOUND", "Inbound"
        OUTBOUND = "OUTBOUND", "Outbound"

    class Type(models.TextChoices):
        TEXT = "TEXT", "Text"
        IMAGE = "IMAGE", "Image"
        AUDIO = "AUDIO", "Audio"
        DOCUMENTO = "DOCUMENTO", "Documento"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="messages"
    )
    session = models.ForeignKey(
        ChatSession, on_delete=models.CASCADE, related_name="messages"
    )
    provider_message_id = models.CharField(
        max_length=255, unique=True, help_text="Idempotencia (RNF-03)"
    )
    direction = models.CharField(max_length=10, choices=Direction.choices)
    message_type = models.CharField(
        max_length=10, choices=Type.choices, default=Type.TEXT
    )
    body = models.TextField(help_text="Texto literal o URL firmada")
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)

    objects = models.Manager()
    active_objects = ActiveManager()
    tenant_objects = ActiveTenantManager()

    class Meta:
        # RNF-44: Optimización de carga inicial de mensajes (O(log n))
        indexes = [
            models.Index(fields=["session", "-created_at"]),
        ]
        constraints = []

    def __str__(self) -> str:
        return str(self.provider_message_id)


class AuditLog(models.Model):
    """Telemetría y Anti-Fraude (Event Sourcing parcial). Inmutable: prohibido UPDATE/DELETE."""

    id = models.BigAutoField(
        primary_key=True
    )  # MASTER_SPEC §9.3: BigInt Auto-incremental
    session = models.ForeignKey(
        ChatSession, on_delete=models.CASCADE, related_name="audit_logs"
    )
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="audit_logs"
    )
    actor = models.ForeignKey(
        AppUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions",
    )
    action = models.CharField(
        max_length=50, help_text="Ej: SESSION_START, FSM_TRANSITION, STATUS_CHANGED"
    )
    old_value = JSONField(default=dict)
    new_value = JSONField(default=dict)
    owner_at_time_of_close = models.ForeignKey(
        AppUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_sessions_audit",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()
    tenant_objects = TenantManager()

    def __str__(self) -> str:
        return f"{self.action} on {self.session_id}"


class WebhookRateLimit(models.Model):
    """Rate limiting DB-based para el webhook de Twilio (sin Redis)."""

    id = models.BigAutoField(primary_key=True)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="webhook_rate_limits"
    )
    wa_id_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA-256 hash del WaId para agrupar por remitente",
    )
    window_start = models.DateTimeField(
        db_index=True,
        help_text="Inicio de la ventana de rate limit",
    )
    request_count = models.IntegerField(
        default=1,
        help_text="Cantidad de requests en la ventana actual",
    )

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "wa_id_hash", "window_start"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "wa_id_hash", "window_start"],
                name="unique_rate_limit_per_window",
            ),
        ]

    def __str__(self) -> str:
        return f"RateLimit-{self.wa_id_hash[:8]} count={self.request_count}"
