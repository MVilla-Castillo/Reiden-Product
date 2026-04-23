// Lead (from lead.model.ts consolidated)
export interface Lead {
  id: string;
  name: string;
  company: string;
  source: LeadSource;
  status: string;
  assignedTo: string | null;
  createdAt: Date;
  waitingTime: number;
}

export type LeadSource = 'whatsapp' | 'web' | 'referral' | 'campaign';

export interface SalesPerson {
  id: string;
  name: string;
  email: string;
  activeLeadsCount: number;
}

export interface DashboardMetrics {
  leadsInBotFlow: number;
  pendingAssignment: number;
  leadsInCommercialManagement: number;
  conversions: number;
}

export interface AssignLeadRequest {
  leadId: string;
  salesPersonId: string;
}

// Tenant
export interface TenantSettings {
  tenant_id: string;
  nombre_legal: string;
  routing_mode: 'AUTO' | 'MANUAL';
  is_verified: boolean;
}

// Session y Leads (Unified from Backend)
export interface SessionDto {
  session_id: string;
  lead_phone_hash: string;
  lead_profile_name?: string | null;
  status: string;
  urgency_score: number;
  fsm_step: string;
  vehicle_type?: string;
  payment_method?: string;
  budget_range?: string;
  purchase_intent?: string;
  salesperson_id?: string | null;
  acquisition_source?: string | null;
  assigned_at?: string | null;
  closed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SalespersonDto {
  id: string;
  email: string;
  role: string;
  active_sessions_count: number;
}

// Messaging
export type DeliveryStatus = 'pending' | 'sent' | 'delivered' | 'read' | 'failed';

export interface BackendMessage {
  message_id?: string;
  id?: string;
  direction: 'INBOUND' | 'OUTBOUND';
  message_type?: string;
  body: string;
  created_at: string;
  provider_message_id?: string;
  provider_message_sid?: string;
  delivery_status?: DeliveryStatus;
  is_forwarded?: boolean;
  is_frequently_forwarded?: boolean;
}

export interface SendMessageResponse {
  message_id: string;
  direction: 'INBOUND' | 'OUTBOUND';
  body: string;
  created_at: string;
  provider_message_sid: string;
  delivery_status?: DeliveryStatus;
}

export interface AssignLeadResponse {
  session_id: string;
  status: string;
  salesperson_id: string | null;
  salesperson_name?: string;
  assigned_at?: string;
}

export interface LeadNameHistory {
  old_name: string | null;
  new_name: string | null;
  changed_by: string | null;
  changed_at: string | null;
}

export interface UpdateLeadResponse {
  lead_profile_name: string | null;
  name_history: LeadNameHistory[];
}

// Metrics
export interface MetricsResponse {
  date_from: string;
  date_to: string;
  date_filter: string;
  funnel: {
    total_leads: number;
    completed_fsm: number;
    assigned_leads: number;
    con_vendedor: number;
    pending_assignment: number;
    won_sessions: number;
    lost_sessions: number;
    abandoned_sessions: number;
    conversion_rate_fsm: number;
    conversion_rate_assignment: number;
    win_rate: number;
  };
  fsm_distribution: {
    vehicle_type: Record<string, number>;
    payment_method: Record<string, number>;
    budget_range: Record<string, number>;
    purchase_intent: Record<string, number>;
  };
  urgency_distribution: {
    '0-30': number;
    '31-60': number;
    '61-100': number;
    '100+': number;
  };
  time_metrics: {
    avg_time_to_complete_fsm: number;
    avg_time_to_assign: number;
    avg_time_to_first_response: number;
    avg_time_to_close: number;
  };
  salesperson_performance: Array<{
    salesperson_id: string;
    leads_assigned: number;
    wins: number;
    losses: number;
    win_rate: number;
    avg_first_response_minutes: number;
    ranking_position: number;
  }>;
}
