import { Observable } from 'rxjs';
import { SessionDto } from '../../../core/models/crm.models';

export interface LeadRepositoryInterface {
  getLeads(): Observable<SessionDto[]>;
}