"""
crm/migrations/0019_rotate_wa_id_encryption.py — Rotación de la clave Fernet de wa_id.

Lee dos claves desde el entorno:
- OLD_WA_ID_ENCRYPTION_KEY: la clave actual con la que están cifrados los datos
- WA_ID_ENCRYPTION_KEY: la nueva clave a la que se migran los datos

Re-cifra cada Lead.wa_id no vacío. Es idempotente: si la fila ya está cifrada con
la nueva clave (porque la migración corrió antes y se reintentó), se omite.

Si OLD_WA_ID_ENCRYPTION_KEY no está seteada o coincide con la nueva, la migración
es no-op (loguea WARN y retorna). Esto permite aplicar el patch sin rotación
inmediata; basta con redeployar tras setear OLD para iniciar la rotación.

NOTA OPERATIVA: tras éxito + verificación, desetear OLD_WA_ID_ENCRYPTION_KEY del
entorno de producción para evitar reutilizar la clave antigua.
"""

from __future__ import annotations

import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from django.db import migrations

logger = logging.getLogger(__name__)


def _get_keys() -> tuple[bytes, bytes] | None:
    old_key = os.environ.get("OLD_WA_ID_ENCRYPTION_KEY", "").strip()
    new_key = os.environ.get("WA_ID_ENCRYPTION_KEY", "").strip()
    if not old_key:
        logger.warning(
            "0019_rotate_wa_id_encryption: OLD_WA_ID_ENCRYPTION_KEY no seteada — no-op."
        )
        return None
    if not new_key:
        logger.warning(
            "0019_rotate_wa_id_encryption: WA_ID_ENCRYPTION_KEY no seteada — no-op."
        )
        return None
    if old_key == new_key:
        logger.info("0019_rotate_wa_id_encryption: OLD == NEW, nada que rotar — no-op.")
        return None
    return old_key.encode("utf-8"), new_key.encode("utf-8")


def _rotate(apps, schema_editor, *, source_key: bytes, target_key: bytes) -> None:
    Lead = apps.get_model("crm", "Lead")
    source = Fernet(source_key)
    target = Fernet(target_key)

    rotated = 0
    already_target = 0
    failed = 0

    qs = Lead.objects.exclude(wa_id="").only("id", "wa_id")
    for row in qs.iterator(chunk_size=500):
        token = (row.wa_id or "").encode("utf-8")
        if not token:
            continue
        try:
            plaintext = source.decrypt(token)
        except InvalidToken:
            try:
                target.decrypt(token)
                already_target += 1
                continue
            except InvalidToken:
                failed += 1
                logger.error(
                    "0019_rotate_wa_id_encryption: lead_id=%s no descifra ni con OLD ni con NEW",
                    row.id,
                )
                continue
        new_token = target.encrypt(plaintext).decode("utf-8")
        Lead.objects.filter(pk=row.pk).update(wa_id=new_token)
        rotated += 1

    logger.info(
        "0019_rotate_wa_id_encryption: rotated=%d already_target=%d failed=%d",
        rotated,
        already_target,
        failed,
    )


def rotate_forward(apps, schema_editor):
    keys = _get_keys()
    if keys is None:
        return
    old_key, new_key = keys
    _rotate(apps, schema_editor, source_key=old_key, target_key=new_key)


def rotate_reverse(apps, schema_editor):
    keys = _get_keys()
    if keys is None:
        return
    old_key, new_key = keys
    _rotate(apps, schema_editor, source_key=new_key, target_key=old_key)


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0018_add_profile_name_and_forwarded_flags"),
    ]

    operations = [
        migrations.RunPython(rotate_forward, rotate_reverse),
    ]
