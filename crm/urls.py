"""
crm/urls.py — URL routing del módulo CRM.

Contiene:
  - /api/webhooks/twilio/ → Endpoint PÚBLICO para recibir mensajes de Twilio.
  - /api/workers/process-message/ → Endpoint PRIVADO para Cloud Tasks worker.

Nota: El OIDCStatelessMiddleware tiene un bypass explícito para ambas rutas.
"""
from django.urls import path

from crm.views.webhook import twilio_webhook_view
from crm.views.worker import process_message_worker_view
from crm.views.dashboard import leads_dashboard_api

urlpatterns = [
    # Sprint 3: Endpoint de Ingesta de Webhooks Twilio (público, validado por firma HMAC)
    path('api/webhooks/twilio/', twilio_webhook_view, name='twilio_webhook'),
    # Sprint 3: Worker de Procesamiento (privado, validado por X-Internal-Secret)
    path('api/workers/process-message/', process_message_worker_view, name='process_message_worker'),
    
    # Sprint 5: Dashboard API (privado, requiere sesión OIDC)
    path('api/dashboard/leads/', leads_dashboard_api, name='dashboard_leads'),
]
