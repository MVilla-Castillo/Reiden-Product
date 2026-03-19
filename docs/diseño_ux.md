# Skill de Diseño UX: "ERP Corporativo - Dark & Soft Orange"

**Versión:** 1.1
**Objetivo:** Guía de estilo y componentes para generación de interfaces profesionales de nivel Big Tech.

---

## 1. Identidad Visual (Sistema de Colores)

Para este diseño corporativo, el contraste se basa en tonos profundos y acentos cálidos no vibrantes.

-   **Deep Charcoal / Black (`#1A1A1B`):** Color primario para Sidebars, Headers y superficies de navegación.
-   **Soft Orange (`#F39C12` / `#E67E22`):** Color de acción y énfasis. Debe usarse con moderación para mantener la sobriedad.
-   **Background Grey (`#F8F9FA`):** Fondo de la zona de trabajo principal.
-   **Pure White (`#FFFFFF`):** Fondo de tarjetas (cards), inputs de formulario y contenedores de datos.
-   **Borders (`#DCDDE1`):** Gris suave para líneas divisorias y bordes de inputs.

---

## 2. Layout y Estructura (Arquitectura de Información)

### 2.1 Sidebar (Navegación Lateral)
-   **Fondo:** `#1A1A1B` (Negro carbón).
-   **Logo:** Ubicado en el tope superior, texto o icono en `Soft Orange`.
-   **Items de Menú:**
    -   **Estado Inactivo:** Texto blanco o gris claro con opacidad al 70%.
    -   **Estado Hover/Activo:** Fondo ligeramente más claro que el sidebar, con un "indicator bar" vertical de 3px a la izquierda en `Soft Orange`.
-   **Iconografía:** Outline (lineal) de 1.5px de grosor.

### 2.2 Dashboard Overview (Kpis y Gráficos)
-   **KPI Cards:** Contenedores blancos con `border-radius: 8px`. El valor numérico debe resaltar en negrita (Black).
-   **Gráficos de Línea/Barras:**
    -   Ejes y Grid: Gris muy tenue.
    -   Serie Principal: `Soft Orange`.
    -   Serie Secundaria: `Deep Charcoal` (con opacidad).
-   **Tooltips:** Fondo negro con texto blanco y bordes redondeados.

---

## 3. Especificación de Componentes de Formulario

Basado en la estructura de "Add New Customer", aplicar las siguientes reglas:

### 3.1 Cabecera de Formulario
-   **Banner Superior:** Fondo `Deep Charcoal`.
-   **Título:** "AÑADIR NUEVO [ENTIDAD]" en mayúsculas, color blanco, peso semibold.
-   **Tabs de Navegación:** Pestañas estilo "Flat". La pestaña activa muestra un subrayado (border-bottom) de 2px en `Soft Orange`.

### 3.2 Campos de Entrada (Inputs)
-   **Label:** Texto arriba del input, color `#2D3436`, tamaño pequeño (12px-13px).
-   **Input Box:** Borde gris claro. Al hacer `focus`, el borde cambia a `Soft Orange`.
-   **Required Badge:** Un pequeño tag al lado del label con fondo `Soft Orange` y texto blanco que diga "Requerido".
-   **Atajos (Shortcuts):** Texto sutil al lado del label (ej: "Presione F2 para buscar") en gris medio.

### 3.3 Controles de Selección
-   **Toggles (Switches):** Fondo gris cuando está apagado; fondo `Soft Orange` cuando está encendido (`active`).
-   **Checkboxes:** Bordes redondeados de 2px. Al estar marcado, fondo `Soft Orange` con check blanco.

---

## 4. Reglas de Implementación para el Agente (Prompt Injection)

Cuando generes código Frontend basado en esta skill:

1.  **Prioridad de Espaciado:** Usa un sistema de espaciado consistente (8px, 16px, 24px). No amontones elementos.
2.  **Validación Junior-Filter:** No generes formularios sin estados de error. Si un campo es obligatorio y está vacío, el borde debe ser rojo (`#E74C3C`), pero el enfoque principal de éxito siempre es `Soft Orange`.
3.  **Accesibilidad:** Asegúrate de que el contraste entre el texto blanco y el fondo negro del sidebar cumpla con los estándares WCAG.
4.  **Micro-interacciones:** Los botones con fondo `Soft Orange` deben oscurecerse un 10% en el estado `:hover`.

---

## 5. Casos de Borde y Resiliencia (Trade-offs)

-   **Fallback de Carga:** Mientras los datos del dashboard cargan, utiliza *Skeletons* con un pulso gris suave, no spinners genéricos.
-   **Empty States:** Si no hay datos en las tablas, muestra una ilustración minimalista en tonos grises con un botón de acción en `Soft Orange` (ej: "Crear primer registro").