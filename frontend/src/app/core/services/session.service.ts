import { Injectable, signal, computed } from '@angular/core';

export type UserRole = 'manager' | 'sales';

@Injectable({ providedIn: 'root' })
export class SessionService {
  private readonly _role = signal<UserRole>((localStorage.getItem('role') as UserRole) || 'manager');
  private readonly _token = signal<string | null>(localStorage.getItem('access_token'));

  readonly currentRole = computed(() => this._role());
  readonly token = computed(() => this._token());

  setRole(role: UserRole): void {
    localStorage.setItem('role', role);
    this._role.set(role);
  }

  setToken(token: string): void {
    localStorage.setItem('access_token', token);
    this._token.set(token);
  }

  clear(): void {
    localStorage.removeItem('access_token');
    localStorage.removeItem('role');
    this._token.set(null);
  }
}