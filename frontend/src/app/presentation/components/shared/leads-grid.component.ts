import { Component, Input, Output, EventEmitter, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { SessionDto, SalespersonDto } from '../../../core/models/crm.models';
import { EmptyStateComponent } from './empty-state.component';

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

export type BatchActionEvent =
  | { action: 'assign';   ids: string[]; agentId: string }
  | { action: 'ganado' | 'perdido'; ids: string[] };

@Component({
  selector: 'app-leads-grid',
  standalone: true,
  imports: [CommonModule, FormsModule, EmptyStateComponent],
  templateUrl: './leads-grid.component.html',
  styleUrl: './leads-grid.component.scss'
})
export class LeadsGridComponent {
  @Input() leads: SessionDto[] = [];
  @Input() salesPersons: SalespersonDto[] = [];
  @Input() canAssign = false;

  @Output() assignLead  = new EventEmitter<{ leadId: string; agentId: string }>();
  @Output() batchAction = new EventEmitter<BatchActionEvent>();
  @Output() clearFilters = new EventEmitter<void>();

  private readonly router = inject(Router);

  // Exponer los mapas al template
  readonly statusLabels  = STATUS_LABELS;
  readonly intentLabels  = INTENT_LABELS;

  // ── Estado de filtros ──────────────────────────────────────────────────
  searchText          = signal('');
  filterStatus        = signal('');
  filterPurchaseIntent = signal('');
  filterDateFrom      = signal('');
  filterDateTo        = signal('');

  // ── Estado de ordenamiento ────────────────────────────────────────────
  sortColumn = signal('');
  sortDirection = signal<'asc' | 'desc'>('asc');

  // ── Selección batch ────────────────────────────────────────────────────
  selectedIds    = signal<Set<string>>(new Set());
  batchAssignTo  = signal('');

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
    const col    = this.sortColumn();
    const dir    = this.sortDirection();

    let result = this.leads.filter(lead => {
      if (text) {
        const matchId      = lead.session_id.toLowerCase().includes(text);
        const matchPhone   = lead.lead_phone_hash.toLowerCase().includes(text);
        const matchVehicle = (lead.vehicle_type ?? '').toLowerCase().includes(text);
        if (!matchId && !matchPhone && !matchVehicle) return false;
      }
      if (status && lead.status !== status) return false;
      if (intent && lead.purchase_intent !== intent) return false;
      const datePart = lead.created_at?.substring(0, 10) ?? '';
      if (from && datePart < from) return false;
      if (to   && datePart > to)   return false;
      return true;
    });

    if (col) {
      result = [...result].sort((a, b) => {
        let valA: string | number | null = null;
        let valB: string | number | null = null;

        switch (col) {
          case 'vehicle':   valA = a.vehicle_type ?? '';       valB = b.vehicle_type ?? '';       break;
          case 'intent':    valA = a.purchase_intent ?? '';    valB = b.purchase_intent ?? '';    break;
          case 'status':   valA = a.status ?? '';              valB = b.status ?? '';             break;
          case 'received':  valA = a.created_at ?? '';         valB = b.created_at ?? '';         break;
          case 'score':     valA = a.urgency_score ?? 0;       valB = b.urgency_score ?? 0;       break;
        }

        const cmp = this._compareValues(valA, valB);
        return dir === 'asc' ? cmp : -cmp;
      });
    }

    return result;
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

  onClearFilters(): void {
    this.searchText.set('');
    this.filterStatus.set('');
    this.filterPurchaseIntent.set('');
    this.filterDateFrom.set('');
    this.filterDateTo.set('');
    this.sortColumn.set('');
    this.sortDirection.set('asc');
    this.clearFilters.emit();
  }

  onSort(column: string): void {
    if (this.sortColumn() === column) {
      this.sortDirection.set(this.sortDirection() === 'asc' ? 'desc' : 'asc');
    } else {
      this.sortColumn.set(column);
      this.sortDirection.set('asc');
    }
  }

  onContactClick(lead: SessionDto): void {
    this.router.navigate(['/chat'], { queryParams: { session: lead.session_id } });
  }

  private _compareValues(a: string | number | null, b: string | number | null): number {
    if (a === null || a === undefined) return 1;
    if (b === null || b === undefined) return -1;
    if (typeof a === 'number' && typeof b === 'number') return a - b;
    return String(a).localeCompare(String(b));
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

  // ── Batch selection ────────────────────────────────────────────────────
  get selectionCount(): number { return this.selectedIds().size; }

  get allSelected(): boolean {
    const sel = this.selectedIds();
    const rows = this.filteredLeads;
    return rows.length > 0 && rows.every(l => sel.has(l.session_id));
  }

  isSelected(id: string): boolean { return this.selectedIds().has(id); }

  toggleSelect(id: string): void {
    this.selectedIds.update(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  toggleSelectAll(): void {
    if (this.allSelected) {
      this.selectedIds.set(new Set());
    } else {
      this.selectedIds.set(new Set(this.filteredLeads.map(l => l.session_id)));
    }
  }

  clearSelection(): void {
    this.selectedIds.set(new Set());
    this.batchAssignTo.set('');
  }

  executeBatchAssign(): void {
    const ids = Array.from(this.selectedIds());
    const agentId = this.batchAssignTo();
    if (!ids.length || !agentId) return;
    this.batchAction.emit({ action: 'assign', ids, agentId });
    this.clearSelection();
  }

  executeBatchStatus(action: 'ganado' | 'perdido'): void {
    const ids = Array.from(this.selectedIds());
    if (!ids.length) return;
    this.batchAction.emit({ action, ids });
    this.clearSelection();
  }
}
