import { Component, Input, Output, EventEmitter, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Lead, SalesPerson } from '../../../core/models/lead.model';

type DateFilter = 'today' | 'week' | 'month' | 'year' | 'all' | 'custom';
type StatusFilter = 'all' | 'BOT' | 'PENDING_ASSIGNMENT' | 'CON_VENDEDOR' | 'GANADO' | 'PERDIDO';

interface FilterState {
  dateFilter: DateFilter;
  dateFrom: string;
  dateTo: string;
  status: StatusFilter;
  searchTerm: string;
}

@Component({
  selector: 'app-leads-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './leads-panel.component.html',
  styleUrl: './leads-panel.component.scss'
})
export class LeadsPanelComponent implements OnInit {
  @Input() leads: Lead[] = [];
  @Input() salesPersons: SalesPerson[] = [];
  @Input() canAssign = false;
  @Output() filterChange = new EventEmitter<FilterState>();
  @Output() assign = new EventEmitter<{ leadId: string; salesPersonId: string }>();

  openDropdownId = signal<string | null>(null);

  filters = signal<FilterState>({
    dateFilter: 'today',
    dateFrom: '',
    dateTo: '',
    status: 'all',
    searchTerm: ''
  });

  filteredLeads = computed(() => {
    let result = [...this.leads];
    const f = this.filters();

    if (f.status !== 'all') {
      result = result.filter(l => l.status === f.status);
    }

    if (f.searchTerm) {
      const term = f.searchTerm.toLowerCase();
      result = result.filter(l => 
        l.lead_phone_hash?.toLowerCase().includes(term) ||
        l.fsm_step?.toLowerCase().includes(term) ||
        l.vehicle_type?.toLowerCase().includes(term)
      );
    }

    return result;
  });

  stats = computed(() => {
    const leads = this.filteredLeads();
    return {
      total: leads.length,
      bot: leads.filter(l => l.status === 'BOT').length,
      pending: leads.filter(l => l.status === 'PENDING_ASSIGNMENT').length,
      active: leads.filter(l => l.status === 'CON_VENDEDOR').length,
      won: leads.filter(l => l.status === 'GANADO').length,
      lost: leads.filter(l => l.status === 'PERDIDO').length,
    };
  });

  ngOnInit(): void {
    this.emitFilterChange();
  }

  setDateFilter(filter: DateFilter): void {
    if (filter === 'custom') {
      this.filters.update(f => ({ ...f, dateFilter: 'custom' }));
      this.emitFilterChange();
      return;
    }

    const today = new Date();
    const todayStr = today.toISOString().split('T')[0];
    
    let dateFrom = '';
    let dateTo = '';

    switch (filter) {
      case 'today':
        dateFrom = todayStr;
        dateTo = todayStr;
        break;
      case 'week':
        const weekAgo = new Date(today);
        weekAgo.setDate(weekAgo.getDate() - 7);
        dateFrom = weekAgo.toISOString().split('T')[0];
        dateTo = todayStr;
        break;
      case 'month':
        const monthAgo = new Date(today);
        monthAgo.setMonth(monthAgo.getMonth() - 1);
        dateFrom = monthAgo.toISOString().split('T')[0];
        dateTo = todayStr;
        break;
      case 'year':
        const yearAgo = new Date(today);
        yearAgo.setFullYear(yearAgo.getFullYear() - 1);
        dateFrom = yearAgo.toISOString().split('T')[0];
        dateTo = todayStr;
        break;
      case 'all':
        dateFrom = '';
        dateTo = '';
        break;
    }

    this.filters.update(f => ({
      ...f,
      dateFilter: filter,
      dateFrom,
      dateTo
    }));

    this.emitFilterChange();
  }

  setStatusFilter(status: StatusFilter): void {
    this.filters.update(f => ({ ...f, status }));
  }

  onSearchChange(term: string): void {
    this.filters.update(f => ({ ...f, searchTerm: term }));
  }

  onDateRangeChange(): void {
    this.filters.update(f => ({ ...f, dateFilter: 'custom' }));
    this.emitFilterChange();
  }

  onDateFromChange(dateFrom: string): void {
    this.filters.update(f => ({ ...f, dateFrom, dateFilter: 'custom' }));
    this.emitFilterChange();
  }

  onDateToChange(dateTo: string): void {
    this.filters.update(f => ({ ...f, dateTo, dateFilter: 'custom' }));
    this.emitFilterChange();
  }

  toggleDropdown(event: Event, leadId: string): void {
    event.stopPropagation();
    this.openDropdownId.set(this.openDropdownId() === leadId ? null : leadId);
  }

  onAssign(event: Event, leadId: string, salesPersonId: string): void {
    event.stopPropagation();
    this.assign.emit({ leadId, salesPersonId });
    this.openDropdownId.set(null);
  }

  private emitFilterChange(): void {
    this.filterChange.emit(this.filters());
  }

  getSalesPersonName(id: string | null): string {
    if (!id) return 'Sin asignar';
    const sp = this.salesPersons.find(s => s.id === id);
    return sp ? sp.name : 'Sin asignar';
  }

  getStatusLabel(status: Lead['status']): string {
    const labels: Record<Lead['status'], string> = {
      'BOT': 'Flujo Bot',
      'PENDING_ASSIGNMENT': 'Pendiente',
      'CON_VENDEDOR': 'En Gestión',
      'GANADO': 'Ganado',
      'PERDIDO': 'Perdido',
      'ABANDONO_BOT': 'Abandonó'
    };
    return labels[status] || status;
  }

  getStatusClass(status: Lead['status']): string {
    const classes: Record<Lead['status'], string> = {
      'BOT': 'status-bot',
      'PENDING_ASSIGNMENT': 'status-pending',
      'CON_VENDEDOR': 'status-active',
      'GANADO': 'status-won',
      'PERDIDO': 'status-lost',
      'ABANDONO_BOT': 'status-abandoned'
    };
    return classes[status] || '';
  }

  getUrgencyClass(score: number): string {
    if (score >= 150) return 'urgency-high';
    if (score >= 80) return 'urgency-medium';
    return 'urgency-normal';
  }

  formatDate(dateStr: string | null): string {
    if (!dateStr) return '--';
    const date = new Date(dateStr);
    return date.toLocaleDateString('es-CL', { 
      day: '2-digit', 
      month: 'short',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  getWaitingTime(createdAt: string | null): string {
    if (!createdAt) return '--';
    const created = new Date(createdAt);
    const now = new Date();
    const hours = Math.floor((now.getTime() - created.getTime()) / (1000 * 60 * 60));
    
    if (hours < 1) return 'Ahora';
    if (hours < 24) return `${hours}h`;
    const days = Math.floor(hours / 24);
    return `${days}d`;
  }
}
