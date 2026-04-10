import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Lead, Salesperson } from '../../../core/models/crm.models';

@Component({
  selector: 'app-leads-grid',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './leads-grid.component.html',
  styleUrl: './leads-grid.component.scss'
})
export class LeadsGridComponent {
  @Input() leads: Lead[] = [];
  @Input() salesPersons: Salesperson[] = [];
  @Input() canAssign = false;
  
  @Output() assignLead = new EventEmitter<{leadId: string, agentId: string}>();

  onAssign(leadId: string, event: Event) {
    const target = event.target as HTMLSelectElement;
    const agentId = target.value;
    if (agentId) {
      this.assignLead.emit({ leadId, agentId });
      // Reset dropdown dynamically if you want it to behave like a transient action
      target.value = '';
    }
  }
}