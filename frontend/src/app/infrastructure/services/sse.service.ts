import { Injectable, NgZone } from '@angular/core';
import { Observable } from 'rxjs';

export interface SseEvent {
  type: string;
  data: any;
}

@Injectable({ providedIn: 'root' })
export class SseService {
  private readonly baseUrl = 'http://localhost:8000/api';

  constructor(private ngZone: NgZone) {}

  /**
   * Abre una conexión SSE y emite eventos como Observable<SseEvent>.
   * Se suscribe a los event names indicados (EventSource nombrado).
   * Al hacer unsubscribe() se cierra el EventSource automáticamente.
   */
  connect(path: string, eventNames: string[]): Observable<SseEvent> {
    return new Observable(observer => {
      const es = new EventSource(`${this.baseUrl}${path}`);

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
        // EventSource reconecta automáticamente (back-off nativo del browser).
        this.ngZone.run(() => observer.next({ type: 'sse_reconnecting', data: null }));
      };

      // Cleanup al hacer unsubscribe
      return () => {
        for (const [name, handler] of handlers) {
          es.removeEventListener(name, handler);
        }
        es.close();
      };
    });
  }

  dashboardStream(): Observable<SseEvent> {
    return this.connect('/sse/dashboard/', ['snapshot', 'pending_leads', 'settings']);
  }

  messagesStream(sessionId: string): Observable<SseEvent> {
    return this.connect(`/sse/messages/${sessionId}/`, ['message', 'status_change']);
  }
}
