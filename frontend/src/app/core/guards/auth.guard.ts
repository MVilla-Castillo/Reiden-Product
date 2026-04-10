import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { SessionService } from '../services/session.service';

export const authGuard: CanActivateFn = (route, state) => {
  const session = inject(SessionService);
  const router = inject(Router);
  const roleRequired = route.data['role'] as string;

  if (!session.token()) {
    router.navigate(['/login']);
    return false;
  }

  if (roleRequired && session.currentRole() !== roleRequired) {
    if (session.currentRole() === 'manager') {
      router.navigate(['/dashboard']);
    } else {
      router.navigate(['/chat']);
    }
    return false;
  }

  return true;
};
