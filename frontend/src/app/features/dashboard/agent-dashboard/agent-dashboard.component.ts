import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
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
  imports: [CommonModule],
  templateUrl: './agent-dashboard.component.html',
  styleUrl: './agent-dashboard.component.css'
})
export class AgentDashboardComponent implements OnInit {
  chats: ChatPreview[] = [];
  selectedChatId: string | null = null;
  messages: Message[] = [];
  profile: ClientProfile | null = null;

  constructor(private crmService: CrmApiService) {}

  ngOnInit() {
    this.fetchChats();
  }

  fetchChats() {
    this.crmService.getAssignedChats().subscribe({
      next: (data) => {
        if (data && data.length > 0) {
          this.chats = data;
          // Automatically select the first chat
          this.selectChat(this.chats[0].id);
        }
      },
      error: (err) => console.error('Error fetching chats', err)
    });
  }

  selectChat(id: string) {
    this.selectedChatId = id;
    this.messages = []; // clear current UI
    
    // Attempt to load profile embedded in chat list if any
    const selected = this.chats.find(c => c.id === id);
    if (selected && selected.profile) {
      this.profile = selected.profile;
    } else {
      this.profile = null;
    }

    // Fetch messages for this session
    this.crmService.getChatMessages(id).subscribe({
      next: (data) => {
        if (data) {
          this.messages = data;
        }
      },
      error: (err) => console.error(`Error loading messages for session ${id}`, err)
    });
  }

  sendMessageAction(text: string) {
    if (!this.selectedChatId || !text.trim()) return;

    this.crmService.sendMessage(this.selectedChatId, text).subscribe({
      next: (res) => {
        // Optimistically push the message to UI (or rely on response)
        this.messages.push({
          sender: 'vendedor',
          avatar: '/assets/logo-pagina-r.png',
          text: text
        });
      },
      error: (err) => console.error('Error sending message', err)
    });
  }

  updateLeadStatusAction(status: string) {
    if (!this.selectedChatId) return;

    this.crmService.updateLeadStatus(this.selectedChatId, status).subscribe({
      next: (res) => {
         console.log('Status updated to', status);
      },
      error: (err) => console.error('Error updating status', err)
    });
  }
}
