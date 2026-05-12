"""Contenido textual de las guías interactivas (tour onboarding) por pestaña y rol.

Estructura:
    GUIDES[tab][role] = {"title": str, "steps": [GuideStep, ...]}

Cada step:
    {
        "id": str,                   # estable, sirve de key en frontend
        "selector": str,             # query selector CSS (preferir [data-guide='...'])
        "title": str,                # encabezado del tooltip
        "desc": str,                 # descripción concisa (1-2 oraciones)
        "placement": "top"|"bottom"|"left"|"right",  # sugerencia de posición del tooltip
    }
"""

from __future__ import annotations

from typing import Any

VALID_TABS = ("dashboard", "leads", "chat", "reports")
MANAGER_ONLY_TABS = ("dashboard", "reports")


def _step(
    step_id: str,
    selector: str,
    title: str,
    desc: str,
    placement: str = "bottom",
) -> dict[str, str]:
    return {
        "id": step_id,
        "selector": selector,
        "title": title,
        "desc": desc,
        "placement": placement,
    }


GUIDES: dict[str, Any] = {
    "dashboard": {
        "manager": {
            "title": "Guía del Dashboard",
            "steps": [
                _step(
                    "kpis",
                    "[data-guide='dashboard-kpis']",
                    "Indicadores clave (KPIs)",
                    "Tiempo de respuesta, leads pendientes, activos y tasa de cierre en tiempo real.",
                    placement="bottom",
                ),
                _step(
                    "refresh",
                    "[data-guide='dashboard-refresh']",
                    "Refrescar métricas",
                    "Recarga manual de todos los KPIs desde la base de datos.",
                    placement="left",
                ),
                _step(
                    "routing-toggle",
                    "[data-guide='dashboard-routing-toggle']",
                    "Modo de enrutamiento (AUTO / MANUAL)",
                    "AUTO: el sistema reparte leads automáticamente. MANUAL: tú decides quién atiende cada lead.",
                    placement="left",
                ),
                _step(
                    "pending-grid",
                    "[data-guide='dashboard-pending-grid']",
                    "Cola de pendientes",
                    "Leads sin vendedor asignado, listos para asignar uno a uno o por lote.",
                    placement="top",
                ),
            ],
        },
    },
    "leads": {
        "manager": {
            "title": "Guía de Gestor de Leads",
            "steps": [
                _step(
                    "filters",
                    "[data-guide='leads-filters']",
                    "Filtros de búsqueda",
                    "Busca por nombre y filtra por estado, intención de compra y rango de fechas.",
                    placement="bottom",
                ),
                _step(
                    "table",
                    "[data-guide='leads-table']",
                    "Tabla de leads",
                    "Todos los leads del tenant: contacto, intención, presupuesto, método de pago, vehículo, score y estado.",
                    placement="top",
                ),
                _step(
                    "urgency-badge",
                    "[data-guide='leads-urgency-badge']",
                    "Indicador de urgencia",
                    "Mientras más alto el score, más urgente e importante es el lead.",
                    placement="top",
                ),
                _step(
                    "status-badge",
                    "[data-guide='leads-status-badge']",
                    "Estado del lead (FSM)",
                    "Etiqueta del paso en el ciclo: PENDING_ASSIGNMENT, CON_VENDEDOR, GANADO, PERDIDO.",
                    placement="top",
                ),
                _step(
                    "assign-col",
                    "[data-guide='leads-assign-col']",
                    "Asignar a vendedor",
                    "Dropdown por fila para asignar el lead y disparar notificación al vendedor.",
                    placement="left",
                ),
                _step(
                    "batch-toolbar",
                    "[data-guide='leads-batch-select']",
                    "Acciones por lote",
                    "Marca varios leads aquí para desbloquear la barra de acciones: asignar en masa o marcar Ganados/Perdidos a la vez.",
                    placement="bottom",
                ),
                _step(
                    "pagination",
                    "[data-guide='leads-pagination']",
                    "Paginación",
                    "Controles Anterior/Siguiente para navegar la tabla de leads.",
                    placement="top",
                ),
            ],
        },
        "salesperson": {
            "title": "Guía de Mis Leads",
            "steps": [
                _step(
                    "table",
                    "[data-guide='leads-table']",
                    "Tus leads asignados",
                    "Los leads que el gerente o el sistema te asignaron. Solo ves tu cartera.",
                    placement="top",
                ),
                _step(
                    "filters",
                    "[data-guide='leads-filters']",
                    "Filtros para priorizar",
                    "Búsqueda por nombre y filtros por estado, intención y fechas.",
                    placement="bottom",
                ),
                _step(
                    "urgency-badge",
                    "[data-guide='leads-urgency-badge']",
                    "Urgencia (horas sin atender)",
                    "Mientras más alto el score, más urgente e importante es el lead.",
                    placement="top",
                ),
                _step(
                    "status-badge",
                    "[data-guide='leads-status-badge']",
                    "Estado del lead",
                    "Etiqueta del estado actual: CON_VENDEDOR, GANADO o PERDIDO.",
                    placement="top",
                ),
            ],
        },
    },
    "chat": {
        "manager": {
            "title": "Guía de Conversaciones",
            "steps": [
                _step(
                    "filters",
                    "[data-guide='chat-filters']",
                    "Filtros de chats",
                    "Botones rápidos: Todos, Activos, Ganados, Perdidos, Abandonados.",
                    placement="bottom",
                ),
                _step(
                    "list",
                    "[data-guide='chat-list']",
                    "Lista de conversaciones",
                    "Panel izquierdo con chats: cliente, estado, vehículo y última actividad. Click abre el chat.",
                    placement="right",
                ),
                _step(
                    "messages",
                    "[data-guide='chat-messages']",
                    "Ventana de mensajes",
                    "Historial completo con estado de entrega: ⏳ pending, ✓ enviado, ✓✓ leído, ✗ fallido. Click reintenta fallidos.",
                    placement="left",
                ),
                _step(
                    "input",
                    "[data-guide='chat-input']",
                    "Enviar mensaje y adjuntar",
                    "Caja de texto, botón 📎 para adjuntar (imágenes hasta 16MB, videos hasta 100MB) y botón Enviar.",
                    placement="top",
                ),
                _step(
                    "lead-drawer",
                    "[data-guide='chat-lead-drawer']",
                    "Ficha del lead",
                    "Panel derecho: vehículo, método de pago, presupuesto, intención, creado en y vendedor.",
                    placement="left",
                ),
                _step(
                    "status-actions",
                    "[data-guide='chat-status-actions']",
                    "Cierre del lead",
                    "Botones verde 'Ganado' y rojo 'Perdido' (pide motivo). Marca el lead y actualiza métricas.",
                    placement="left",
                ),
            ],
        },
        "salesperson": {
            "title": "Guía de Conversaciones",
            "steps": [
                _step(
                    "filters",
                    "[data-guide='chat-filters']",
                    "Filtros de chats",
                    "Botones rápidos: Todos, Activos, Ganados, Perdidos, Abandonados.",
                    placement="bottom",
                ),
                _step(
                    "list",
                    "[data-guide='chat-list']",
                    "Tus conversaciones",
                    "Tus chats asignados, ordenados por última actividad.",
                    placement="right",
                ),
                _step(
                    "messages",
                    "[data-guide='chat-messages']",
                    "Ventana de mensajes",
                    "Historial con estado de entrega. Click reintenta fallidos.",
                    placement="left",
                ),
                _step(
                    "input",
                    "[data-guide='chat-input']",
                    "Enviar mensaje y adjuntar",
                    "Caja de texto, botón 📎 (imágenes 16MB, videos 100MB) y botón Enviar.",
                    placement="top",
                ),
                _step(
                    "lead-drawer",
                    "[data-guide='chat-lead-drawer']",
                    "Ficha del lead",
                    "Vehículo, presupuesto, método de pago, intención y fecha.",
                    placement="left",
                ),
                _step(
                    "status-actions",
                    "[data-guide='chat-status-actions']",
                    "Cerrar el lead",
                    "Botones 'Ganado' (verde) y 'Perdido' (rojo, pide motivo).",
                    placement="left",
                ),
            ],
        },
    },
    "reports": {
        "manager": {
            "title": "Guía de Reportes",
            "steps": [
                _step(
                    "date-filter",
                    "[data-guide='reports-date-filter']",
                    "Filtro de fechas",
                    "Presets: Hoy, Semana, Mes, Año, Todo + selector personalizado desde-hasta.",
                    placement="bottom",
                ),
                _step(
                    "kpis",
                    "[data-guide='reports-kpis']",
                    "KPIs del período",
                    "Total leads, ganados, perdidos, tasa de cierre y tiempo de primera respuesta del período.",
                    placement="bottom",
                ),
                _step(
                    "leaderboard",
                    "[data-guide='reports-leaderboard']",
                    "Leaderboard de vendedores",
                    "Ranking con medals (🥇🥈🥉) por asignados, ganados, perdidos, win rate y respuesta.",
                    placement="top",
                ),
                _step(
                    "detail-cards",
                    "[data-guide='reports-detail-cards']",
                    "Detalle por vendedor",
                    "Cards con barra de win rate (verde ≥60%, naranja 40-59%, rojo <40%) y stats personales.",
                    placement="top",
                ),
            ],
        },
    },
}
