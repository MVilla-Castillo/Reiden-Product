import { Injectable, signal, computed } from '@angular/core';
import { Subject } from 'rxjs';
import { supabase } from '../supabase';

export type UserRole = 'manager' | 'sales';

@Injectable({ providedIn: 'root' })
export class SessionService {
  private readonly _role = signal<UserRole>((localStorage.getItem('role') as UserRole) || 'sales');
  private readonly _token = signal<string | null>(localStorage.getItem('supabase_token'));
  private readonly _userId = signal<string | null>(localStorage.getItem('user_id'));

  readonly currentRole = computed(() => this._role());
  readonly token = computed(() => this._token());
  readonly userId = computed(() => this._userId());

  readonly sessionExpired$ = new Subject<void>();
  readonly tokenReady$ = new Subject<string | null>();

  private isExpiredState = false;

  get isExpired() { return this.isExpiredState; }

  constructor() {
    this.initAuthListener();
  }

  private initAuthListener() {
    supabase.auth.onAuthStateChange((event: string, session: { access_token: string } | null) => {
      if (event === 'SIGNED_OUT' || !session) {
        this.markExpired();
      } else if (event === 'TOKEN_REFRESHED' && session.access_token) {
        this.setToken(session.access_token);
      }
    });
  }

  setRole(role: UserRole): void {
    localStorage.setItem('role', role);
    this._role.set(role);
  }

  setUserId(userId: string): void {
    localStorage.setItem('user_id', userId);
    this._userId.set(userId);
  }

  setToken(token: string): void {
    localStorage.setItem('supabase_token', token);
    this._token.set(token);
  }

  markExpired(): void {
    if (this.isExpiredState) return;
    this.isExpiredState = true;
    localStorage.setItem('session_expired', 'true');
    localStorage.removeItem('supabase_token');
    localStorage.removeItem('role');
    localStorage.removeItem('user_id');
    this._token.set(null);
    this.sessionExpired$.next();
  }

  replayWithToken(token: string, role: UserRole, userId: string): void {
    this.isExpiredState = false;
    this.setRole(role);
    this.setUserId(userId);
    this.setToken(token);
    this.tokenReady$.next(token);
    this.tokenReady$.next(null);
  }

  clear(): void {
    localStorage.removeItem('supabase_token');
    localStorage.removeItem('role');
    localStorage.removeItem('user_id');
    this._token.set(null);
  }
}