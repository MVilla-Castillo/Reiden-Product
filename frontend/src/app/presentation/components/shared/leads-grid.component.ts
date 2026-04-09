import { Component, Input, Output, EventEmitter, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Lead, SalesPerson } from '../../../core/models/lead.model';

@Component({
  selector: 'app-leads-grid',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './leads-grid.component.html',
  styleUrl: './leads-grid.component.scss'
})
export class LeadsGridComponent {
  @Input() leads: Lead[] = [];
  @Input() salesPersons: SalesPerson[] = [];
  @Input() canAssign = false;
  @Output() assign = new EventEmitter<{ leadId: string; salesPersonId: string }>();
  @Output() take = new EventEmitter<string>();

  openDropdownId = signal<string | null>(null);

  toggleDropdown(leadId: string) {
    this.openDropdownId.set(this.openDropdownId() === leadId ? null : leadId);
  }

  onAssign(leadId: string, salesPersonId: string) {
    this.assign.emit({ leadId, salesPersonId });
    this.openDropdownId.set(null);
  }

  getSalesPersonName(id: string | null): string {
    if (!id) return 'Sin asignar';
    const sp = this.salesPersons.find(s => s.id === id);
    return sp ? sp.name : 'Sin asignar';
  }

  getStatusLabel(status: Lead['status']): string {
    const labels: Record<Lead['status'], string> = {
      'bot_flow': 'Flujo Bot',
      'pending_assignment': 'Pendiente',
      'in_commercial_management': 'En Gestión',
      'won': 'Ganado',
      'lost': 'Perdido'
    };
    return labels[status];
  }

  getStatusClass(status: Lead['status']): string {
    const classes: Record<Lead['status'], string> = {
      'bot_flow': 'status-bot',
      'pending_assignment': 'status-pending',
      'in_commercial_management': 'status-active',
      'won': 'status-won',
      'lost': 'status-lost'
    };
    return classes[status];
  }

  closeDropdown() {
    this.openDropdownId.set(null);
  }
}