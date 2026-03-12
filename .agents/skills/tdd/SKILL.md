---
name: TDD Workflow (pytest-django)
description: Ciclo Red-Green-Refactor con patrones AAA y reglas específicas para testing en CCRM-SAAS (FSM, Twilio mock, 90% coverage).
---

# 🧪 TDD Workflow (CCRM-SAAS)

Aplica el ciclo **Red→Green→Refactor** con `pytest` y `pytest-django`. Esta skill es obligatoria para el Módulo FSM (Sprint 4) donde se exige cobertura ≥ 90%.

## 1. El Ciclo TDD

```
🔴 RED    → Escribe un test que falle describiendo el comportamiento esperado.
    ↓
🟢 GREEN  → Escribe el MÍNIMO código de producción para que el test pase.
    ↓
🔵 REFACTOR → Mejora la claridad y estructura sin romper ningún test.
    ↓
         Repite hasta completar la funcionalidad.
```

**Las 3 Leyes:**
1. Sólo escribir código de producción para hacer pasar un test fallido.
2. Sólo escribir el test justo para demostrar que falla.
3. Sólo escribir el código justo para hacer pasar el test.

## 2. Estructura Obligatoria: Patrón AAA

Todo test en CCRM-SAAS debe seguir **Arrange → Act → Assert**:

```python
def test_fsm_transition_to_bot_completes_payment_step(db, tenant_factory, lead_factory):
    # ARRANGE
    tenant = tenant_factory()
    lead = lead_factory(tenant=tenant)
    session = ChatSession.objects.create(tenant=tenant, lead=lead, status='BOT')

    # ACT
    result = advance_fsm(session, answer='Crédito')

    # ASSERT
    session.refresh_from_db()
    assert session.fsm_answers['payment_method'] == 'Crédito'
    assert session.last_fsm_step == 'BUDGET_RANGE_QUERY'
```

## 3. Reglas Específicas para CCRM-SAAS

*   **Prohibido HTTP real a Twilio:** Todo código que llame a la API de Twilio DEBE ser interceptado:
    ```python
    from unittest.mock import patch

    @patch('crm.services.twilio_client.messages.create')
    def test_bot_sends_interactive_message(mock_twilio, db, ...):
        mock_twilio.return_value.sid = 'SM_fake_123'
        # ... test
        mock_twilio.assert_called_once()
    ```
*   **Tests Transaccionales:** Los tests del Webhook validan que un error hace Rollback y no deja datos huérfanos en `ChatSession` o `Message`.
*   **Un comportamiento por test:** Si un `def test_...` tiene más de 3 `assert`, dividirlo.
*   **Cobertura ≥ 90% para FSM y Enrutamiento:** Al ejecutar `uv run pytest --cov=crm`, el reporte debe mostrar ≥ 90% en los módulos `fsm.py` y `routing.py`.

## 4. Prioridad de Tests

| Prioridad | Tipo                | Ejemplo CCRM-SAAS                                |
|-----------|---------------------|--------------------------------------------------|
| 1         | Happy path          | Lead completa los 4 pasos FSM correctamente      |
| 2         | Error / Rollback    | Twilio falla → ChatSession no se corrompe        |
| 3         | Edge case           | Lead envía texto libre en vez de botón           |
| 4         | Concurrencia        | Dos webhooks del mismo Lead llegan simultáneamente |

## 5. Anti-Patrones

| ❌ No hacer                           | ✅ Hacer en cambio                              |
|--------------------------------------|------------------------------------------------|
| Saltarse el RED (test pasa de entrada) | Verificar que el test FALLA antes de codificar |
| Tests de implementación (cómo)        | Tests de comportamiento (qué hace el sistema)  |
| Fixtures JSON/YAML                    | Factory Boy para datos flexibles               |
| `assert response.status_code == 200`  | Verificar el estado de la BD post-acción       |
