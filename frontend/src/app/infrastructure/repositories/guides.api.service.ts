import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { GuideResponse, GuideTab } from '../../core/models/guides.models';

@Injectable({ providedIn: 'root' })
export class GuidesApiService {
  private readonly baseUrl = 'http://localhost:8000/api';
  private readonly http = inject(HttpClient);

  getGuide(tab: GuideTab): Observable<GuideResponse> {
    return this.http.get<GuideResponse>(`${this.baseUrl}/dashboard/guides/${tab}/`);
  }
}
