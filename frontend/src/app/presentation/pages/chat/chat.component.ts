import { Component, inject, signal, computed, OnInit, OnDestroy, ViewChild, ElementRef, AfterViewChecked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ScrollingModule } from '@angular/cdk/scrolling';
import { Subscription } from 'rxjs';
import { ActivatedRoute, Router } from '@angular/router';
import { CrmApiService } from '../../../infrastructure/repositories/crm.api.service';
import { SseService } from '../../../infrastructure/services/sse.service';
import { SessionDto, BackendMessage, LeadNameHistory } from '../../../core/models/crm.models';
import { EmptyStateComponent } from '../../components/shared/empty-state.component';
import { TopBarComponent } from '../../components/shared/top-bar.component';
import { IconComponent } from '../../components/shared/icons.component';
import { GuideButtonComponent } from '../../components/shared/guide-button.component';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule, ScrollingModule, EmptyStateComponent, TopBarComponent, IconComponent, GuideButtonComponent],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss'
})
export class ChatComponent implements OnInit, OnDestroy, AfterViewChecked {
  @ViewChild('messagesContainer') private messagesContainer?: ElementRef<HTMLDivElement>;
  @ViewChild('nameInput') private nameInputRef?: ElementRef<HTMLInputElement>;

  private crmApi = inject(CrmApiService);
  private sseService = inject(SseService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  chats = signal<SessionDto[]>([]);
  selectedSession = signal<SessionDto | null>(null);
  selectedSessionId = signal<string | null>(null);
  messages = signal<BackendMessage[]>([]);
  newMessage = signal('');
  sseReconnecting = signal(false);
  fileUploadError = signal<string | null>(null);
  uploadProgress = signal(0);
  isUploading = signal(false);
  failedUploadFile = signal<File | null>(null);
  useVirtualScroll = computed(() => this.chats().length > 50);

  messageOffset = signal(0);
  hasMoreMessages = signal(true);
  isLoadingMore = signal(false);
  isAtBottom = signal(true);
  isAtTop = signal(false);

  chatFilter = signal<'all' | 'active' | 'won' | 'lost' | 'abandoned'>('all');
  filteredChats = computed(() => {
    const filter = this.chatFilter();
    const allChats = this.chats();
    if (filter === 'all') return allChats;
    if (filter === 'active') return allChats.filter(c => c.status === 'CON_VENDEDOR');
    if (filter === 'won') return allChats.filter(c => c.status === 'GANADO');
    if (filter === 'lost') return allChats.filter(c => c.status === 'PERDIDO');
    if (filter === 'abandoned') return allChats.filter(c => c.status === 'ABANDONO_BOT');
    return allChats;
  });

  private uploadController: AbortController | null = null;
  private shouldScrollToBottom = false;

  private msgSseSub?: Subscription;
  private dashboardSseSub?: Subscription;
  private queryParamsSub?: Subscription;

  constructor() {}

  ngOnInit() {
    this.loadMyChats();
    this.dashboardSseSub = this.sseService.dashboardStream().subscribe(event => {
      if (event.type === 'snapshot' || event.type === 'pending_leads') {
        this.loadMyChats();
      }

      if (event.type === 'lead_updated') {
        const { session_id, lead_profile_name } = event.data ?? {};
        if (!session_id) return;
        this.chats.update(chats => chats.map(c =>
          c.session_id === session_id ? { ...c, lead_profile_name } : c
        ));
        this.selectedSession.update(s =>
          s && s.session_id === session_id ? { ...s, lead_profile_name } : s
        );
      }
    });
    this.queryParamsSub = this.route.queryParams.subscribe(params => {
      const sessionId = params['session'];
      if (!sessionId) return;

      const existing = this.chats().find(c => c.session_id === sessionId);
      if (existing) {
        this.selectLead(existing);
      } else {
        this.crmApi.getMyChats().subscribe(chats => {
          const chat = chats.find(c => c.session_id === sessionId);
          if (chat) {
            this.chats.set(chats);
            this.selectLead(chat);
          }
        });
      }
    });
  }

  ngOnDestroy() {
    this.msgSseSub?.unsubscribe();
    this.dashboardSseSub?.unsubscribe();
    this.queryParamsSub?.unsubscribe();
  }

  ngAfterViewChecked() {
    if (this.shouldScrollToBottom) {
      this.scrollToBottom(false);
      this.shouldScrollToBottom = false;
    }
  }

  loadMyChats() {
    this.crmApi.getMyChats().subscribe(chats => {
      this.chats.set(chats);
    });
  }

  trackChat(_: number, chat: SessionDto) { return chat.session_id; }

  handleFileSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    input.value = '';

    const allowed = ['image/jpeg', 'image/png', 'application/pdf', 'video/mp4'];
    if (!allowed.includes(file.type)) {
      this.fileUploadError.set('Tipos permitidos: JPG, PNG, PDF, MP4');
      return;
    }
    const isVideo = file.type.startsWith('video/');
    const maxBytes = isVideo ? 100 * 1024 * 1024 : 16 * 1024 * 1024;
    if (file.size > maxBytes) {
      this.fileUploadError.set(`Archivo demasiado grande. Máximo: ${isVideo ? '100 MB' : '16 MB'}.`);
      return;
    }
    this.startUpload(file);
  }

