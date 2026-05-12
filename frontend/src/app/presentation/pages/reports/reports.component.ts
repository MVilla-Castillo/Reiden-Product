import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { CrmApiService } from '../../../infrastructure/repositories/crm.api.service';
import { MetricsResponse, SalespersonDto } from '../../../core/models/crm.models';
import { KpiCardComponent } from '../../components/shared/kpi-card.component';
import { SkeletonComponent } from '../../components/shared/skeleton.component';
import { IconComponent } from '../../components/shared/icons.component';
import { GuideButtonComponent } from '../../components/shared/guide-button.component';

interface LeaderboardRow {
  salesperson_id: string;
  displayName: string;
  medal: string;
  leads_assigned: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_first_response_minutes: number;
  ranking_position: number;
}

@Component({
  selector: 'app-reports',
  standalone: true,
  imports: [CommonModule, FormsModule, KpiCardComponent, SkeletonComponent, IconComponent, GuideButtonComponent],
  templateUrl: './reports.component.html',
  styleUrl: './reports.component.scss'
})
export class ReportsComponent implements OnInit {
  private crmApi = inject(CrmApiService);

  metrics    = signal<MetricsResponse | null>(null);
  salespeople = signal<SalespersonDto[]>([]);
  loading    = signal(false);
  error      = signal(false);
  dateFilter = signal('month');
  showCustom = signal(false);
  dateFrom   = signal('');
  dateTo     = signal('');

  readonly dateOptions = [
    { label: 'Hoy',    value: 'today' },
    { label: 'Semana', value: 'week'  },
    { label: 'Mes',    value: 'month' },
    { label: 'Año',    value: 'year'  },
    { label: 'Todo',   value: 'all'   },
  ];

  ngOnInit() { this.loadData(); }

  setFilter(value: string) {
    if (value === 'custom') { this.showCustom.set(true); return; }
    this.showCustom.set(false);
    this.dateFilter.set(value);
    this.loadData();
  }

  applyCustom() {
    if (!this.dateFrom() || !this.dateTo()) return;
    this.loadData({ date_from: this.dateFrom(), date_to: this.dateTo() });
  }

  private loadData(filters?: Record<string, string>) {
    this.loading.set(true);
    this.error.set(false);
    const f = filters ?? { date_filter: this.dateFilter() };
    forkJoin({
      metrics:    this.crmApi.getMetrics(f),
      salespeople: this.crmApi.getSalespeople(),
    }).subscribe({
      next: ({ metrics, salespeople }) => {
        this.metrics.set(metrics);
        this.salespeople.set(salespeople);
        this.loading.set(false);
      },
      error: () => { this.loading.set(false); this.error.set(true); },
    });
  }

  get leaderboard(): LeaderboardRow[] {
    const perf = this.metrics()?.salesperson_performance ?? [];
    const spMap = new Map(this.salespeople().map(s => [s.id, s.email.split('@')[0]]));
    return [...perf]
      .sort((a, b) => a.ranking_position - b.ranking_position)
      .map(p => ({
        ...p,
        displayName: spMap.get(p.salesperson_id) ?? 'Vendedor',
        medal: p.ranking_position === 1 ? '🥇'
             : p.ranking_position === 2 ? '🥈'
             : p.ranking_position === 3 ? '🥉'
             : `#${p.ranking_position}`,
      }));
  }

  formatMinutes(minutes: number): string {
    const m = Math.floor(minutes);
    const s = Math.round((minutes - m) * 60);
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  winRateColor(rate: number): string {
    if (rate >= 60) return '#22c55e';
    if (rate >= 40) return '#f59e0b';
    return '#ef4444';
  }

  medalBorder(pos: number): string {
    if (pos === 1) return '#f59e0b';
    if (pos === 2) return '#94a3b8';
    if (pos === 3) return '#b45309';
    return '#e2e8f0';
  }
}
