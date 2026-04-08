import { Injectable, signal, computed } from '@angular/core';

export type UserRole = 'manager' | 'sales';

@Injectable({ providedIn: 'root' })
export class SessionService {
  private readonly _role = signal<UserRole>('manager');
  private readonly _token = signal<string | null>('demo-token');
  private readonly _userId = signal<string>('user-001');

  readonly currentRole = computed(() => this._role());
  readonly token = computed(() => this._token());
  readonly userId = computed(() => this._userId());

  setRole(role: UserRole): void {
    this._role.set(role);
  }

  setToken(token: string): void {
    this._token.set(token);
  }

  isManager(): boolean {
    return this._role() === 'manager';
  }

  isSales(): boolean {
    return this._role() === 'sales';
  }
}