import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Message {
  id: string;
  body: string;
  direction: 'INBOUND' | 'OUTBOUND';
  created_at: string;
}

export interface ChatSession {
  session_id: string;
  lead_id: string;
  status: string;
  messages: Message[];
}

@Injectable({ providedIn: 'root' })
export class ChatRepositoryService {
  private http = inject(HttpClient);
  private apiUrl = '/api/dashboard/leads';

  getMessages(sessionId: string, limit: number = 50, offset: number = 0): Observable<ChatSession> {
    return this.http.get<ChatSession>(`${this.apiUrl}/${sessionId}/messages/?limit=${limit}&offset=${offset}`);
  }

  sendMessage(sessionId: string, body: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/${sessionId}/messages/send/`, { body });
  }
}
