import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ICrmRepository } from '../../core/ports/crm.repository';
import {
  AssignLeadResponse,
  ChatSession,
  Lead,
  Message,
  Metrics,
  Salesperson,
  SendMessageResponse,
  TenantSettings
} from '../../core/models/crm.models';

@Injectable({
  providedIn: 'root'
})
export class CrmApiService implements ICrmRepository {
  private readonly baseUrl = 'http://localhost:8000/api';
  private readonly http = inject(HttpClient);

  // ==========================================
  // DASHBOARD GERENCIAL
  // ==========================================

  getMetrics(): Observable<Metrics> {
    return this.http.get<Metrics>(`${this.baseUrl}/dashboard/metrics/`);
  }

  getTenantSettings(): Observable<TenantSettings> {
    return this.http.get<TenantSettings>(`${this.baseUrl}/dashboard/settings/`);
  }

  updateTenantSettings(routingMode: 'Auto' | 'Manual'): Observable<TenantSettings> {
    return this.http.patch<TenantSettings>(`${this.baseUrl}/dashboard/settings/`, { routingMode });
  }

  getPendingLeads(): Observable<Lead[]> {
    return this.http.get<Lead[]>(`${this.baseUrl}/dashboard/leads/pending/`);
  }

  getSalespeople(): Observable<Salesperson[]> {
    return this.http.get<Salesperson[]>(`${this.baseUrl}/dashboard/salespeople/`);
  }

  // ==========================================
  // PANEL VENDEDOR (CHAT)
  // ==========================================

  getMyChats(): Observable<ChatSession[]> {
    return this.http.get<ChatSession[]>(`${this.baseUrl}/dashboard/leads/`);
  }

  getMessages(sessionId: string): Observable<Message[]> {
    return this.http.get<Message[]>(`${this.baseUrl}/dashboard/leads/${sessionId}/messages/`);
  }

  sendMessage(sessionId: string, text: string): Observable<SendMessageResponse> {
    return this.http.post<SendMessageResponse>(`${this.baseUrl}/dashboard/leads/${sessionId}/messages/send/`, { text });
  }

  assignLead(sessionId: string): Observable<AssignLeadResponse> {
    return this.http.post<AssignLeadResponse>(`${this.baseUrl}/dashboard/leads/${sessionId}/assign/`, {});
  }

  reassignLead(sessionId: string, newSalespersonId: string): Observable<any> {
    return this.http.patch<any>(`${this.baseUrl}/dashboard/leads/${sessionId}/reassign/`, {
      action: 'reassign',
      new_salesperson_id: newSalespersonId
    });
  }

  updateSessionStatus(sessionId: string, status: 'GANADO' | 'PERDIDO'): Observable<any> {
    return this.http.patch<any>(`${this.baseUrl}/dashboard/leads/${sessionId}/status/`, { status });
  }
}
