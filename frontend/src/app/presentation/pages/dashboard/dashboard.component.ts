import { Component, inject, OnInit, signal, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { interval, switchMap, startWith } from 'rxjs';
import { CrmApiService } from '../../../infrastructure/repositories/crm.api.service';
import { SessionService } from '../../../core/services/session.service';
import { KpiCardComponent } from '../../components/shared/kpi-card.component';
import { LeadsGridComponent } from '../../components/shared/leads-grid.component';
import { Lead, Salesperson, Metrics, TenantSettings } from '../../../core/models/crm.models';

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

  leads = signal<Lead[]>([]);
  salesPersons = signal<Salesperson[]>([]);
  metrics = signal<Metrics>({
    responseTime: { value: '0', trend: '0%' },
    closeRate: { value: '0%', trend: '0%' },
    activeLeads: { value: 0, trend: '0%' },
    pendingAssignments: { value: 0, trend: '0%' }
  });
  tenantSettings = signal<TenantSettings>({ routingMode: 'Manual' });

  isManager = signal(true);

  constructor() {
    effect(() => {
      this.isManager.set(this.session.currentRole() === 'manager');
    });
  }

  ngOnInit() {
    this.setupPolling();
  }

  setupPolling() {
    interval(30000).pipe(
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
    const newMode = this.tenantSettings().routingMode === 'Auto' ? 'Manual' : 'Auto';
    this.crmApi.updateTenantSettings(newMode).subscribe(ts => this.tenantSettings.set(ts));
  }
}
