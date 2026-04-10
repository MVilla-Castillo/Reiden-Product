import { Observable } from 'rxjs';
import {
  AssignLeadResponse,
  ChatSession,
  Lead,
  Message,
  Metrics,
  Salesperson,
  SendMessageResponse,
  TenantSettings
} from '../models/crm.models';

export interface ICrmRepository {
  // Dashboard
  getMetrics(): Observable<Metrics>;
  getTenantSettings(): Observable<TenantSettings>;
  updateTenantSettings(mode: 'Auto' | 'Manual'): Observable<TenantSettings>;
  getPendingLeads(): Observable<Lead[]>;
  getSalespeople(): Observable<Salesperson[]>;

  // Panel Vendedor (Chat)
  getMyChats(): Observable<ChatSession[]>;
  getMessages(sessionId: string): Observable<Message[]>;
  sendMessage(sessionId: string, text: string): Observable<SendMessageResponse>;
  assignLead(sessionId: string): Observable<AssignLeadResponse>;
  reassignLead(sessionId: string, newSalespersonId: string): Observable<any>;
  updateSessionStatus(sessionId: string, status: 'GANADO' | 'PERDIDO'): Observable<any>;
}
