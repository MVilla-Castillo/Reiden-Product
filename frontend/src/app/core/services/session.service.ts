import { Injectable, signal, computed } from '@angular/core';

export type UserRole = 'manager' | 'sales';

@Injectable({ providedIn: 'root' })
export class SessionService {
  private readonly _role = signal<UserRole>((localStorage.getItem('role') as UserRole) || 'manager');
  private readonly _token = signal<string | null>(localStorage.getItem('access_token'));
  private readonly _userId = signal<string | null>(localStorage.getItem('user_id'));

  readonly currentRole = computed(() => this._role());
  readonly token = computed(() => this._token());
  readonly userId = computed(() => this._userId());

  setRole(role: UserRole): void {
    localStorage.setItem('role', role);
    this._role.set(role);
  }

  setUserId(userId: string): void {
    localStorage.setItem('user_id', userId);
    this._userId.set(userId);
  }

  setToken(token: string): void {
    localStorage.setItem('access_token', token);
    this._token.set(token);
  }

  clear(): void {
    localStorage.removeItem('access_token');
    localStorage.removeItem('role');
    localStorage.removeItem('user_id');
    this._token.set(null);
  }
}