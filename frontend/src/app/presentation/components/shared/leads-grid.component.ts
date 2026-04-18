import { Component, Input, Output, EventEmitter, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SessionDto, SalespersonDto } from '../../../core/models/crm.models';

// ── Mapas de etiquetas legibles ────────────────────────────────────────────
export const STATUS_LABELS: Record<string, string> = {
  PENDING_ASSIGNMENT: 'Pendiente',
  CON_VENDEDOR:       'Con Vendedor',
  GANADO:             'Ganado',
  PERDIDO:            'Perdido',
  BOT:                'Flujo Bot',
  ABANDONED:          'Abandonado',
};

export const INTENT_LABELS: Record<string, string> = {
  HOY:         'Hoy',
  ESTA_SEMANA: 'Esta semana',
  MES_O_MAS:   'Mes o más',
};

@Component({
  selector: 'app-leads-grid',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './leads-grid.component.html',
  styleUrl: './leads-grid.component.scss'
})
export class LeadsGridComponent {
  @Input() leads: SessionDto[] = [];
  @Input() salesPersons: SalespersonDto[] = [];
  @Input() canAssign = false;

  @Output() assignLead = new EventEmitter<{ leadId: string; agentId: string }>();

  // Exponer los mapas al template
  readonly statusLabels  = STATUS_LABELS;
  readonly intentLabels  = INTENT_LABELS;

  // ── Estado de filtros ──────────────────────────────────────────────────
  searchText          = signal('');
  filterStatus        = signal('');
  filterPurchaseIntent = signal('');
  filterDateFrom      = signal('');
  filterDateTo        = signal('');

  // ── Opciones estáticas predefinidas (no dependen de datos) ───────────────
  get availableStatuses(): string[] {
    return Object.keys(STATUS_LABELS);
  }

  get availablePurchaseIntents(): string[] {
    return Object.keys(INTENT_LABELS);
  }

  // ── Lista filtrada ─────────────────────────────────────────────────────
  get filteredLeads(): SessionDto[] {
    const text   = this.searchText().toLowerCase().trim();
    const status = this.filterStatus();
    const intent = this.filterPurchaseIntent();
    const from   = this.filterDateFrom();
    const to     = this.filterDateTo();

    return this.leads.filter(lead => {
      // Búsqueda de texto: ID, hash de teléfono o vehículo
      if (text) {
        const matchId      = lead.session_id.toLowerCase().includes(text);
        const matchPhone   = lead.lead_phone_hash.toLowerCase().includes(text);
        const matchVehicle = (lead.vehicle_type ?? '').toLowerCase().includes(text);
        if (!matchId && !matchPhone && !matchVehicle) return false;
      }

      // Filtro de estado (compara valor crudo del backend)
      if (status && lead.status !== status) return false;

      // Filtro de intención de compra
      if (intent && lead.purchase_intent !== intent) return false;

      // Filtro de rango de fechas (YYYY-MM-DD del ISO string en offset Chile)
      const datePart = lead.created_at?.substring(0, 10) ?? '';
      if (from && datePart < from) return false;
      if (to   && datePart > to)   return false;

      return true;
    });
  }

  get hasActiveFilters(): boolean {
    return !!(
      this.searchText()           ||
      this.filterStatus()         ||
      this.filterPurchaseIntent() ||
      this.filterDateFrom()       ||
      this.filterDateTo()
    );
  }

  clearFilters(): void {
    this.searchText.set('');
    this.filterStatus.set('');
    this.filterPurchaseIntent.set('');
    this.filterDateFrom.set('');
    this.filterDateTo.set('');
  }

  statusLabel(raw: string): string {
    return this.statusLabels[raw] ?? raw;
  }

  intentLabel(raw: string): string {
    return this.intentLabels[raw] ?? raw;
  }

  onAssign(leadId: string, event: Event): void {
    const target = event.target as HTMLSelectElement;
    const agentId = target.value;
    if (agentId) {
      this.assignLead.emit({ leadId, agentId });
      target.value = '';
    }
  }
}
