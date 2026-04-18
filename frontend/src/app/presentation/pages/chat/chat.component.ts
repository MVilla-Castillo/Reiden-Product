import { Component, inject, signal, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { CrmApiService } from '../../../infrastructure/repositories/crm.api.service';
import { SseService } from '../../../infrastructure/services/sse.service';
import { SessionDto, BackendMessage } from '../../../core/models/crm.models';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss'
})
export class ChatComponent implements OnInit, OnDestroy {
  private crmApi = inject(CrmApiService);
  private sseService = inject(SseService);

  chats = signal<SessionDto[]>([]);
  selectedSession = signal<SessionDto | null>(null);
  selectedSessionId = signal<string | null>(null);
  messages = signal<BackendMessage[]>([]);
  newMessage = signal('');

  private msgSseSub?: Subscription;

  constructor() {}

  ngOnInit() {
    this.loadMyChats();
  }

  ngOnDestroy() {
    this.msgSseSub?.unsubscribe();
  }

  loadMyChats() {
    this.crmApi.getMyChats().subscribe(chats => {
      this.chats.set(chats);
    });
  }

  selectLead(chat: SessionDto) {
    this.selectedSession.set(chat);
    this.selectedSessionId.set(chat.session_id);

    // Carga el historial completo una sola vez
    this.crmApi.getMessages(chat.session_id).subscribe(messages => {
      this.messages.set(messages);
    });

    // Cierra la conexión anterior (si se cambia de sesión) y abre la nueva
    this.msgSseSub?.unsubscribe();
    this.msgSseSub = this.sseService.messagesStream(chat.session_id).subscribe(event => {
      if (event.type === 'message') {
        this.messages.update(msgs => {
          // Deduplicar: evita agregar mensajes que ya están (ej. update optimista de OUTBOUND)
          const incoming = event.data as BackendMessage;
          const alreadyExists = incoming.message_id
            ? msgs.some(m => m.message_id === incoming.message_id)
            : false;
          return alreadyExists ? msgs : [...msgs, incoming];
        });
      }

      if (event.type === 'status_change') {
        this.selectedSession.update(s =>
          s ? { ...s, status: event.data.status } : s
        );
        this.chats.update(cs =>
          cs.map(c =>
            c.session_id === event.data.session_id ? { ...c, status: event.data.status } : c
          )
        );
      }
    });
  }

  send() {
    const sessionId = this.selectedSessionId();
    const body = this.newMessage();
    if (!sessionId || !body.trim()) return;

    this.crmApi.sendMessage(sessionId, body).subscribe(res => {
      this.newMessage.set('');
      // Actualización optimista: agrega inmediatamente sin esperar el evento SSE
      const msg: BackendMessage = {
        message_id: res.message_id,
        direction: res.direction,
        body: res.body,
        created_at: res.created_at,
        provider_message_sid: res.provider_message_sid
      };
      this.messages.update(msgs => [...msgs, msg]);
      // El evento SSE que llegará después será deduplicado por message_id
    });
  }

  updateStatus(status: 'GANADO' | 'PERDIDO') {
    const sessionId = this.selectedSessionId();
    if (!sessionId) return;

    let lostReason: string | undefined;
    if (status === 'PERDIDO') {
      const reason = prompt('Por favor indique el motivo de pérdida del lead:');
      if (!reason) return;
      lostReason = reason;
    }

    this.crmApi.updateSessionStatus(sessionId, status, lostReason).subscribe(() => {
      this.loadMyChats();
      this.selectedSession.set(null);
      this.selectedSessionId.set(null);
      this.msgSseSub?.unsubscribe();
    });
  }
}
