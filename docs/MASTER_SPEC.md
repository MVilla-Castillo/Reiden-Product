# MASTER_SPEC: CCRM-SAAS Automotriz

## 1. Objetivo y Visión
Transformar la gestión de leads de automotoras mediante un CRM Conversacional (CCRM) que garantice una respuesta inmediata (Speed to Lead) y una calificación de prospectos determinista antes de la intervención humana.

### Criterios de Éxito (KPIs)
* **Tiempo de Respuesta:** 100% de los leads atendidos por el bot en < 2 segundos.
* **Calificación:** 0% de leads pasados a vendedores sin presupuesto o modelo definido.
* **Adopción:** Interfaz de bandeja de entrada que permita responder en < 10 segundos.

---

## 2. Definición del Dominio (Entidades de Negocio)
* **Tenant (Automotora):** Entidad legal que contrata el servicio. Define sus propias reglas de ruteo.
* **Lead (Prospecto):** Cliente interesado. Su identidad está protegida pero es trazable.
* **ChatSession:** El ciclo de vida de una conversación. Pasa por estados (Bot -> Vendedor -> Cierre).
* **Vendedor:** Operador humano encargado de cerrar la venta tras el triage del bot.

---

## 3. Alcance y Restricciones (Scope)
* **Fuera de Alcance:** Gestión de stock físico, pasarela de pagos, marketing masivo (Spam), App móvil nativa.
* **Interfaz:** Optimizado exclusivamente para Web de Escritorio (Desktop).

---

## 4. Máquina de Estados Finita (FSM) - Detalle Lógico
El bot guía al usuario mediante opciones cerradas (botones/listas) para evitar ambigüedad. El flujo se inicia con un mensaje precargado: "Quiero info".

| Estado | Pregunta / Acción | Transición | Opciones (Botones) |
| :--- | :--- | :--- | :--- |
| **INICIAL** | Recepción de "Quiero info" | -> VEHICLE_TYPE | - |
| **VEHICLE_TYPE** | ¿Qué tipo de auto buscas? | -> PAYMENT_METHOD | City Car, SUV, Sedán, Pick-up |
| **PAYMENT_METHOD** | Formato de pago | -> BUDGET_RANGE | Contado, Crédito, Retoma |
| **BUDGET_RANGE** | Presupuesto estimado | -> PURCHASE_INTENT | < 6M, 7M a 14M, 15M o más |
| **PURCHASE_INTENT** | Intención de compra | -> QUALIFIED | Hoy, Esta semana, Mes o más |

**Reglas de Reintento y Validación:**
* **Solo Texto:** Cada paso solo admite texto/botones. Si se envía una imagen/audio, el bot envía un warning pidiendo corregir.
* **Límite de Advertencias:** Se permite hasta 2 reintentos con warning. Al 3er error, el bot deja de enviar el warning y queda en espera pasiva del paso actual.
* **Inactividad:** Si se cumple el tiempo designado, la sesión pasa a `ABANDONO_BOT`.

---

## 5. Lógica de Dominio y Algoritmos
### 5.1 Cálculo de Urgency Score (Priorización)
Puntaje calculado de forma determinista al finalizar el flujo:
* **Prioridad Máxima (Score 100):** Si `PURCHASE_INTENT` == "Hoy".
* **Intención Temporal:** `Esta semana` (+20 pts), `Mes o más` (+10 pts).
* **Bono por Presupuesto:** `< 6M` (+10 pts), `7M a 14M` (+20 pts), `15M o más` (+40 pts).
* **Bono por Pago:** `Crédito` (+20 pts).
* **Score máximo:** El score puede exceder 100. 

*Nota: La suma total máxima (excluyendo el "Hoy" absoluto) determina la posición en el Dashboard.*

### 5.2 Reglas de Ruteo
* **Modo Manual:** El Gerente asigna leads desde una cola de pendientes.
* **Modo Auto (Round-Robin):** El sistema asigna al siguiente vendedor disponible con menor carga de chats activos.

---

## 6. Historias de Usuario
*(Mantener aquí tus historias de Cliente, Gerente y Vendedor)*