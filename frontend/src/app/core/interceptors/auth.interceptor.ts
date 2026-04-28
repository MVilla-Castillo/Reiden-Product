import {
  HttpInterceptorFn,
  HttpErrorResponse,
  HttpRequest,
  HttpEventType,
  HttpResponse,
} from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError, switchMap, filter, take, tap } from 'rxjs';
import * as Sentry from '@sentry/angular';
import { SessionService } from '../services/session.service';

const SESSION_TRACE_ID = crypto.randomUUID();

function addAuth(req: HttpRequest<unknown>, token: string, userId: string) {
  return req.clone({
    headers: req.headers
      .set('Authorization', `Bearer ${token}`)
      .set('X-User-ID', userId)
      .set('X-Trace-ID', SESSION_TRACE_ID),
  });
}

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const token = localStorage.getItem('access_token');
  const userId = localStorage.getItem('user_id') ?? '';
  const session = inject(SessionService);

  const authReq = req.url.includes('/api/') && token
    ? addAuth(req, token, userId)
    : req;

  return next(authReq).pipe(
    tap(event => {
      if (event.type === HttpEventType.Response) {
        const backendTraceId = (event as HttpResponse<unknown>).headers.get('X-Trace-ID');
        if (backendTraceId) {
          (window as any).__lastTraceId__ = backendTraceId;
          Sentry.getCurrentScope().setTag('trace_id', backendTraceId);
        }
      }
    }),
    catchError((err: HttpErrorResponse) => {
      if (err.status === 401 && req.url.includes('/api/')) {
        session.markExpired();
        return session.tokenReady$.pipe(
          filter((t): t is string => t !== null),
          take(1),
          switchMap(newToken =>
            next(addAuth(req, newToken, localStorage.getItem('user_id') ?? ''))
          )
        );
      }
      if (err.status >= 500 || err.status === 0) {
        Sentry.withScope((scope) => {
          scope.setTag('http_status', String(err.status));
          scope.setTag('url', req.url);
          scope.setTag('method', req.method);
          const traceId = (window as any).__lastTraceId__;
          if (traceId) scope.setTag('trace_id', traceId);
          Sentry.captureException(new Error(`HTTP ${err.status} on ${req.method} ${req.url}`));
        });
      }
      return throwError(() => err);
    })
  );
};
