---
name: Clean Architecture & Django Anti-Patterns
description: Reglas estrictas Anti-Junior para la estructuración de código en Django, forzando mantenibilidad y testing.
---

# 🏗️ Clean Architecture & Django Anti-Patterns (CCRM-SAAS)

Esta skill obliga al agente a aplicar principios de Clean Architecture y evitar antipatrones comunes de Django. **Lee y aplica estas reglas antes de escribir cualquier vista (view) o modelo (model).**

## 1. Fat Models, Utility Layers & Thin Views
*   **Prohibido lógica de negocio en `views.py`:** Las vistas solo deben encargarse de desempaquetar el request HTTP, llamar a una función de servicio (`services.py` o métodos del modelo) y devolver un `HttpResponse`/`JsonResponse`.
*   **Encapsulación de Queries (Custom Managers):** Nunca escribas `Lead.objects.filter(tenant_id=...)` en una vista. Todo filtrado complejo o repetitivo debe vivir en un `CustomManager` (ej. `Lead.objects.for_tenant(tenant)`).
*   **Evitar `signals` para lógica core:** Prohibido usar señales de Django (`post_save`, `pre_save`) para lógica de negocio secuencial como "Enviar webhook a Twilio después de guardar el Lead". Las señales ocultan el flujo de control y hacen imposible el testing ordenado. Llama a la tarea de *Cloud Tasks* explícitamente desde la función de servicio.

## 2. Tipado Estricto (MyPy)
*   **Anotación Obligatoria:** Todo método, argumento de función y retorno en Python debe estar anotado (`def process_webhook(payload: dict) -> JsonResponse:`).
*   **Tipos para JSONB:** Usa `TypedDict` o clases de Pydantic para validar y estructurar el diccionario que entra en la base de datos como `fsm_answers`. No confíes en diccionarios crudos `dict[str, Any]`.

## 3. Inmutabilidad (Soft Deletion)
*   **Prohibido `delete()`:** Nunca utilices el método `.delete()` del ORM sobre entidades Core (`Lead`, `ChatSession`). 
*   **Cómo borrar:** Debes implementar una lógica que establezca `is_deleted = True` y asegúrate de que el Manager por defecto siempre excluya estos registros (`queryset.filter(is_deleted=False)`).

## 4. Estilos y Formatting
*   Uso mandatorio de `black` y `isort` mental para la estructura de imports (estándar de la librería, django, terceros, locales).
*   Docs string en cada función pública explicando el parámetro, el retorno y los *Side Effects* (ej. "Encola tarea HTTP", "Inserta registro").

## 5. ORM Anti-Patterns (Prevención N+1)
*   **Prohibido N+1 en Listas:** Todo endpoint que retorne una lista de objetos relacionados (ej. ChatSessions con su Lead y Vendedor) DEBE usar `select_related()` para Foreign Keys simples o `prefetch_related()` para relaciones Many-to-Many/inversas. El dashboard de vendedores cargando 50 chats debe generar máximo 2 queries SQL.
*   **Anotaciones en vez de Python loops:** Para calcular métricas (ej. count de mensajes por sesión, urgency_score promedio), usa `queryset.annotate()` y `aggregate()` del ORM. Prohibido iterar en Python y contar con lógica de aplicación lo que PostgreSQL puede hacer en una sola query.
*   **`only()` y `defer()` para proyecciones:** Cuando necesites sólo 2-3 campos de un modelo pesado (ej. solo `id` y `status` de ChatSession en un listado), usa `ChatSession.objects.only('id', 'status', 'lead_id')` para evitar transferir columnas JSONB pesadas innecesariamente.

## 6. Testing Patterns (pytest-django)
*   **Estructura AAA obligatoria:** Todo test debe seguir el patrón Arrange-Act-Assert. Prohibido mezclar configuración, ejecución y verificación en el mismo bloque.
*   **Factories sobre Fixtures:** Usa `factory_boy` para crear datos de prueba en vez de fixtures de Django (JSON/YAML). Las factories son más legibles, componibles y mantenibles.
*   **Un comportamiento por test:** Cada función de test valida un único comportamiento o caso de borde. Si un test tiene más de 2-3 `assert`, probablemente debe dividirse.
*   **Prohibido HTTP real a Twilio:** Todo código que llame a la API de Twilio debe ser interceptado con `unittest.mock.patch` o la librería `responses`. Los tests deben ser deterministas y no depender de red externa.
