import { Component, inject, OnInit, signal, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { interval, switchMap, startWith } from 'rxjs';
import { CrmApiService } from '../../../infrastructure/repositories/crm.api.service';
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
export class DashboardComponent implements OnInit {
  crmApi = inject(CrmApiService);
  session = inject(SessionService);

  leads = signal<SessionDto[]>([]);
  salesPersons = signal<SalespersonDto[]>([]);
  metrics = signal<MetricsResponse | null>(null);
  tenantSettings = signal<TenantSettings | null>(null);

  isManager = signal(true);

  constructor() {
    effect(() => {
      this.isManager.set(this.session.currentRole() === 'manager');
    }, { allowSignalWrites: true });
  }

  ngOnInit() {
    this.setupPolling();
  }

  setupPolling() {
    interval(5000).pipe(
      startWith(0),
      switchMap(() => {
        this.loadData();
        return [null];
      })
    ).subscribe();
  }

loadData() {
    this.crmApi.getMetrics().subscribe(m => this.metrics.set(m));
    this.crmApi.getPendingLeads().subscribe(leads => this.leads.set(leads));
    this.crmApi.getSalespeople().subscribe(sp => this.salesPersons.set(sp));
    this.crmApi.getTenantSettings().subscribe(ts => this.tenantSettings.set(ts));
  }

  toggleRoutingMode() {
    const ts = this.tenantSettings();
    if (!ts) return;
    const newMode = ts.routing_mode === 'AUTO' ? 'MANUAL' : 'AUTO';
    this.crmApi.updateTenantSettings(newMode).subscribe(updated => this.tenantSettings.set(updated));
  }
}
