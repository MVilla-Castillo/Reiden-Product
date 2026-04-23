import { HttpInterceptorFn, HttpErrorResponse, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError, switchMap, filter, take } from 'rxjs';
import { SessionService } from '../services/session.service';

function addAuth(req: HttpRequest<unknown>, token: string, userId: string) {
  return req.clone({
    headers: req.headers
      .set('Authorization', `Bearer ${token}`)
      .set('X-User-ID', userId)
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
    catchError((err: HttpErrorResponse) => {
      if (err.status === 401 && req.url.includes('/api/')) {
        session.markExpired();
        // Wait for re-auth, then replay the original request once
        return session.tokenReady$.pipe(
          filter((t): t is string => t !== null),
          take(1),
          switchMap(newToken => {
            const retried = addAuth(req, newToken, localStorage.getItem('user_id') ?? '');
            return next(retried);
          })
        );
      }
      return throwError(() => err);
    })
  );
};
