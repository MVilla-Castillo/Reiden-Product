import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CrmApiService } from '../../../infrastructure/repositories/crm.api.service';
import { LeadsGridComponent } from '../../components/shared/leads-grid.component';
import { Lead, Salesperson } from '../../../core/models/crm.models';

@Component({
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
                [class.active]="routingMode() === 'Manual'"
                (click)="toggleRoutingMode()">
                Enrutamiento Manual
             </button>
             <button 
                [class.active]="routingMode() === 'Auto'"
                (click)="toggleRoutingMode()">
                Automático (Round Robin)
             </button>
          </div>
        </div>
      </header>
      
      <div class="grid-wrapper">
        <app-leads-grid 
          [leads]="leads()" 
          [salesPersons]="salesPersons()"
          [canAssign]="routingMode() === 'Manual'"
          (assignLead)="handleAssignment($event)">
        </app-leads-grid>
      </div>

      <!-- Toast Notification -->
      @if (toastMessage()) {
        <div class="toast-notification success">
          <span class="toast-icon">✅</span>
          {{ toastMessage() }}
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
      position: absolute; top: 1rem; right: 1rem; padding: 1rem 1.5rem; border-radius: 8px; display: flex; align-items: center; gap: 0.75rem; font-weight: 500; font-size: 0.95rem; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); animation: slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .toast-notification.success { background: #ecfdf5; color: #065f46; border-left: 4px solid #10b981; }
    @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
  `]
})
export class LeadsComponent implements OnInit {
  crmApi = inject(CrmApiService);
  
  leads = signal<Lead[]>([]);
  salesPersons = signal<Salesperson[]>([]);
  routingMode = signal<'Auto' | 'Manual'>('Manual');
  toastMessage = signal<string | null>(null);

  ngOnInit() {
    this.refreshLeads();
    this.crmApi.getSalespeople().subscribe(sp => this.salesPersons.set(sp));
    
    this.crmApi.getTenantSettings().subscribe(settings => {
      this.routingMode.set(settings.routingMode);
    });
  }

  refreshLeads() {
    this.crmApi.getPendingLeads().subscribe(leads => this.leads.set(leads));
  }

  toggleRoutingMode() {
    const newMode = this.routingMode() === 'Auto' ? 'Manual' : 'Auto';
    this.routingMode.set(newMode);
    this.crmApi.updateTenantSettings(newMode).subscribe((res: any) => {
      this.toastMessage.set('El motor fue cambiado a Enrutamiento ' + newMode);
      setTimeout(() => this.toastMessage.set(null), 3000);
    });
  }

  handleAssignment(event: {leadId: string, agentId: string}) {
    // In a real scenario we'd do: this.crmApi.assignLead(event.leadId, event.agentId).subscribe(...)
    this.toastMessage.set('Has asignado correctamente el Lead ' + event.leadId.substring(0,6) + ' a este Vendedor.');
    
    // Remove it optimistically from the pending view
    this.leads.update(current => current.filter(l => l.id !== event.leadId));
    
    setTimeout(() => this.toastMessage.set(null), 3000);
  }
}