  startUpload(file: File) {
    const sessionId = this.selectedSessionId();
    if (!sessionId) return;

    this.fileUploadError.set(null);
    this.isUploading.set(true);
    this.uploadProgress.set(0);
    this.failedUploadFile.set(null);

    this.uploadController = new AbortController();
    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) this.uploadProgress.set(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      this.isUploading.set(false);
      this.uploadProgress.set(0);
      if (xhr.status < 200 || xhr.status >= 300) {
        this.failedUploadFile.set(file);
        this.fileUploadError.set('Error al enviar el archivo. Toca reintentar.');
      }
    };
    xhr.onerror = () => {
      this.isUploading.set(false);
      this.uploadProgress.set(0);
      this.failedUploadFile.set(file);
      this.fileUploadError.set('Error de red al enviar el archivo. Toca reintentar.');
    };
    xhr.onabort = () => {
      this.isUploading.set(false);
      this.uploadProgress.set(0);
    };

    const token = localStorage.getItem('access_token');
    const userId = localStorage.getItem('user_id');
    xhr.open('POST', `/api/v1/dashboard/leads/${sessionId}/media/`);
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    if (userId) xhr.setRequestHeader('X-User-ID', userId);
    this.uploadController.signal.addEventListener('abort', () => xhr.abort());
    xhr.send(formData);
  }

  cancelUpload() {
    this.uploadController?.abort();
    this.uploadController = null;
  }

  retryUpload() {
    const file = this.failedUploadFile();
    if (file) this.startUpload(file);
  }

  openFirstChatForGuide = (): void => {
    const first = this.filteredChats()[0];
    if (!this.selectedSession() && first) {
      this.selectLead(first);
    }
  };

  selectLead(chat: SessionDto) {
    this.selectedSession.set(chat);
    this.selectedSessionId.set(chat.session_id);
    this.messageOffset.set(0);
    this.hasMoreMessages.set(true);
    this.isAtBottom.set(true);
    this.isAtTop.set(false);
    this.nameHistory.set([]);

    this.crmApi.getMessages(chat.session_id, 20, 0).subscribe(messages => {
      this.messages.set(messages);
      this.hasMoreMessages.set(messages.length === 20);
      this.shouldScrollToBottom = true;
    });

    // Cierra la conexión anterior (si se cambia de sesión) y abre la nueva
    this.msgSseSub?.unsubscribe();
    this.sseReconnecting.set(false);
    this.msgSseSub = this.sseService.messagesStream(chat.session_id).subscribe(event => {
      if (event.type === 'sse_reconnecting') {
        this.sseReconnecting.set(true);
        return;
      }
      if (event.type === 'sse_connected') {
        this.sseReconnecting.set(false);
        return;
      }

      if (event.type === 'message') {
        this.messages.update(msgs => {
          const incoming = event.data as BackendMessage;
          const alreadyExists = incoming.message_id
            ? msgs.some(m => m.message_id === incoming.message_id)
            : false;
          if (!alreadyExists) {
            setTimeout(() => this.scrollToBottom(false), 0);
          }
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

    const tempId = `temp_${Date.now()}`;
    const optimisticMsg: BackendMessage = {
      message_id: tempId,
      direction: 'OUTBOUND',
      body,
      created_at: new Date().toISOString(),
      delivery_status: 'pending',
    };
    this.messages.update(msgs => [...msgs, optimisticMsg]);
    this.newMessage.set('');
    this.shouldScrollToBottom = true;

    this.crmApi.sendMessage(sessionId, body).subscribe({
      next: res => {
        const confirmed: BackendMessage = {
          message_id: res.message_id,
          direction: res.direction,
          body: res.body,
          created_at: res.created_at,
          provider_message_sid: res.provider_message_sid,
          delivery_status: 'sent',
        };
        this.messages.update(msgs => this._replaceMessage(tempId, confirmed, msgs));
      },
      error: () => {
        this.messages.update(msgs => this._updateStatus(tempId, 'failed', msgs));
      },
    });
  }

  retryMessage(msgId: string) {
    const msg = this.messages().find(m => m.message_id === msgId);
    if (!msg || msg.delivery_status !== 'failed') return;
    this.messages.update(msgs => this._updateStatus(msgId, 'pending', msgs));
    const sessionId = this.selectedSessionId();
    if (!sessionId) return;

    this.crmApi.sendMessage(sessionId, msg.body).subscribe({
      next: res => {
        const confirmed: BackendMessage = {
          message_id: res.message_id,
          direction: res.direction,
          body: res.body,
          created_at: res.created_at,
          provider_message_sid: res.provider_message_sid,
          delivery_status: 'sent',
        };
        this.messages.update(msgs => this._replaceMessage(msgId, confirmed, msgs));
      },
      error: () => {
        this.messages.update(msgs => this._updateStatus(msgId, 'failed', msgs));
      },
    });
  }

  private _replaceMessage(tempId: string, confirmed: BackendMessage, msgs: BackendMessage[]): BackendMessage[] {
    const replaced = msgs.map(m => m.message_id === tempId ? confirmed : m);
    // Si SSE llegó antes que HTTP, el mensaje real ya fue agregado al array.
    // Deduplicar por message_id para evitar que aparezca dos veces.
    const seen = new Set<string>();
    return replaced.filter(m => {
      if (!m.message_id) return true;
      if (seen.has(m.message_id)) return false;
      seen.add(m.message_id);
      return true;
    });
  }

  private _updateStatus(msgId: string, status: BackendMessage['delivery_status'], msgs: BackendMessage[]): BackendMessage[] {
    return msgs.map(m => m.message_id === msgId ? { ...m, delivery_status: status } : m);
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

  loadMoreMessages() {
    const sessionId = this.selectedSessionId();
    if (!sessionId || this.isLoadingMore() || !this.hasMoreMessages()) return;

    this.isLoadingMore.set(true);
    const newOffset = this.messageOffset() + 20;

    this.crmApi.getMessages(sessionId, 20, newOffset).subscribe({
      next: olderMessages => {
        const el = this.messagesContainer?.nativeElement;
        const prevScrollHeight = el?.scrollHeight ?? 0;
        this.messages.update(msgs => [...olderMessages, ...msgs]);
        this.messageOffset.set(newOffset);
        this.hasMoreMessages.set(olderMessages.length === 20);
        this.isLoadingMore.set(false);
        // Restaurar posición para que el viewport no salte al inicio
        if (el) setTimeout(() => { el.scrollTop = el.scrollHeight - prevScrollHeight; }, 0);
      },
      error: () => {
        this.isLoadingMore.set(false);
      }
    });
  }

  onMessagesScroll(event: Event) {
    const target = event.target as HTMLDivElement;
    const atTop = target.scrollTop <= 50;
    const atBottom = target.scrollHeight - target.scrollTop - target.clientHeight <= 50;

    this.isAtTop.set(atTop);
    this.isAtBottom.set(atBottom);

    if (atTop && this.hasMoreMessages() && !this.isLoadingMore()) {
      this.loadMoreMessages();
    }
  }

  scrollToBottom(smooth = true) {
    if (!this.messagesContainer) return;
    const el = this.messagesContainer.nativeElement;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
  }

  scrollToTop(smooth = true) {
    if (!this.messagesContainer) return;
    const el = this.messagesContainer.nativeElement;
    el.scrollTo({ top: 0, behavior: smooth ? 'smooth' : 'auto' });
  }

  isEditingName = signal(false);
  editingNameValue = signal('');
  nameHistory = signal<LeadNameHistory[]>([]);
  nameSaveError = signal<string | null>(null);

  startEditName() {
    const session = this.selectedSession();
    if (!session) return;
    this.editingNameValue.set(session.lead_profile_name || '');
    this.isEditingName.set(true);
    setTimeout(() => this.nameInputRef?.nativeElement.focus(), 0);
  }

  cancelEditName() {
    this.isEditingName.set(false);
    this.editingNameValue.set('');
  }

  saveName() {
    const sessionId = this.selectedSessionId();
    const newName = this.editingNameValue().trim();
    if (!sessionId) return;
    if (!newName) { this.cancelEditName(); return; }

    this.crmApi.updateLeadProfileName(sessionId, newName).subscribe({
      next: (res) => {
        this.selectedSession.update(s => s ? { ...s, lead_profile_name: res.lead_profile_name } : s);
        this.chats.update(chats => chats.map(c => 
          c.session_id === sessionId ? { ...c, lead_profile_name: res.lead_profile_name } : c
        ));
        this.nameHistory.set(res.name_history || []);
        this.isEditingName.set(false);
      },
      error: (err) => {
        console.error('Error al actualizar nombre del lead', err);
        this.nameSaveError.set(
          'No se pudo guardar el nuevo nombre. Verifica tu conexión e intenta de nuevo.'
        );
        setTimeout(() => this.nameSaveError.set(null), 5000);
      }
    });
  }

  loadNameHistory(sessionId: string) {
    this.crmApi.getLeadNameHistory(sessionId).subscribe({
      next: (res) => {
        this.nameHistory.set(res.name_history || []);
      },
      error: () => {}
    });
  }

  setFilter(filter: 'all' | 'active' | 'won' | 'lost' | 'abandoned') {
    this.chatFilter.set(filter);
  }

  getEmptyStateTitle(): string {
    const filter = this.chatFilter();
    if (filter === 'all') return 'Sin chats';
    if (filter === 'active') return 'Sin chats activos';
    if (filter === 'won') return 'Sin chats ganados';
    if (filter === 'lost') return 'Sin chats perdidos';
    if (filter === 'abandoned') return 'Sin chats abandonados';
    return 'Sin chats';
  }

  getEmptyStateSubtitle(): string {
    const filter = this.chatFilter();
    if (filter === 'all') return 'No hay conversaciones todavía.';
    if (filter === 'active') return 'No tienes conversaciones activas.';
    if (filter === 'won') return 'No tienes ventas cerradas.';
    if (filter === 'lost') return 'No tienes chats perdidos.';
    if (filter === 'abandoned') return 'No hay chats abandonados.';
    return '';
  }
}
