import { HttpInterceptorFn, HttpErrorResponse, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { SessionService } from '../services/session.service';
import { supabase } from '../supabase';

function addAuth(req: HttpRequest<unknown>, token: string, userId: string) {
  return req.clone({
    headers: req.headers
      .set('Authorization', `Bearer ${token}`)
      .set('apikey', 'supabase_anon_key')
      .set('X-User-ID', userId)
  });
}

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const token = localStorage.getItem('supabase_token');
  const userId = localStorage.getItem('user_id') ?? '';
  const session = inject(SessionService);

  const authReq = req.url.includes('/api/') && token
    ? addAuth(req, token, userId)
    : req;

  return next(authReq).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 401 && req.url.includes('/api/')) {
        supabase.auth.signOut().then(() => {
          session.markExpired();
        });
      }
      return throwError(() => err);
    })
  );
};
