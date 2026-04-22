import { Component, inject, OnInit, OnDestroy, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CrmApiService } from '../../../infrastructure/repositories/crm.api.service';
import { SseService } from '../../../infrastructure/services/sse.service';
import { LeadsGridComponent, BatchActionEvent } from '../../components/shared/leads-grid.component';
import { SessionDto, SalespersonDto } from '../../../core/models/crm.models';
import { Subscription } from 'rxjs';

@Component({
// ... (Keeping decorator matching)
  selector: 'app-leads',
  standalone: true,
  imports: [CommonModule, LeadsGridComponent],
  template: `
    <div class="leads-page">
      <header class="page-header">
        <div class="header-titles">
          <h1>Gestor de Oportunidades y Leads</h1>
          <p>Supervisa todos los prospects del sistema y asígnalos manualmente a tu equipo.</p>
        </div>
        
        <div class="routing-control">
          <label>Modo de Asignación Global:</label>
          <div class="toggle-switch">
             <button 
                [class.active]="routingMode() === 'MANUAL'"
                (click)="toggleRoutingMode()">
                Enrutamiento Manual
             </button>
             <button 
                [class.active]="routingMode() === 'AUTO'"
                (click)="toggleRoutingMode()">
                Automático (Round Robin)
             </button>
          </div>
        </div>
      </header>
      
      <div class="grid-wrapper">
        @if (routingMode() === 'AUTO') {
          <div class="auto-assign-banner">
            <span class="banner-icon">🤖</span>
            <span class="banner-text">Modo Automático activo - Los leads se asignarán automáticamente al vendedor con menor carga</span>
            <button class="btn-auto-assign" (click)="assignAllPendingAuto()">
              Asignar Pendientes Ahora
            </button>
          </div>
        }
        <app-leads-grid
          [leads]="leads()"
          [salesPersons]="salesPersons()"
          [canAssign]="routingMode() === 'MANUAL'"
          (assignLead)="handleAssignment($event)"
          (batchAction)="handleBatchAction($event)">
        </app-leads-grid>
      </div>

      <!-- Toast Notification -->
      @if (toastMessage()) {
        <div class="toast-notification" [class.success]="toastType() === 'success'" [class.error]="toastType() === 'error'" role="alert">
          <span class="toast-icon">{{ toastType() === 'error' ? '⚠️' : '✅' }}</span>
          <span class="toast-text">{{ toastMessage() }}</span>
          @if (toastType() === 'error') {
            <button class="toast-dismiss" (click)="dismissToast()" aria-label="Cerrar notificación">✕</button>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .leads-page {
      padding: 2rem;
      max-width: 1400px;
      margin: 0 auto;
      position: relative;
    }
    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
      background: white;
      padding: 1.5rem;
      border-radius: 12px;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);

      h1 { font-size: 1.5rem; color: #111827; margin: 0 0 0.5rem; }
      p { color: #6b7280; margin: 0; font-size: 0.95rem; }
    }
    
    .routing-control {
      text-align: right;
      label { display: block; font-size: 0.85rem; color: #6b7280; margin-bottom: 0.5rem; font-weight: 500;}
      .toggle-switch { display: flex; gap: 4px; background: #f3f4f6; padding: 4px; border-radius: 8px; border: 1px solid #e5e7eb;}
      button { border: none; background: transparent; padding: 8px 16px; border-radius: 6px; font-weight: 600; color: #6b7280; cursor: pointer; transition: all 0.2s; font-size: 0.9rem;}
      button.active { background: white; color: #111827; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    }

    .grid-wrapper {
      background: white;
      border-radius: 12px;
      padding: 1.5rem;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }

    /* Toast */
    .toast-notification {
      position: absolute; top: 1rem; right: 1rem; max-width: 420px; padding: 0.875rem 1rem; border-radius: 8px; display: flex; align-items: flex-start; gap: 0.625rem; font-weight: 500; font-size: 0.875rem; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); animation: slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1); z-index: 100;
    }
    .toast-notification.success { background: #ecfdf5; color: #065f46; border-left: 4px solid #10b981; }
    .toast-notification.error   { background: #fef2f2; color: #991b1b; border-left: 4px solid #ef4444; }
    .toast-text { flex: 1; }
    .toast-dismiss {
      background: none; border: none; cursor: pointer; color: inherit; opacity: 0.6; font-size: 0.875rem; padding: 0; line-height: 1; flex-shrink: 0; margin-top: 1px;
      &:hover { opacity: 1; }
    }
    @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }

    .auto-assign-banner {
      display: flex; align-items: center; gap: 12px; padding: 16px 20px; background: linear-gradient(135deg, #fef3c7, #fde68a); border-radius: 12px; margin-bottom: 20px; border: 1px solid #f59e0b;
    }
    .banner-icon { font-size: 1.5rem; }
    .banner-text { flex: 1; color: #92400e; font-weight: 500; font-size: 0.95rem; }
    .btn-auto-assign {
      padding: 10px 20px; background: #f59e0b; color: white; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.2s;
    }
    .btn-auto-assign:hover { background: #d97706; transform: translateY(-1px); }
  `]
})
export class LeadsComponent implements OnInit, OnDestroy {
  crmApi = inject(CrmApiService);
  private sseService = inject(SseService);

