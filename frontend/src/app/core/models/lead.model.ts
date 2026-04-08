export interface Lead {
  id: string;
  name: string;
  company: string;
  source: LeadSource;
  status: LeadStatus;
  assignedTo: string | null;
  createdAt: Date;
  waitingTime: number;
}

export type LeadSource = 'whatsapp' | 'web' | 'referral' | 'campaign';

export type LeadStatus = 
  | 'bot_flow' 
  | 'pending_assignment' 
  | 'in_commercial_management' 
  | 'won' 
  | 'lost';

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