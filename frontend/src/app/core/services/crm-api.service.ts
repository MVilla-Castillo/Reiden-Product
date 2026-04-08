import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class CrmApiService {
  private baseUrl = environment.apiUrl;

  // Placeholder for OIDC Token handling. For now, we mock the header.
  private get headers(): HttpHeaders {
    return new HttpHeaders({
      'Content-Type': 'application/json',
      // 'Authorization': 'Bearer YOUR_TOKEN_HERE' 
    });
  }

  constructor(private http: HttpClient) {}

  // 1. Dashboard Gerencial Endpoints
  
  getMetrics(): Observable<any> {
    return this.http.get(`${this.baseUrl}/dashboard/metrics/`, { headers: this.headers });
  }

  getPendingLeads(): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}/dashboard/leads/pending/`, { headers: this.headers });
  }

  getSalespeople(): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}/dashboard/salespeople/`, { headers: this.headers });
  }

  getSettings(): Observable<any> {
    return this.http.get(`${this.baseUrl}/dashboard/settings/`, { headers: this.headers });
  }

  updateSettings(data: { routingMode: string }): Observable<any> {
    return this.http.patch(`${this.baseUrl}/dashboard/settings/`, data, { headers: this.headers });
  }

  // 2. Dashboard Vendedor Endpoints

  getAssignedChats(): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}/dashboard/leads/`, { headers: this.headers });
  }

  getChatMessages(sessionId: string): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}/dashboard/leads/${sessionId}/messages/`, { headers: this.headers });
  }

  sendMessage(sessionId: string, text: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/dashboard/leads/${sessionId}/messages/send/`, { text }, { headers: this.headers });
  }

  assignLead(sessionId: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/dashboard/leads/${sessionId}/assign/`, {}, { headers: this.headers });
  }

  updateLeadStatus(sessionId: string, status: string): Observable<any> {
    return this.http.patch(`${this.baseUrl}/dashboard/leads/${sessionId}/status/`, { status }, { headers: this.headers });
  }
}
