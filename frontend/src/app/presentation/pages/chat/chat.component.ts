import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { interval, switchMap } from 'rxjs';
import { LeadRepositoryService } from '../../../infrastructure/repositories/lead.repository';
import { ChatRepositoryService, Message } from '../../../infrastructure/repositories/chat.repository';
import { Lead } from '../../../core/models/lead.model';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss'
})
export class ChatComponent implements OnInit {
  private leadRepo = inject(LeadRepositoryService);
  private chatRepo = inject(ChatRepositoryService);

  leads = signal<Lead[]>([]);
  selectedSessionId = signal<string | null>(null);
  messages = signal<Message[]>([]);
  newMessage = signal('');

  constructor() {}

  ngOnInit() {
    this.loadMyLeads();
    this.setupMessagePolling();
  }

  setupMessagePolling() {
    interval(5000).pipe(
      switchMap(() => {
        const sessionId = this.selectedSessionId();
        if (sessionId) {
          return this.chatRepo.getMessages(sessionId);
        }
        return [];
      })
    ).subscribe(res => {
      if (res && typeof res === 'object' && 'messages' in res) {
        this.messages.set(res.messages);
      }
    });
  }

  loadMyLeads() {
    this.leadRepo.getAll().subscribe(leads => {
      this.leads.set(leads);
    });
  }

  selectLead(id: string) {
    this.selectedSessionId.set(id);
    this.loadMessages(id);
  }

  loadMessages(sessionId: string) {
    this.chatRepo.getMessages(sessionId).subscribe(session => {
      this.messages.set(session.messages);
    });
  }

  send() {
    const sessionId = this.selectedSessionId();
    const body = this.newMessage();
    if (!sessionId || !body) return;

    this.chatRepo.sendMessage(sessionId, body).subscribe(() => {
      this.newMessage.set('');
      this.loadMessages(sessionId);
    });
  }
}

