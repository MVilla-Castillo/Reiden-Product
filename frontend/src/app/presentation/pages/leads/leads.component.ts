import { Component, inject, OnInit, OnDestroy, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CrmApiService } from '../../../infrastructure/repositories/crm.api.service';
import { SseService } from '../../../infrastructure/services/sse.service';
import { LeadsGridComponent, BatchActionEvent } from '../../components/shared/leads-grid.component';
import { TopBarComponent } from '../../components/shared/top-bar.component';
import { SessionDto, SalespersonDto } from '../../../core/models/crm.models';
import { Subscription } from 'rxjs';

@Component({
// ... (Keeping decorator matching)
  selector: 'app-leads',
  standalone: true,
  imports: [CommonModule, LeadsGridComponent, TopBarComponent],
  template: `
    <div class="leads-page">
      <app-top-bar title="Gestor de Leads" breadcrumb="Leads"></app-top-bar>
      
      <div class="grid-wrapper">
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
      background: var(--color-surface);
      padding: 1.5rem;
      border-radius: var(--radius-xl);
      box-shadow: var(--shadow-card);

      h1 { font-size: var(--font-xl); color: #111827; margin: 0 0 0.5rem; }
      p { color: var(--color-muted); margin: 0; font-size: var(--font-sm); }
    }

    .routing-control {
      text-align: right;
      label { display: block; font-size: var(--font-sm); color: var(--color-muted); margin-bottom: 0.5rem; font-weight: 500;}
      .toggle-switch { display: flex; gap: 4px; background: var(--color-bg); padding: 4px; border-radius: var(--radius-md); border: 1px solid var(--color-border);}
      button { border: none; background: transparent; padding: 8px 16px; border-radius: var(--radius-sm); font-weight: 600; color: var(--color-muted); cursor: pointer; transition: all 0.2s; font-size: var(--font-sm);}
      button.active { background: var(--color-surface); color: #111827; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    }

    .grid-wrapper {
      background: var(--color-surface);
      border-radius: var(--radius-xl);
      padding: 1.5rem;
      box-shadow: var(--shadow-card);
    }

    .toast-notification {
      position: fixed; top: 1rem; right: 1rem; max-width: 420px; padding: 0.875rem 1rem; border-radius: var(--radius-md); display: flex; align-items: flex-start; gap: 0.625rem; font-weight: 500; font-size: var(--font-sm); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); animation: slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1); z-index: 100;
    }
    .toast-notification.success { background: var(--color-success-bg); color: var(--color-success-text); border-left: 4px solid var(--color-success); }
    .toast-notification.error   { background: var(--color-danger-bg); color: var(--color-danger-text); border-left: 4px solid var(--color-danger); }
    .toast-text { flex: 1; }
    .toast-dismiss {
      background: none; border: none; cursor: pointer; color: inherit; opacity: 0.6; font-size: var(--font-sm); padding: 0; line-height: 1; flex-shrink: 0; margin-top: 1px;
      &:hover { opacity: 1; }
    }
    @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }

    .auto-assign-banner {
      display: flex; align-items: center; gap: 12px; padding: 16px 20px; background: var(--color-warning-bg); border-radius: var(--radius-lg); margin-bottom: 20px; border: 1px solid var(--color-warning);
    }
    .banner-icon { font-size: var(--font-lg); }
    .banner-text { flex: 1; color: var(--color-warning-text); font-weight: 500; font-size: var(--font-sm); }
    .btn-auto-assign {
      padding: 10px 20px; background: var(--color-warning); color: white; border: none; border-radius: var(--radius-md); font-weight: 600; cursor: pointer; transition: all 0.2s;
    }
    .btn-auto-assign:hover { background: var(--color-primary-hover); transform: translateY(-1px); }

    .failed-modal-overlay {
      position: absolute; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 200; border-radius: var(--radius-xl);
    }
    .failed-modal {
      background: var(--color-surface); border-radius: var(--radius-xl); padding: 1.5rem; max-width: 400px; width: 90%; box-shadow: 0 20px 40px rgba(0,0,0,0.15); animation: slideIn 0.2s cubic-bezier(0.16,1,0.3,1);
    }
    .failed-modal-header {
      display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;
      h4 { margin: 0; font-size: var(--font-sm); color: #111827; }
    }
    .modal-close { background: none; border: none; cursor: pointer; color: var(--color-muted); font-size: var(--font-sm); padding: 0; }
    .failed-list {
      list-style: none; padding: 0; margin: 0 0 1.25rem; max-height: 180px; overflow-y: auto;
      li { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; padding: 0.5rem 0; border-bottom: 1px solid var(--color-border); font-size: var(--font-sm); color: #374151; }
      li:last-child { border-bottom: none; }
    }
    .failed-id { font-weight: 600; flex-shrink: 0; }
    .failed-reason { color: var(--color-danger-text); font-size: var(--font-xs); text-align: right; }
    .failed-modal-actions { display: flex; gap: 0.75rem; }
    .btn-retry { flex: 1; padding: 0.625rem; background: var(--color-primary); color: white; border: none; border-radius: var(--radius-md); font-weight: 600; cursor: pointer; font-size: var(--font-sm); transition: opacity 0.15s; &:hover { opacity: 0.9; } }
    .btn-cancel { padding: 0.625rem 1rem; background: var(--color-bg); color: var(--color-muted); border: 1px solid var(--color-border); border-radius: var(--radius-md); font-weight: 500; cursor: pointer; font-size: var(--font-sm); transition: background 0.15s; &:hover { background: #e5e7eb; } }
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
  failedAutoLeads = signal<Array<{id: string; phone: string; reason: string}>>([]);
  showFailedModal = signal(false);
  private sseSub?: Subscription;
  private toastTimer?: ReturnType<typeof setTimeout>;

  ngOnInit() {
    this.sseSub = this.sseService.dashboardStream().subscribe(event => {
      if (event.type === 'snapshot') {
        this.leads.set(event.data.leads ?? []);
        this.salesPersons.set(event.data.salespeople ?? []);
        if (event.data.settings?.routing_mode) {
          this.routingMode.set(event.data.settings.routing_mode);
        }
      }

      if (event.type === 'pending_leads') {
        this.crmApi.getMyChats().subscribe(leads => this.leads.set(leads));
      }

      if (event.type === 'settings') {
        this.routingMode.set(event.data.routing_mode);
      }
    });

    this.crmApi.getMyChats().subscribe(leads => this.leads.set(leads));
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
