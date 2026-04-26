import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import { HttpClient } from '@angular/common/http';
import { SessionDto } from '../../../core/models/crm.models';
import { LeadRepositoryInterface } from '../interfaces/lead.repository.interface';

@Injectable({ providedIn: 'root' })
export class PendingLeadRepository implements LeadRepositoryInterface {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost:8000/api';

  getLeads(): Observable<SessionDto[]> {
    return this.http.get<{ pending_leads: SessionDto[] }>(`${this.baseUrl}/dashboard/leads/pending/`)
      .pipe(
        map(res => res.pending_leads)
      );
  }
}