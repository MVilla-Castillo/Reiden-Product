import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { SidebarComponent } from '../../../core/layout/sidebar/sidebar.component';
import { TopbarComponent } from '../../../core/layout/topbar/topbar.component';
import { CrmApiService } from '../../../core/services/crm-api.service';

interface Lead {
  name: string;
  vehicle: string;
  source: string;
  received: string;
  status: string;
  urgency: 'hito' | 'medium' | 'normal' | string;
}

interface AgentRank {
  name: string;
  rank: number;
  score: number;
  avatar: string;
}

@Component({
  selector: 'app-manager-dashboard',
  standalone: true,
  imports: [CommonModule, SidebarComponent, TopbarComponent],
  templateUrl: './manager-dashboard.component.html',
  styleUrl: './manager-dashboard.component.css'
})
export class ManagerDashboardComponent implements OnInit {
  routingMode: 'Auto' | 'Manual' = 'Auto';

  metrics: any = {
    responseTime: { value: '-- min', trend: '--%' },
    closeRate: { value: '--%', trend: '--%' },
    activeLeads: { value: '--', trend: '--%' },
    pendingAssignments: { value: '--', trend: '--%' },
  };

  pendingLeads: Lead[] = [];
  salesRanking: AgentRank[] = [];

  constructor(private crmService: CrmApiService, private router: Router) {}

  ngOnInit() {
    this.fetchMetrics();
    this.fetchPendingLeads();
    this.fetchSalespeople();
    this.fetchSettings();
  }

  takeLead(leadId: string) {
    if(!leadId) return;
    this.crmService.assignLead(leadId).subscribe({
      next: (res) => {
        // Redirigimos al panel de vendedor
        this.router.navigate(['/vendedor']);
      },
      error: (err) => {
        console.error('Error assigning lead to manager', err);
        // Fallback for UI if backend isn't ready
        this.router.navigate(['/vendedor']);
      }
    });
  }

  fetchMetrics() {
    this.crmService.getMetrics().subscribe({
      next: (data) => {
        if (data) {
          // Map backend structure to frontend structure
          this.metrics = data;
        }
      },
      error: (err) => console.error('Error fetching metrics', err)
    });
  }

  fetchPendingLeads() {
    this.crmService.getPendingLeads().subscribe({
      next: (data) => {
        if (data) this.pendingLeads = data;
      },
      error: (err) => console.error('Error fetching pending leads', err)
    });
  }

  fetchSalespeople() {
    this.crmService.getSalespeople().subscribe({
      next: (data) => {
        if (data) this.salesRanking = data;
      },
      error: (err) => console.error('Error fetching salespeople rankings', err)
    });
  }

  fetchSettings() {
    this.crmService.getSettings().subscribe({
      next: (data) => {
        if (data && data.routingMode) {
          this.routingMode = data.routingMode;
        }
      },
      error: (err) => console.error('Error fetching settings', err)
    });
  }

  toggleRouting(mode: 'Auto' | 'Manual') {
    this.crmService.updateSettings({ routingMode: mode }).subscribe({
      next: () => {
         this.routingMode = mode;
      },
      error: (err) => console.error('Error updating routing mode', err)
    });
  }
}
