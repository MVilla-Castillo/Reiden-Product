"""
crm/migrations/0007_encrypt_wa_id_field.py — Migración para cifrar wa_id.

Elimina el campo wa_id (texto plano, max_length=50) y añade wa_id (ciphertext, max_length=255).
El backfill copia los datos existentes. La encriptación se maneja en el adapter.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0006_message_is_deleted"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="wa_id_encrypted",
            field=models.CharField(
                default="",
                max_length=255,
                help_text="ID de WhatsApp cifrado con AES-256 (privacidad PII)",
            ),
        ),
        migrations.RunSQL(
            sql="UPDATE crm_lead SET wa_id_encrypted = wa_id WHERE wa_id != ''",
            reverse_sql="UPDATE crm_lead SET wa_id = wa_id_encrypted WHERE wa_id_encrypted != ''",
        ),
        migrations.RemoveField(
            model_name="lead",
            name="wa_id",
        ),
        migrations.RenameField(
            model_name="lead",
            old_name="wa_id_encrypted",
            new_name="wa_id",
        ),
    ]
