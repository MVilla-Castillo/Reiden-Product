import { Injectable, NgZone } from '@angular/core';
import { Observable, from, switchMap } from 'rxjs';

export interface SseEvent {
  type: string;
  data: any;
}

@Injectable({ providedIn: 'root' })
export class SseService {
  private readonly baseUrl = 'http://localhost:8000/api';

  constructor(private ngZone: NgZone) {}

  // Pide al backend un ticket de un solo uso (TTL 30s) para autenticar el SSE
  // sin exponer el JWT real en la URL ni en los logs del servidor.
  private async fetchTicket(): Promise<string> {
    const token = localStorage.getItem('supabase_token');
    const userId = localStorage.getItem('user_id') ?? '';
    const res = await fetch(`${this.baseUrl}/sse/ticket/`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'X-User-ID': userId,
      },
    });
    if (!res.ok) throw new Error(`SSE ticket error: ${res.status}`);
    const { ticket } = await res.json();
    return ticket;
  }

  connect(path: string, eventNames: string[]): Observable<SseEvent> {
    return from(this.fetchTicket()).pipe(
      switchMap(ticket => new Observable<SseEvent>(observer => {
        const url = `${this.baseUrl}${path}?ticket=${encodeURIComponent(ticket)}`;
        const es = new EventSource(url);

        const makeHandler = (eventName: string) => (e: MessageEvent) => {
          this.ngZone.run(() => {
            try {
              observer.next({ type: eventName, data: JSON.parse(e.data) });
            } catch {
              observer.next({ type: eventName, data: e.data });
            }
          });
        };

        const handlers: Array<[string, EventListener]> = eventNames.map(name => [
          name,
          makeHandler(name) as EventListener,
        ]);

        for (const [name, handler] of handlers) {
          es.addEventListener(name, handler);
        }

        es.onopen = () => {
          this.ngZone.run(() => observer.next({ type: 'sse_connected', data: null }));
        };

        es.onerror = () => {
          this.ngZone.run(() => observer.next({ type: 'sse_reconnecting', data: null }));
        };

        return () => {
          for (const [name, handler] of handlers) {
            es.removeEventListener(name, handler);
          }
          es.close();
        };
      }))
    );
  }

  dashboardStream(): Observable<SseEvent> {
    return this.connect('/sse/dashboard/', ['snapshot', 'pending_leads', 'settings']);
  }

  messagesStream(sessionId: string): Observable<SseEvent> {
    return this.connect(`/sse/messages/${sessionId}/`, ['message', 'status_change']);
  }
}
