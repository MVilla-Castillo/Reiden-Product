import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { Lead, SalesPerson, DashboardMetrics, AssignLeadRequest } from '../../core/models/lead.model';

@Injectable({ providedIn: 'root' })
export class LeadRepositoryService {
  private http = inject(HttpClient);
  private apiUrl = '/api/dashboard';

  getAll(): Observable<Lead[]> {
    return this.http.get<{ leads: any[] }>(\`\${this.apiUrl}/leads/\`).pipe(
      map(res => res.leads.map(l => ({
        id: l.session_id,
        name: l.lead_phone_hash, // Use hash as name since we don't have it yet
        company: 'N/A',
        source: 'whatsapp',
        status: l.status as any,
        assignedTo: l.salesperson_id,
        createdAt: new Date(l.created_at),
        waitingTime: 0
      })))
    );
  }

  getSalesPersons(): Observable<SalesPerson[]> {
    return this.http.get<{ salespeople: SalesPerson[] }>(\`\${this.apiUrl}/salespeople/\`).pipe(
      map(res => res.salespeople)
    );
  }

  assign(request: AssignLeadRequest): Observable<Lead> {
    return this.http.post<any>(\`\${this.apiUrl}/leads/\${request.leadId}/assign/\`, {
      salesperson_id: request.salesPersonId
    }).pipe(
      map(res => ({
        id: res.session_id,
        name: '',
        company: '',
        source: 'whatsapp',
        status: res.status as any,
        assignedTo: res.salesperson_id,
        createdAt: new Date(),
        waitingTime: 0
      }))
    );
  }

  takeLead(leadId: string): Observable<Lead> {
    return this.http.post<any>(\`\${this.apiUrl}/leads/\${leadId}/assign/\`, {
      salesperson_id: 'AUTO' // Mock: using AUTO or a fixed manager ID for now
    }).pipe(
      map(res => ({
        id: res.session_id,
        name: '',
        company: '',
        source: 'whatsapp',
        status: res.status as any,
        assignedTo: res.salesperson_id,
        createdAt: new Date(),
        waitingTime: 0
      }))
    );
  }

  getMetrics(): Observable<DashboardMetrics> {
    return this.http.get<DashboardMetrics>(\`\${this.apiUrl}/metrics/\`);
  }
}