import { Injectable, inject, signal } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map, tap, catchError, of } from 'rxjs';
import { Lead, SalesPerson, DashboardMetrics, AssignLeadRequest, Session, Message, FunnelMetrics, SalespersonPerformance } from '../../core/models/lead.model';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private baseUrl = 'http://localhost:8000';

  private _leads = signal<Lead[]>([]);
  private _salesPersons = signal<SalesPerson[]>([]);
  private _metrics = signal<DashboardMetrics>({
    leadsInBotFlow: 0,
    pendingAssignment: 0,
    leadsInCommercialManagement: 0,
    conversions: 0
  });

  readonly leads = this._leads.asReadonly();
  readonly salesPersons = this._salesPersons.asReadonly();
  readonly metrics = this._metrics.asReadonly();

  getLeads(filters?: Record<string, string>): Observable<Lead[]> {
    let params = new HttpParams();
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params = params.set(key, value);
      });
    }

    return this.http.get<{ leads: Lead[]; count: number }>(`${this.baseUrl}/api/dashboard/leads/`, { params })
      .pipe(
        map(response => response.leads),
        catchError(() => of([]))
      );
  }

  getPendingLeads(): Observable<Lead[]> {
    return this.http.get<{ pending_leads: Lead[] }>(`${this.baseUrl}/api/dashboard/leads/pending/`)
      .pipe(
        map(response => response.pending_leads),
        catchError(() => of([]))
      );
  }

  getSalesPersons(): Observable<SalesPerson[]> {
    return this.http.get<{ salespeople: SalesPerson[] }>(`${this.baseUrl}/api/dashboard/salespeople/`)
      .pipe(
        map(response => response.salespeople),
        catchError(() => of([]))
      );
  }

  getMetrics(dateFrom: string, dateTo: string): Observable<{
    funnel: FunnelMetrics;
    salesperson_performance: SalespersonPerformance[];
  }> {
    const params = new HttpParams()
      .set('date_from', dateFrom)
      .set('date_to', dateTo);

    return this.http.get<{
      funnel: FunnelMetrics;
      fsm_distribution: any;
      urgency_distribution: any;
      time_metrics: any;
      salesperson_performance: SalespersonPerformance[]
    }>(
      `${this.baseUrl}/api/dashboard/metrics/`,
      { params }
    ).pipe(
      map(response => ({
        funnel: response.funnel,
        salesperson_performance: response.salesperson_performance
      })),
      catchError(() => of({ 
        funnel: { 
          total_leads: 0, 
          completed_fsm: 0, 
          assigned_leads: 0, 
          won_sessions: 0, 
          lost_sessions: 0, 
          abandoned_sessions: 0,
          conversion_rate_fsm: 0,
          conversion_rate_assignment: 0,
          win_rate: 0
        },
        salesperson_performance: []
      }))
    );
  }

  assignLead(sessionId: string, request: AssignLeadRequest): Observable<Lead> {
    return this.http.post<Lead>(`${this.baseUrl}/api/dashboard/leads/${sessionId}/assign/`, request)
      .pipe(
        tap(() => this.refreshLeads()),
        catchError(() => of({} as Lead))
      );
  }

  reassignLead(sessionId: string, salespersonId: string | null): Observable<Lead> {
    return this.http.patch<Lead>(`${this.baseUrl}/api/dashboard/leads/${sessionId}/reassign/`, {
      salesperson_id: salespersonId
    }).pipe(
      tap(() => this.refreshLeads()),
      catchError(() => of({} as Lead))
    );
  }

  changeStatus(sessionId: string, status: 'GANADO' | 'PERDIDO'): Observable<Lead> {
    return this.http.patch<Lead>(`${this.baseUrl}/api/dashboard/leads/${sessionId}/status/`, {
      status
    }).pipe(
      tap(() => this.refreshLeads()),
      catchError(() => of({} as Lead))
    );
  }

  getMessages(sessionId: string): Observable<Message[]> {
    return this.http.get<Message[]>(`${this.baseUrl}/api/dashboard/leads/${sessionId}/messages/`)
      .pipe(catchError(() => of([])));
  }

  sendMessage(sessionId: string, content: string): Observable<Message> {
    return this.http.post<Message>(`${this.baseUrl}/api/dashboard/leads/${sessionId}/messages/send/`, {
      content
    }).pipe(catchError(() => of({} as Message)));
  }

  getSettings(): Observable<{ routing_mode: string }> {
    return this.http.get<{ routing_mode: string }>(`${this.baseUrl}/api/dashboard/settings/`)
      .pipe(catchError(() => of({ routing_mode: 'MANUAL' })));
  }

  updateSettings(routingMode: 'MANUAL' | 'AUTO'): Observable<{ routing_mode: string }> {
    return this.http.patch<{ routing_mode: string }>(`${this.baseUrl}/api/dashboard/settings/`, {
      routing_mode: routingMode
    }).pipe(catchError(() => of({ routing_mode: 'MANUAL' })));
  }

  refreshLeads() {
    this.getLeads().subscribe();
  }

  refreshMetrics() {
    const today = new Date().toISOString().split('T')[0];
    this.getMetrics(today, today).subscribe();
  }

  refreshSalesPersons() {
    this.getSalesPersons().subscribe();
  }
}