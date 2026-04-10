import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { interval, switchMap, filter } from 'rxjs';
import { CrmApiService } from '../../../infrastructure/repositories/crm.api.service';
import { SessionDto, BackendMessage } from '../../../core/models/crm.models';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss'
})
export class ChatComponent implements OnInit {
  private crmApi = inject(CrmApiService);

  chats = signal<SessionDto[]>([]);
  selectedSession = signal<SessionDto | null>(null);
  selectedSessionId = signal<string | null>(null);
  messages = signal<BackendMessage[]>([]);
  newMessage = signal('');

  constructor() {}

  ngOnInit() {
    this.loadMyChats();
    this.setupMessagePolling();
  }

  setupMessagePolling() {
    interval(3000).pipe(
      filter(() => !!this.selectedSessionId()),
      switchMap(() => this.crmApi.getMessages(this.selectedSessionId()!))
    ).subscribe(messages => {
      this.messages.set(messages);
    });
  }

  loadMyChats() {
    this.crmApi.getMyChats().subscribe(chats => {
      this.chats.set(chats);
    });
  }

  selectLead(chat: SessionDto) {
    this.selectedSession.set(chat);
    this.selectedSessionId.set(chat.session_id);
    this.loadMessages(chat.session_id);
  }

  loadMessages(sessionId: string) {
    this.crmApi.getMessages(sessionId).subscribe(messages => {
      this.messages.set(messages);
    });
  }

  send() {
    const sessionId = this.selectedSessionId();
    const body = this.newMessage();
    if (!sessionId || !body.trim()) return;

    this.crmApi.sendMessage(sessionId, body).subscribe((res) => {
      this.newMessage.set('');
      // Optimistic update
      const msg: BackendMessage = {
        message_id: res.message_id,
        direction: res.direction,
        body: res.body,
        created_at: res.created_at,
        provider_message_sid: res.provider_message_sid
      };
      this.messages.update(msgs => [...msgs, msg]);
    });
  }

  updateStatus(status: 'GANADO' | 'PERDIDO') {
    const sessionId = this.selectedSessionId();
    if (!sessionId) return;
    
    let lostReason: string | undefined;
    if (status === 'PERDIDO') {
      const reason = prompt('Por favor indique el motivo de pérdida del lead:');
      if (!reason) return; // User cancelled
      lostReason = reason;
    }

    this.crmApi.updateSessionStatus(sessionId, status, lostReason).subscribe(() => {
      this.loadMyChats();
      this.selectedSession.set(null);
      this.selectedSessionId.set(null);
    });
  }
}

