import { Observable } from 'rxjs';
import { Lead, SalesPerson, DashboardMetrics, AssignLeadRequest } from '../models/lead.model';

export interface ILeadRepository {
  getAll(): Observable<Lead[]>;
  assign(request: AssignLeadRequest): Observable<Lead>;
  getSalesPersons(): Observable<SalesPerson[]>;
}

export interface IMetricsService {
  getDashboardMetrics(): Observable<DashboardMetrics>;
}

export interface ISessionService {
  getCurrentRole(): 'manager' | 'sales';
  setRole(role: 'manager' | 'sales'): void;
  getToken(): string | null;
  setToken(token: string): void;
}