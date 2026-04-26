from django.contrib import admin
from core.crypto import decrypt
from crm.models import Tenant, AppUser, Lead, ChatSession, Message, AuditLog


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = (
        "nombre_legal",
        "rut_empresa",
        "phone_number_id",
        "is_verified",
        "created_at",
    )
    search_fields = ("nombre_legal", "rut_empresa")


@admin.register(AppUser)
class AppUserAdmin(admin.ModelAdmin):
    list_display = ("email", "role", "tenant", "is_staff", "is_active")
    search_fields = ("email",)
    list_filter = ("role", "is_staff")


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "wa_id_hash", "first_name", "last_interaction")
    search_fields = ("wa_id_hash", "first_name")
    list_filter = ("tenant",)
    readonly_fields = ("wa_id_display",)

    def wa_id_display(self, obj: Lead) -> str:
        return decrypt(obj.wa_id)

    wa_id_display.short_description = "wa_id (decrypted)"


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "lead",
        "tenant",
        "status",
        "urgency_score",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "tenant")
    search_fields = ("lead__wa_id_hash",)
    readonly_fields = ("fsm_answers", "created_at", "updated_at")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "direction", "message_type", "body", "created_at")
    list_filter = ("direction", "message_type")
    search_fields = ("body", "provider_message_id")
    readonly_fields = ("created_at",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "action", "created_at")
    list_filter = ("action",)
    search_fields = ("action",)
    readonly_fields = ("old_value", "new_value", "created_at")
