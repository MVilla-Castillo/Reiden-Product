import { Injectable } from '@angular/core';
import { Observable, of, delay, BehaviorSubject } from 'rxjs';
import { Lead, SalesPerson, DashboardMetrics, AssignLeadRequest } from '../../core/models/lead.model';

@Injectable({ providedIn: 'root' })
export class LeadRepositoryService {
  private leadsSubject = new BehaviorSubject<Lead[]>(this.generateMockLeads());
  leads$ = this.leadsSubject.asObservable();

  private salesPersons: SalesPerson[] = [
    { id: 'sp-001', name: 'Juan Pérez', email: 'juan@company.com', activeLeadsCount: 5 },
    { id: 'sp-002', name: 'María González', email: 'maria@company.com', activeLeadsCount: 3 },
    { id: 'sp-003', name: 'Carlos López', email: 'carlos@company.com', activeLeadsCount: 7 },
    { id: 'sp-004', name: 'Ana Martínez', email: 'ana@company.com', activeLeadsCount: 2 },
  ];

  getAll(): Observable<Lead[]> {
    return this.leads$.pipe(delay(300));
  }

  getSalesPersons(): Observable<SalesPerson[]> {
    return of(this.salesPersons).pipe(delay(200));
  }

  assign(request: AssignLeadRequest): Observable<Lead> {
    const leads = this.leadsSubject.getValue();
    const updatedLeads = leads.map(lead => 
      lead.id === request.leadId 
        ? { ...lead, assignedTo: request.salesPersonId, status: 'in_commercial_management' as const }
        : lead
    );
    this.leadsSubject.next(updatedLeads);
    
    const assignedLead = updatedLeads.find(l => l.id === request.leadId)!;
    return of(assignedLead).pipe(delay(200));
  }

  getMetrics(): Observable<DashboardMetrics> {
    const leads = this.leadsSubject.getValue();
    return of({
      leadsInBotFlow: leads.filter(l => l.status === 'bot_flow').length,
      pendingAssignment: leads.filter(l => l.status === 'pending_assignment').length,
      leadsInCommercialManagement: leads.filter(l => l.status === 'in_commercial_management').length,
      conversions: leads.filter(l => l.status === 'won').length,
    }).pipe(delay(200));
  }

  private generateMockLeads(): Lead[] {
    const sources: Lead['source'][] = ['whatsapp', 'web', 'referral', 'campaign'];
    const statuses: Lead['status'][] = ['bot_flow', 'pending_assignment', 'in_commercial_management', 'won', 'lost'];
    
    return [
      { id: 'lead-001', name: 'Roberto Silva', company: 'AutoMotors Chile', source: 'whatsapp', status: 'bot_flow', assignedTo: null, createdAt: new Date(), waitingTime: 5 },
      { id: 'lead-002', name: 'Claudia Ramírez', company: 'Concesionaria Norte', source: 'web', status: 'pending_assignment', assignedTo: null, createdAt: new Date(), waitingTime: 12 },
      { id: 'lead-003', name: 'Fernando Torres', company: 'Vehículos Sur', source: 'campaign', status: 'in_commercial_management', assignedTo: 'sp-001', createdAt: new Date(), waitingTime: 0 },
      { id: 'lead-004', name: 'Sandra Mendoza', company: 'Automotora Central', source: 'referral', status: 'in_commercial_management', assignedTo: 'sp-002', createdAt: new Date(), waitingTime: 0 },
      { id: 'lead-005', name: 'Javier Herrera', company: 'Garaje Moderno', source: 'whatsapp', status: 'won', assignedTo: 'sp-003', createdAt: new Date(), waitingTime: 0 },
      { id: 'lead-006', name: 'Patricia Flores', company: 'Autos del Valle', source: 'web', status: 'pending_assignment', assignedTo: null, createdAt: new Date(), waitingTime: 8 },
      { id: 'lead-007', name: 'Miguel Ángel Cruz', company: 'Motor Plus', source: 'campaign', status: 'bot_flow', assignedTo: null, createdAt: new Date(), waitingTime: 3 },
      { id: 'lead-008', name: 'Laura Benítez', company: 'Concesionario Elite', source: 'whatsapp', status: 'in_commercial_management', assignedTo: 'sp-001', createdAt: new Date(), waitingTime: 0 },
      { id: 'lead-009', name: 'David Sánchez', company: 'AutoZone Chile', source: 'referral', status: 'lost', assignedTo: 'sp-004', createdAt: new Date(), waitingTime: 0 },
      { id: 'lead-010', name: 'Carmen Ibarra', company: 'Vehículos Premium', source: 'web', status: 'won', assignedTo: 'sp-003', createdAt: new Date(), waitingTime: 0 },
    ];
  }
}