import { Component, inject, OnInit, OnDestroy, signal, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription } from 'rxjs';
import { CrmApiService } from '../../../infrastructure/repositories/crm.api.service';
import { SseService } from '../../../infrastructure/services/sse.service';
import { SessionService } from '../../../core/services/session.service';
import { KpiCardComponent } from '../../components/shared/kpi-card.component';
import { LeadsGridComponent } from '../../components/shared/leads-grid.component';
import { SessionDto, SalespersonDto, MetricsResponse, TenantSettings } from '../../../core/models/crm.models';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, KpiCardComponent, LeadsGridComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent implements OnInit, OnDestroy {
  crmApi = inject(CrmApiService);
  session = inject(SessionService);
  private sseService = inject(SseService);

  leads = signal<SessionDto[]>([]);
  salesPersons = signal<SalespersonDto[]>([]);
  metrics = signal<MetricsResponse | null>(null);
  tenantSettings = signal<TenantSettings | null>(null);

  isManager = signal(true);

  private sseSub?: Subscription;

  constructor() {
    effect(() => {
      this.isManager.set(this.session.currentRole() === 'manager');
    }, { allowSignalWrites: true });
  }

  ngOnInit() {
    // Métricas no tienen evento SSE: carga única al iniciar
    this.crmApi.getMetrics().subscribe(m => this.metrics.set(m));

    this.sseSub = this.sseService.dashboardStream().subscribe(event => {
      if (event.type === 'snapshot') {
        // Estado completo al conectar: pending_leads + salespeople + settings
        this.leads.set(event.data.pending_leads ?? []);
        this.salesPersons.set(event.data.salespeople ?? []);
        if (event.data.settings?.routing_mode) {
          this.tenantSettings.update(ts => ({
            ...(ts ?? { tenant_id: '', nombre_legal: '', is_verified: false }),
            routing_mode: event.data.settings.routing_mode,
          }));
        }
      }

      if (event.type === 'pending_leads') {
        // Re-fetch completo para mantener consistencia (orden por urgency_score, etc.)
        this.crmApi.getPendingLeads().subscribe(leads => this.leads.set(leads));
      }

      if (event.type === 'settings') {
        this.tenantSettings.update(ts => ({
          ...(ts ?? { tenant_id: '', nombre_legal: '', is_verified: false }),
          routing_mode: event.data.routing_mode,
        }));
      }
    });
  }

  ngOnDestroy() {
    this.sseSub?.unsubscribe();
  }

  toggleRoutingMode() {
    const ts = this.tenantSettings();
    if (!ts) return;
    const newMode = ts.routing_mode === 'AUTO' ? 'MANUAL' : 'AUTO';
    this.crmApi.updateTenantSettings(newMode).subscribe(updated => this.tenantSettings.set(updated));
  }
}
