import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { interval, Subscription } from 'rxjs';
import { CrmApiService } from '../../../core/services/crm-api.service';

interface ChatPreview {
  id: string;
  name: string;
  avatar: string;
  vehicle: string;
  lastMessage: string;
  time: string;
  status: 'Activo' | 'En espera' | string;
  profile?: ClientProfile;
}

interface Message {
  sender: 'cliente' | 'vendedor' | string;
  avatar: string;
  text: string;
  timestamp?: string;
}

interface ClientProfile {
  carModel: string;
  paymentMethod: string;
  budget: string;
  urgency: string;
  phone: string;
  email: string;
}

@Component({
  selector: 'app-agent-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './agent-dashboard.component.html',
  styleUrl: './agent-dashboard.component.css'
})
export class AgentDashboardComponent implements OnInit, OnDestroy {
  chats: ChatPreview[] = [];
  selectedChatId: string | null = null;
  messages: Message[] = [];
  profile: ClientProfile | null = null;
  newMessage: string = '';

  private pollingSubscription?: Subscription;

  constructor(private crmService: CrmApiService) {}

  ngOnInit() {
    this.fetchChats();
    this.startPolling();
  }

  ngOnDestroy() {
    this.stopPolling();
  }

  startPolling() {
    this.pollingSubscription = interval(10000).subscribe(() => {
      this.fetchChats();
    });
  }

  stopPolling() {
    this.pollingSubscription?.unsubscribe();
  }

  fetchChats() {
    this.crmService.getAssignedChats().subscribe({
      next: (response) => {
        const leads = response?.leads || [];
        const activeChats = leads.filter((l: any) => 
          l.status === 'CON_VENDEDOR' || l.status === 'PENDING_ASSIGNMENT'
        );
        this.chats = activeChats.map((lead: any) => this.mapChat(lead));
        
        if (this.chats.length > 0 && !this.selectedChatId) {
          this.selectChat(this.chats[0].id);
        }
      },
      error: (err) => console.error('Error fetching chats', err)
    });
  }

  private mapChat(lead: any): ChatPreview {
    const vehicleMap: Record<string, string> = {
      'CITY_CAR': 'Auto City',
      'SUV': 'SUV',
      'SEDAN': 'Sedán',
      'PICKUP': 'Pickup',
    };
    return {
      id: lead.session_id,
      name: lead.lead_phone_hash?.substring(0, 8) || 'Lead',
      avatar: 'assets/logo-pagina-r.svg',
      vehicle: vehicleMap[lead.vehicle_type] || lead.vehicle_type || '--',
      lastMessage: lead.fsm_step || '',
      time: this.formatDate(lead.updated_at),
      status: lead.status === 'CON_VENDEDOR' ? 'Activo' : 'En espera',
    };
  }

  private formatDate(dateStr: string): string {
    if (!dateStr) return '--';
    const date = new Date(dateStr);
    return date.toLocaleDateString('es-CL', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  selectChat(id: string) {
    this.selectedChatId = id;
    this.messages = [];
    this.profile = null;

    this.crmService.getChatMessages(id).subscribe({
      next: (data) => {
        const msgs = data?.messages || [];
        this.messages = msgs.map((m: any) => ({
          sender: m.direction === 'OUTGOING' ? 'vendedor' : 'cliente',
          avatar: 'assets/logo-pagina-r.svg',
          text: m.text || m.body || '',
          timestamp: m.created_at
        }));
      },
      error: (err) => console.error(`Error loading messages for session ${id}`, err)
    });
  }

  sendMessage() {
    if (!this.selectedChatId || !this.newMessage.trim()) return;

    this.crmService.sendMessage(this.selectedChatId, this.newMessage).subscribe({
      next: () => {
        this.messages.push({
          sender: 'vendedor',
          avatar: 'assets/logo-pagina-r.svg',
          text: this.newMessage,
          timestamp: new Date().toISOString()
        });
        this.newMessage = '';
      },
      error: (err) => console.error('Error sending message', err)
    });
  }

  updateLeadStatus(status: string) {
    if (!this.selectedChatId) return;

    this.crmService.updateLeadStatus(this.selectedChatId, status).subscribe({
      next: () => {
        this.fetchChats();
      },
      error: (err) => console.error('Error updating status', err)
    });
  }
}
