import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { interval, switchMap, filter } from 'rxjs';
import { CrmApiService } from '../../../infrastructure/repositories/crm.api.service';
import { ChatSession, Message } from '../../../core/models/crm.models';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss'
})
export class ChatComponent implements OnInit {
  private crmApi = inject(CrmApiService);

  chats = signal<ChatSession[]>([]);
  selectedSession = signal<ChatSession | null>(null);
  selectedSessionId = signal<string | null>(null);
  messages = signal<Message[]>([]);
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

  selectLead(chat: ChatSession) {
    this.selectedSession.set(chat);
    this.selectedSessionId.set(chat.id);
    this.loadMessages(chat.id);
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
      this.messages.update(msgs => [...msgs, res.messageObj]);
    });
  }

  updateStatus(status: 'GANADO' | 'PERDIDO') {
    const sessionId = this.selectedSessionId();
    if (!sessionId) return;
    this.crmApi.updateSessionStatus(sessionId, status).subscribe(() => {
      this.loadMyChats();
      this.selectedSession.set(null);
      this.selectedSessionId.set(null);
    });
  }
}

