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
El bot guía al usuario mediante opciones cerradas (botones/listas) para evitar ambigüedad.

| Estado | Pregunta / Acción | Transición |
| :--- | :--- | :--- |
| **INICIO** | Saludo e identificación de interés. | -> VEHICLE_TYPE |
| **VEHICLE_TYPE** | Lista de carrocerías (SUV, Sedán, etc). | -> PAYMENT_METHOD |
| **PAYMENT_METHOD** | Botones: Contado, Crédito, Retoma. | -> BUDGET_RANGE |
| **BUDGET_RANGE** | Rangos de precio predefinidos. | -> PURCHASE_INTENT |
| **PURCHASE_INTENT** | ¿Cuándo compra? (Hoy, Mes, +3 meses). | -> TRIAGE_COMPLETED |

**Reglas de Reintento:** Si el lead envía texto libre en lugar de usar botones, el bot reitera la instrucción hasta 3 veces antes de marcar la sesión como `ABANDONO_BOT`.

---

## 5. Lógica de Dominio y Algoritmos
### 5.1 Cálculo de Urgency Score (Priorización)
Cada lead recibe un puntaje de 0 a 100 basado en:
* **Purchase Intent:** `Hoy` (+50 pts), `Esta semana` (+20 pts).
* **Payment Method:** `Crédito` (+30 pts por rentabilidad financiera).
* **Budget:** Rangos altos (+10 pts).

### 5.2 Reglas de Ruteo
* **Modo Manual:** El Gerente asigna leads desde una cola de pendientes.
* **Modo Auto (Round-Robin):** El sistema asigna al siguiente vendedor disponible con menor carga de chats activos.

---

## 6. Historias de Usuario
*(Mantener aquí tus historias de Cliente, Gerente y Vendedor)*