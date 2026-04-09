import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { SessionService } from '../services/session.service';

export const authGuard: CanActivateFn = (route, state) => {
  const session = inject(SessionService);
  const router = inject(Router);
  const roleRequired = route.data['role'] as string;

  if (!session.token()) {
    // In a real app, redirect to /login
    console.warn('No token found, redirecting to login...');
    return true; // For demo purposes we let them in
  }

  if (roleRequired && session.currentRole() !== roleRequired) {
    console.warn(`Role ${roleRequired} required. Redirecting...`);
    if (session.currentRole() === 'manager') {
      router.navigate(['/dashboard']);
    } else {
      router.navigate(['/chat']);
    }
    return false;
  }

  return true;
};
