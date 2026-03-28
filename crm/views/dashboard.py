"""
crm/views/dashboard.py — API GET Endpoints para el Dashboard de Ventas.

Este módulo cumple el requisito del Sprint 5: proveer listados de ChatSessions 
de leads ultracalificados (urgency_score alto), delegando el filtrado pesado
al Custom Manager para respetar la Clean Architecture.
"""
from django.http import JsonResponse, HttpRequest
from crm.models import ChatSession

def leads_dashboard_api(request: HttpRequest) -> JsonResponse:
    """
    GET /api/dashboard/leads/
    
    Obtiene las ChatSessions activas ordenadas por urgency_score.
    Diseñado para el polling desde Angular.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)
        
    # Validar tenant inyectado por el middleware
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({"error": "Tenant no definido."}, status=403)

    # Clean Architecture: El filtro de Tenant se delega al Manager activo (RLS Lógico)
    # Ordenamos por score descendente (los de 100 van primero)
    # limitamos a 50 para evitar sobrecarga en polling.
    sessions = (
        ChatSession.tenant_objects
        .for_tenant(tenant.id)
        .order_by('-urgency_score', '-updated_at')
        .select_related('lead')
        [:50]
    )

    data = []
    for s in sessions:
        data.append({
            "session_id": str(s.id),
            "lead_phone": s.lead.wa_id,
            "status": s.status,
            "urgency_score": s.urgency_score,
            "fsm_step": s.fsm_answers.get('current_step', 'UNKNOWN'),
            "intent": s.fsm_answers.get('intent'),
            "timeline": s.fsm_answers.get('timeline'),
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        })

    return JsonResponse({"leads": data}, status=200)
