import { Component, inject, OnInit, signal, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { LeadRepositoryService } from '../../../infrastructure/repositories/lead.repository';
import { SessionService } from '../../../core/services/session.service';
import { KpiCardComponent } from '../../components/shared/kpi-card.component';
import { LeadsGridComponent } from '../../components/shared/leads-grid.component';
import { Lead, SalesPerson, DashboardMetrics } from '../../../core/models/lead.model';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, KpiCardComponent, LeadsGridComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent implements OnInit {
  leadRepo = inject(LeadRepositoryService);
  session = inject(SessionService);

  leads = signal<Lead[]>([]);
  salesPersons = signal<SalesPerson[]>([]);
  metrics = signal<DashboardMetrics>({
    leadsInBotFlow: 0,
    pendingAssignment: 0,
    leadsInCommercialManagement: 0,
    conversions: 0
  });

  isManager = signal(true);

  constructor() {
    effect(() => {
      this.isManager.set(this.session.currentRole() === 'manager');
    });
  }

  ngOnInit() {
    this.loadData();
  }

  loadData() {
    this.leadRepo.getAll().subscribe(leads => this.leads.set(leads));
    this.leadRepo.getSalesPersons().subscribe(sp => this.salesPersons.set(sp));
    this.leadRepo.getMetrics().subscribe(m => this.metrics.set(m));
  }

  onAssignLead(event: { leadId: string; salesPersonId: string }) {
    this.leadRepo.assign(event).subscribe(() => {
      this.loadData();
    });
  }
}