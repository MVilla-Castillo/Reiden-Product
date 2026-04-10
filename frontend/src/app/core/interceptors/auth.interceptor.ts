import { HttpInterceptorFn } from '@angular/common/http';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  // Extraemos el token del localStorage si existe.
  // En desarrollo, el backend tiene un bypass de Google Workspace,
  // por lo que enviamos un token falso (Bearer bypass) para pasar la validación estructural.
  const token = localStorage.getItem('access_token') || 'bypass_token';

  // Solo inyectamos token estructurado para todas las peticiones a la API del proyecto
  if (req.url.includes('/api/')) {
    const authReq = req.clone({
      headers: req.headers.set('Authorization', `Bearer ${token}`)
    });
    return next(authReq);
  }

  return next(req);
};
