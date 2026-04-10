import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import {
  AssignLeadResponse,
  SessionDto,
  BackendMessage,
  MetricsResponse,
  SalespersonDto,
  SendMessageResponse,
  TenantSettings
} from '../../core/models/crm.models';

@Injectable({
  providedIn: 'root'
})
export class CrmApiService {
  private readonly baseUrl = 'http://localhost:8000/api';
  private readonly http = inject(HttpClient);

  // ==========================================
  // DASHBOARD GERENCIAL
  // ==========================================

  getMetrics(filters: any = {}): Observable<MetricsResponse> {
    let queryStr = '';
    if (filters.date_from && filters.date_to) {
      queryStr = `?date_from=${filters.date_from}&date_to=${filters.date_to}`;
    } else {
      // Para evadir el error 400 del Backend con `date_filter=all`, enviamos fechas duras
      const today = new Date();
      const past = new Date();
      past.setFullYear(today.getFullYear() - 1); // Traer el último año por defecto
      
      const toIso = (d: Date) => d.toISOString().split('T')[0];
      queryStr = `?date_from=${toIso(past)}&date_to=${toIso(today)}`;
    }
    return this.http.get<MetricsResponse>(`${this.baseUrl}/dashboard/metrics/${queryStr}`);
  }

  getTenantSettings(): Observable<TenantSettings> {
    return this.http.get<TenantSettings>(`${this.baseUrl}/dashboard/settings/`);
  }

  updateTenantSettings(routingMode: 'AUTO' | 'MANUAL'): Observable<TenantSettings> {
    return this.http.patch<TenantSettings>(`${this.baseUrl}/dashboard/settings/`, { routing_mode: routingMode });
  }

  getPendingLeads(): Observable<SessionDto[]> {
    return this.http.get<{pending_leads: SessionDto[]}>(`${this.baseUrl}/dashboard/leads/pending/`)
      .pipe(map(res => res.pending_leads));
  }

  getSalespeople(): Observable<SalespersonDto[]> {
    return this.http.get<{salespeople: SalespersonDto[]}>(`${this.baseUrl}/dashboard/salespeople/`)
      .pipe(map(res => res.salespeople));
  }

  // ==========================================
  // PANEL VENDEDOR (CHAT)
  // ==========================================

  getMyChats(): Observable<SessionDto[]> {
    return this.http.get<{leads: SessionDto[]}>(`${this.baseUrl}/dashboard/leads/`)
      .pipe(map(res => res.leads));
  }

  getMessages(sessionId: string, limit: number = 50): Observable<BackendMessage[]> {
    return this.http.get<{messages: BackendMessage[]}>(`${this.baseUrl}/dashboard/leads/${sessionId}/messages/?limit=${limit}`)
      .pipe(map(res => res.messages));
  }

  sendMessage(sessionId: string, text: string): Observable<SendMessageResponse> {
    return this.http.post<SendMessageResponse>(`${this.baseUrl}/dashboard/leads/${sessionId}/messages/send/`, { body: text });
  }

  assignLead(sessionId: string, salespersonId?: string): Observable<AssignLeadResponse> {
    const payload = salespersonId ? { salesperson_id: salespersonId } : {};
    return this.http.post<AssignLeadResponse>(`${this.baseUrl}/dashboard/leads/${sessionId}/assign/`, payload);
  }

  reassignLead(sessionId: string, newSalespersonId: string | null): Observable<AssignLeadResponse> {
    return this.http.patch<AssignLeadResponse>(`${this.baseUrl}/dashboard/leads/${sessionId}/reassign/`, {
      salesperson_id: newSalespersonId
    });
  }

  updateSessionStatus(sessionId: string, status: 'GANADO' | 'PERDIDO', lostReason?: string): Observable<any> {
    const payload: any = { status };
    if (status === 'PERDIDO' && lostReason) {
      payload.lost_reason = lostReason;
    }
    return this.http.patch<any>(`${this.baseUrl}/dashboard/leads/${sessionId}/status/`, payload);
  }
}