  leads = signal<SessionDto[]>([]);
  salesPersons = signal<SalespersonDto[]>([]);
  routingMode = signal<'AUTO' | 'MANUAL'>('MANUAL');
  toastMessage = signal<string | null>(null);
  toastType = signal<'success' | 'error'>('success');
  private sseSub?: Subscription;
  private toastTimer?: ReturnType<typeof setTimeout>;

  ngOnInit() {
    this.sseSub = this.sseService.dashboardStream().subscribe(event => {
      if (event.type === 'snapshot') {
        this.leads.set(event.data.pending_leads ?? []);
        this.salesPersons.set(event.data.salespeople ?? []);
        if (event.data.settings?.routing_mode) {
          this.routingMode.set(event.data.settings.routing_mode);
        }
      }

      if (event.type === 'pending_leads') {
        // Re-fetch para respetar ordenamiento por urgency_score del backend
        this.crmApi.getPendingLeads().subscribe(leads => this.leads.set(leads));
      }

      if (event.type === 'settings') {
        this.routingMode.set(event.data.routing_mode);
      }
    });
  }

  ngOnDestroy() {
    this.sseSub?.unsubscribe();
    clearTimeout(this.toastTimer);
  }

  dismissToast() {
    clearTimeout(this.toastTimer);
    this.toastMessage.set(null);
  }

  private _showToast(msg: string, type: 'success' | 'error' = 'success') {
    clearTimeout(this.toastTimer);
    this.toastMessage.set(msg);
    this.toastType.set(type);
    if (type === 'success') {
      this.toastTimer = setTimeout(() => this.toastMessage.set(null), 3000);
    }
    // errors require manual dismiss
  }

  toggleRoutingMode() {
    const newMode = this.routingMode() === 'AUTO' ? 'MANUAL' : 'AUTO';
    this.crmApi.updateTenantSettings(newMode).subscribe((res: any) => {
      this.routingMode.set(newMode);
      this._showToast('El motor fue cambiado a Enrutamiento ' + newMode);
    });
  }

  assignAllPendingAuto() {
    const pendingLeads = this.leads();
    if (pendingLeads.length === 0) {
      this._showToast('No hay leads pendientes por asignar');
      return;
    }

    let completed = 0;
    let errors = 0;

    pendingLeads.forEach(lead => {
      this.crmApi.assignLead(lead.session_id, 'AUTO').subscribe({
        next: () => {
          completed++;
          this.leads.update(current => current.filter(l => l.session_id !== lead.session_id));
          if (completed + errors === pendingLeads.length) {
            this._showToast(`Se asignaron ${completed} lead(s) automáticamente`);
          }
        },
        error: () => {
          errors++;
          if (completed + errors === pendingLeads.length) {
            this._showToast(`Asignados ${completed}, errores: ${errors}`, 'error');
          }
        }
      });
    });
  }

  handleBatchAction(event: BatchActionEvent) {
    const { action, ids } = event;
    if (action === 'assign') {
      this._handleBatchAssign(ids, (event as { action: 'assign'; ids: string[]; agentId: string }).agentId);
    } else {
      this._handleBatchStatus(ids, action);
    }
  }

  private _handleBatchAssign(ids: string[], agentId: string): void {
    if (!agentId) return;
    let completed = 0;
    let errors = 0;
    const failed: string[] = [];

    ids.forEach(id => {
      this.crmApi.assignLead(id, agentId).subscribe({
        next: () => {
          completed++;
          this.leads.update(current => current.filter(l => l.session_id !== id));
          if (completed + errors === ids.length) this._showBatchResult(completed, failed);
        },
        error: () => {
          errors++;
          failed.push(id.substring(0, 6));
          if (completed + errors === ids.length) this._showBatchResult(completed, failed);
        }
      });
    });
  }

  private _handleBatchStatus(ids: string[], action: 'ganado' | 'perdido'): void {
    let completed = 0;
    let errors = 0;
    const failed: string[] = [];

    ids.forEach(id => {
      this.crmApi.updateSessionStatus(id, action === 'ganado' ? 'GANADO' : 'PERDIDO').subscribe({
        next: () => {
          completed++;
          this.leads.update(current => current.filter(l => l.session_id !== id));
          if (completed + errors === ids.length) this._showBatchResult(completed, failed);
        },
        error: () => {
          errors++;
          failed.push(id.substring(0, 6));
          if (completed + errors === ids.length) this._showBatchResult(completed, failed);
        }
      });
    });
  }

  private _showBatchResult(completed: number, failed: string[]) {
    const msg = failed.length
      ? `✅ ${completed} procesados — ⚠️ ${failed.length} errores: ${failed.join(', ')}`
      : `✅ ${completed} lead${completed === 1 ? '' : 's'} procesado${completed === 1 ? '' : 's'} correctamente`;
    this._showToast(msg, failed.length ? 'error' : 'success');
  }

  handleAssignment(event: {leadId: string, agentId: string}) {
    this.crmApi.assignLead(event.leadId, event.agentId).subscribe({
      next: () => {
        this.leads.update(current => current.filter(l => l.session_id !== event.leadId));
        this._showToast('Lead ' + event.leadId.substring(0,6) + ' asignado correctamente.');
      },
      error: (err) => {
        this._showToast('Error: ' + (err.error?.error || 'Falló la asignación'), 'error');
      }
    });
  }
}
