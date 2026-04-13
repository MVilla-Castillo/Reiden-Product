import { HttpInterceptorFn } from '@angular/common/http';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const token = localStorage.getItem('access_token') || 'bypass_token';
  const userId = localStorage.getItem('user_id');

  if (req.url.includes('/api/')) {
    const authReq = req.clone({
      headers: req.headers
        .set('Authorization', `Bearer ${token}`)
        .set('X-User-ID', userId || '')
    });
    return next(authReq);
  }

  return next(req);
};
