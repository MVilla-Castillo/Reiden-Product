import { Component, inject, OnInit, OnDestroy, signal, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription } from 'rxjs';
import { CrmApiService } from '../../../infrastructure/repositories/crm.api.service';
import { SseService } from '../../../infrastructure/services/sse.service';
import { SessionService } from '../../../core/services/session.service';
import { KpiCardComponent } from '../../components/shared/kpi-card.component';
import { LeadsGridComponent } from '../../components/shared/leads-grid.component';
import { IconComponent } from '../../components/shared/icons.component';
import { SkeletonComponent } from '../../components/shared/skeleton.component';
import { SessionDto, SalespersonDto, MetricsResponse, TenantSettings } from '../../../core/models/crm.models';

const METRICS_BACKUP_MS = 3_600_000;

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, KpiCardComponent, LeadsGridComponent, IconComponent, SkeletonComponent],
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
  isRefreshing = signal(false);
  metricsError = signal(false);
  sseReconnecting = signal(false);

  private sseSub?: Subscription;
  private metricsBackupInterval?: ReturnType<typeof setInterval>;

  constructor() {
    effect(() => {
      this.isManager.set(this.session.currentRole() === 'manager');
    }, { allowSignalWrites: true });
  }

  ngOnInit() {
    this._loadMetrics();

    // Backup automático cada hora: sincroniza con BD por si se perdieron eventos SSE
    this.metricsBackupInterval = setInterval(() => this._loadMetrics(), METRICS_BACKUP_MS);

    this.sseSub = this.sseService.dashboardStream().subscribe(event => {
      if (event.type === 'sse_reconnecting') {
        this.sseReconnecting.set(true);
        return;
      }
      if (event.type === 'sse_connected') {
        this.sseReconnecting.set(false);
        return;
      }

      if (event.type === 'snapshot') {
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
        // Aplica deltas localmente a las KPI sin consultar la BD
        this._applyDeltas(event.data);
        // Re-fetch de la lista de leads para mantener orden y datos frescos
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
    if (this.metricsBackupInterval) {
      clearInterval(this.metricsBackupInterval);
    }
  }

  private _loadMetrics(): void {
    this.crmApi.getMetrics().subscribe({
      next: m => {
        this.metrics.set(m);
        this.metricsError.set(false);
      },
      error: () => this.metricsError.set(true),
    });
  }

  /** Botón manual de refresh — solo visible para managers */
  refreshMetrics(): void {
    this.isRefreshing.set(true);
    this.metricsError.set(false);
    this.crmApi.getMetrics().subscribe({
      next: m => {
        this.metrics.set(m);
        this.isRefreshing.set(false);
      },
      error: () => {
        this.isRefreshing.set(false);
        this.metricsError.set(true);
      },
    });
  }

  /** Convierte minutos decimales a formato "M:SS"  (ej. 2.5 → "2:30") */
  formatMinutes(totalMinutes: number): string {
    const m = Math.floor(totalMinutes);
    const s = Math.round((totalMinutes - m) * 60);
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  toggleRoutingMode() {
    const ts = this.tenantSettings();
    if (!ts) return;
    const newMode = ts.routing_mode === 'AUTO' ? 'MANUAL' : 'AUTO';
    this.crmApi.updateTenantSettings(newMode).subscribe(updated => this.tenantSettings.set(updated));
  }

  handleAssignment(event: {leadId: string, agentId: string}) {
    this.crmApi.assignLead(event.leadId, event.agentId).subscribe({
      next: () => {
        this.leads.update(current => current.filter(l => l.session_id !== event.leadId));
      },
      error: (err) => {
        console.error('Error assigning lead:', err);
      }
    });
  }

  /**
   * Aplica deltas del evento SSE directamente a la señal metrics.
   *
   * Reglas de mapeo:
   *   pending_delta  → total_leads  (solo cuando NO hay assigned_delta; el nuevo lead
   *                                  entra al sistema. En asignación, el count baja
   *                                  automáticamente al subir assigned_leads.)
   *   assigned_delta → assigned_leads
   *   won_delta      → won_sessions
   *   lost_delta     → lost_sessions
   */
  private _applyDeltas(data: any): void {
    const m = this.metrics();
    if (!m) return;

    const pendingDelta: number  = data.pending_delta  ?? 0;
    const assignedDelta: number = data.assigned_delta ?? 0;
    const wonDelta: number      = data.won_delta      ?? 0;
    const lostDelta: number     = data.lost_delta     ?? 0;

    // pending_delta solo mueve total_leads cuando es un nuevo lead (no hay assigned_delta).
    // Si hay assigned_delta, el conteo de "pendientes" baja porque assigned_leads sube.
    const totalDelta = assignedDelta === 0 ? pendingDelta : 0;

    if (totalDelta === 0 && assignedDelta === 0 && wonDelta === 0 && lostDelta === 0) return;

    this.metrics.update(current => ({
      ...current!,
      funnel: {
        ...current!.funnel,
        total_leads:    current!.funnel.total_leads    + totalDelta,
        assigned_leads: current!.funnel.assigned_leads + assignedDelta,
        won_sessions:   current!.funnel.won_sessions   + wonDelta,
        lost_sessions:  current!.funnel.lost_sessions  + lostDelta,
      },
    }));
  }


}
