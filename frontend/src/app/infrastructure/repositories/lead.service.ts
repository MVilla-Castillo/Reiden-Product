import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { SessionDto } from '../../core/models/crm.models';
import { SessionService, UserRole } from '../../core/services/session.service';
import { LeadRepositoryInterface } from './interfaces/lead.repository.interface';
import { PendingLeadRepository } from './strategies/pending-lead.repository';
import { AssignedLeadRepository } from './strategies/assigned-lead.repository';

@Injectable({ providedIn: 'root' })
export class LeadService {
  private readonly session = inject(SessionService);
  private readonly pendingRepo = inject(PendingLeadRepository);
  private readonly assignedRepo = inject(AssignedLeadRepository);

  getLeads(role?: UserRole): Observable<SessionDto[]> {
    const userRole = role ?? this.session.currentRole();
    const repository = this.resolveRepository(userRole);
    return repository.getLeads();
  }

  private resolveRepository(role: UserRole): LeadRepositoryInterface {
    if (role === 'manager') {
      return this.pendingRepo;
    }
    return this.assignedRepo;
  }
}