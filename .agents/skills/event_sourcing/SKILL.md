---
name: Event Sourcing (AuditLog & FSM)
description: Reglas para el diseño inmutable del AuditLog y los eventos de la FSM en CCRM-SAAS. Los eventos son hechos históricos; nunca se modifican.
---

# 📜 Event Sourcing (AuditLog & FSM) - CCRM-SAAS

> **Alcance:** Esta skill aplica **exclusivamente** al modelo `AuditLog` y a las transiciones de la FSM en `ChatSession`. No aplica al stack completo (no usamos un Event Store completo).

## 1. Los Eventos son Hechos Inmutables

*   **Prohibido modificar `AuditLog`:** Una vez insertado un registro en `AuditLog`, es un hecho histórico inalterable. Nunca ejecutar `UPDATE` ni `DELETE` sobre esta tabla.
*   **Prohibido el Soft-Delete en AuditLog:** A diferencia de `Lead` y `ChatSession`, el `AuditLog` no tiene `is_deleted`. Su naturaleza de registro histórico lo hace inviolable.
*   **Los campos `old_value` / `new_value` son snapshots:** Deben capturarse como diccionarios JSON con el estado completo relevante en el momento del cambio, no como referencias a IDs que podrían cambiar.

## 2. Estructura de un Evento de Auditoría

Cada transición de estado en `ChatSession` DEBE generar un registro así:

```python
from crm.models import AuditLog

def transition_session_status(session: ChatSession, new_status: str, actor_id: uuid.UUID | None) -> None:
    """
    Avanza el estado de una ChatSession y registra el evento en AuditLog.
    Side Effect: Inserta un registro en AuditLog (inmutable).
    """
    old_status = session.status
    
    with transaction.atomic():
        session.status = new_status
        session.save(update_fields=['status', 'updated_at'])
        
        AuditLog.objects.create(
            tenant=session.tenant,
            session=session,
            actor_id=actor_id,  # None si es el Bot
            action=f"STATUS_CHANGED",
            old_value={"status": old_status},
            new_value={"status": new_status},
        )
```

## 3. Idempotencia de Eventos (Prevención de Duplicados)

*   Los eventos del Webhook de Twilio pueden llegar duplicados. El `provider_message_id` de Twilio es el identificador de idempotencia.
*   Antes de insertar un `Message`, verificar idempotencia con upsert atómico:
    ```python
    # INSERT ... ON CONFLICT (provider_message_id) DO NOTHING
    Message.objects.get_or_create(
        provider_message_id=twilio_message_sid,
        defaults={...}
    )
    # ⚠️ En Webhooks masivos, preferir el Upsert Atómico via SQL raw
    # para evitar race conditions con get_or_create.
    ```

## 4. Correlation IDs para Trazabilidad

*   Cada evento del AuditLog debe poder rastrearse hasta el mensaje de Twilio que lo originó.
*   Incluir el `provider_message_id` como parte del contexto cuando sea posible en `new_value`:
    ```python
    new_value={"status": new_status, "triggered_by": provider_message_id}
    ```

## 5. Consultas sobre el AuditLog

*   **Para Win-Rate:** `AuditLog.objects.filter(action='STATUS_CHANGED', new_value__status='GANADO', actor_id=vendedor_id, tenant=tenant)`
*   **Para Gamificación:** Usar anotaciones ORM sobre `AuditLog` para calcular métricas agregadas. Prohibido cargar todos los logs en memoria Python y calcular con loops.
*   Las consultas sobre el `AuditLog` son de **solo lectura**. Nunca usar el ORM para modificar estos registros.
