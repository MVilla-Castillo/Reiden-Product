import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { interval, Subscription } from 'rxjs';
import { SidebarComponent } from '../../../core/layout/sidebar/sidebar.component';
import { TopbarComponent } from '../../../core/layout/topbar/topbar.component';
import { CrmApiService } from '../../../core/services/crm-api.service';

interface Lead {
  sessionId: string;
  name: string;
  vehicle: string;
  source: string;
  received: string;
  status: string;
  urgency: string;
}

interface AgentRank {
  name: string;
  rank: number;
  score: number;
  avatar: string;
}

interface Metrics {
  responseTime: { value: string; trend: string };
  closeRate: { value: string; trend: string };
  activeLeads: { value: string; trend: string };
  pendingAssignments: { value: string; trend: string };
}

@Component({
  selector: 'app-manager-dashboard',
  standalone: true,
  imports: [CommonModule, SidebarComponent, TopbarComponent],
  templateUrl: './manager-dashboard.component.html',
  styleUrl: './manager-dashboard.component.css'
})
export class ManagerDashboardComponent implements OnInit, OnDestroy {
  routingMode: 'Auto' | 'Manual' = 'Auto';

  metrics: Metrics = {
    responseTime: { value: '-- min', trend: '--%' },
    closeRate: { value: '--%', trend: '--%' },
    activeLeads: { value: '--', trend: '--%' },
    pendingAssignments: { value: '--', trend: '--%' },
  };

  pendingLeads: Lead[] = [];
  salesRanking: AgentRank[] = [];

  private pollingSubscription?: Subscription;

  constructor(private crmService: CrmApiService, private router: Router) {}

  ngOnInit() {
    this.fetchAll();
    this.startPolling();
  }

  ngOnDestroy() {
    this.stopPolling();
  }

  startPolling() {
    this.pollingSubscription = interval(10000).subscribe(() => {
      this.fetchPendingLeads();
    });
  }

  stopPolling() {
    this.pollingSubscription?.unsubscribe();
  }

  fetchAll() {
    this.fetchMetrics();
    this.fetchPendingLeads();
    this.fetchSalespeople();
    this.fetchSettings();
  }

  takeLead(sessionId: string) {
    if (!sessionId) return;
    // Use AUTO routing (round-robin) to assign to available salesperson
    this.crmService.assignLead(sessionId, 'AUTO').subscribe({
      next: () => {
        this.fetchPendingLeads();
      },
      error: (err) => {
        console.error('Error assigning lead', err);
      }
    });
  }

  fetchMetrics() {
    this.crmService.getMetrics().subscribe({
      next: (data) => {
        if (data) {
          this.metrics = {
            responseTime: { value: data.response_time?.value || '-- min', trend: data.response_time?.trend || '--%' },
            closeRate: { value: data.close_rate?.value || '--%', trend: data.close_rate?.trend || '--%' },
            activeLeads: { value: data.active_leads?.value || '--', trend: data.active_leads?.trend || '--%' },
            pendingAssignments: { value: data.pending_assignments?.value || '--', trend: data.pending_assignments?.trend || '--%' },
          };
        }
      },
      error: (err) => console.error('Error fetching metrics', err)
    });
  }

  fetchPendingLeads() {
    this.crmService.getPendingLeads().subscribe({
      next: (response) => {
        const leads = response?.pending_leads || [];
        this.pendingLeads = leads.map((lead: any) => this.mapLead(lead));
      },
      error: (err) => console.error('Error fetching pending leads', err)
    });
  }

  private mapLead(apiLead: any): Lead {
    const vehicleMap: Record<string, string> = {
      'CITY_CAR': 'Auto City',
      'SUV': 'SUV',
      'SEDAN': 'Sedán',
      'PICKUP': 'Pickup',
    };
    return {
      sessionId: apiLead.session_id,
      name: apiLead.lead_phone_hash?.substring(0, 8) || 'Lead',
      vehicle: vehicleMap[apiLead.vehicle_type] || apiLead.vehicle_type || '--',
      source: 'WhatsApp',
      received: this.formatDate(apiLead.created_at),
      status: apiLead.status,
      urgency: this.mapUrgency(apiLead.urgency_score),
    };
  }

  private mapUrgency(score: number): string {
    if (score >= 150) return 'hito';
    if (score >= 80) return 'medium';
    return 'normal';
  }

  private formatDate(dateStr: string): string {
    if (!dateStr) return '--';
    const date = new Date(dateStr);
    return date.toLocaleDateString('es-CL', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  }

  fetchSalespeople() {
    this.crmService.getSalespeople().subscribe({
      next: (data) => {
        if (data?.salespeople) {
          this.salesRanking = data.salespeople.map((agent: any, index: number) => ({
            name: agent.name || agent.email,
            rank: index + 1,
            score: agent.score || agent.leads_closed || 0,
            avatar: 'assets/logo-pagina-r.svg'
          }));
        }
      },
      error: (err) => console.error('Error fetching salespeople', err)
    });
  }

  fetchSettings() {
    this.crmService.getSettings().subscribe({
      next: (data) => {
        if (data?.routing_mode) {
          this.routingMode = data.routing_mode;
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
