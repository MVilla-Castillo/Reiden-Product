export interface Metrics {
  responseTime: { value: string; trend: string };
  closeRate: { value: string; trend: string };
  activeLeads: { value: number; trend: string };
  pendingAssignments: { value: number; trend: string };
}

export interface TenantSettings {
  routingMode: 'Auto' | 'Manual';
  updatedAt?: string;
}

export interface Lead {
  id: string;
  name: string;
  vehicle: string;
  source: string;
  received: string;
  status: string;
  urgency: 'high' | 'medium' | 'normal' | 'hito';
}

export interface Salesperson {
  id: string;
  rank: number;
  name: string;
  score: number;
  avatar: string;
}

export interface ClientProfile {
  paymentMethod: string;
  budget: string;
  urgency: string;
  phone: string;
  email: string;
}

export interface ChatSession {
  id: string;
  name: string;
  avatar: string;
  vehicle: string;
  lastMessage: string;
  time: string;
  status: 'Activo' | 'En espera' | 'BOT' | 'PENDING_ASSIGNMENT' | 'CON_VENDEDOR' | 'GANADO' | 'PERDIDO';
  profile: ClientProfile;
}

export interface Message {
  sender: 'cliente' | 'vendedor' | 'bot';
  avatar: string;
  text: string;
  timestamp: string;
}

export interface SendMessageResponse {
  status: string;
  messageObj: Message;
}

export interface AssignLeadResponse {
  status: string;
  agent_id: string;
}
