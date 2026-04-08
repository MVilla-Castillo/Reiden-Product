import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class CrmApiService {
  private baseUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  // 1. Dashboard Gerencial Endpoints
  
  getMetrics(): Observable<any> {
    return this.http.get(`${this.baseUrl}/dashboard/metrics/`);
  }

  getPendingLeads(): Observable<{ pending_leads: any[] }> {
    return this.http.get<{ pending_leads: any[] }>(`${this.baseUrl}/dashboard/leads/pending/`);
  }

  getSalespeople(): Observable<{ salespeople: any[] }> {
    return this.http.get<{ salespeople: any[] }>(`${this.baseUrl}/dashboard/salespeople/`);
  }

  getSettings(): Observable<any> {
    return this.http.get(`${this.baseUrl}/dashboard/settings/`);
  }

  updateSettings(data: { routingMode: string }): Observable<any> {
    return this.http.patch(`${this.baseUrl}/dashboard/settings/`, data);
  }

  // 2. Dashboard Vendedor Endpoints

  getAssignedChats(): Observable<{ leads: any[]; count: number }> {
    return this.http.get<{ leads: any[]; count: number }>(`${this.baseUrl}/dashboard/leads/`);
  }

  getChatMessages(sessionId: string): Observable<{ messages: any[] }> {
    return this.http.get<{ messages: any[] }>(`${this.baseUrl}/dashboard/leads/${sessionId}/messages/`);
  }

  sendMessage(sessionId: string, text: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/dashboard/leads/${sessionId}/messages/send/`, { body: text });
  }

  assignLead(sessionId: string, salespersonId?: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/dashboard/leads/${sessionId}/assign/`, {
      salesperson_id: salespersonId || null
    });
  }

  updateLeadStatus(sessionId: string, status: string): Observable<any> {
    return this.http.patch(`${this.baseUrl}/dashboard/leads/${sessionId}/status/`, { status });
  }
}
