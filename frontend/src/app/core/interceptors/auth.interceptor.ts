import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { SessionService } from '../services/session.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const token = localStorage.getItem('access_token');
  const userId = localStorage.getItem('user_id');
  const router = inject(Router);
  const session = inject(SessionService);

  const authReq = req.url.includes('/api/') && token
    ? req.clone({
        headers: req.headers
          .set('Authorization', `Bearer ${token}`)
          .set('X-User-ID', userId || '')
      })
    : req;

  return next(authReq).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 401) {
        session.clear();
        localStorage.setItem('session_expired', '1');
        router.navigate(['/login']);
      }
      return throwError(() => err);
    })
  );
};
