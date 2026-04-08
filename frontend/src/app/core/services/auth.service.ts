import { Injectable, signal, computed } from '@angular/core';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { tap } from 'rxjs/operators';

export interface User {
  id: string;
  email: string;
  name: string;
  role: 'manager' | 'agent';
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly TOKEN_KEY = 'ccrm_token';
  private readonly USER_KEY = 'ccrm_user';

  private userSignal = signal<User | null>(this.loadUser());
  private isAuthenticatedSignal = signal<boolean>(this.hasValidToken());

  user = computed(() => this.userSignal());
  isAuthenticated = computed(() => this.isAuthenticatedSignal());

  constructor(
    private http: HttpClient,
    private router: Router
  ) {}

  private loadUser(): User | null {
    const stored = localStorage.getItem(this.USER_KEY);
    return stored ? JSON.parse(stored) : null;
  }

  private hasValidToken(): boolean {
    const token = localStorage.getItem(this.TOKEN_KEY);
    return !!token;
  }

  getToken(): string | null {
    return localStorage.getItem(this.TOKEN_KEY);
  }

  loginWithGoogle(): void {
    const oauthUrl = `${environment.apiUrl}/oauth/google/`;
    window.location.href = oauthUrl;
  }

  loginAsManager(): void {
    this.http.get<{ token: string; user: User }>(
      `${environment.apiUrl}/auth/dev/login/manager/`
    ).pipe(
      tap(response => {
        this.setSession(response.token, response.user);
      })
    ).subscribe({
      next: () => this.router.navigate(['/dashboard']),
      error: (err) => console.error('Dev login failed', err)
    });
  }

  loginAsSalesperson(): void {
    this.http.get<{ token: string; user: User }>(
      `${environment.apiUrl}/auth/dev/login/salesperson/`
    ).pipe(
      tap(response => {
        this.setSession(response.token, response.user);
      })
    ).subscribe({
      next: () => this.router.navigate(['/vendedor']),
      error: (err) => console.error('Dev login failed', err)
    });
  }

  handleOAuthCallback(code: string): void {
    this.http.post<{ token: string; user: User }>(
      `${environment.apiUrl}/oauth/google/callback/`,
      { code }
    ).pipe(
      tap(response => {
        this.setSession(response.token, response.user);
      })
    ).subscribe({
      next: () => this.router.navigate(['/dashboard']),
      error: (err) => console.error('OAuth callback failed', err)
    });
  }

  private setSession(token: string, user: User): void {
    localStorage.setItem(this.TOKEN_KEY, token);
    localStorage.setItem(this.USER_KEY, JSON.stringify(user));
    this.userSignal.set(user);
    this.isAuthenticatedSignal.set(true);
  }

  logout(): void {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);
    this.userSignal.set(null);
    this.isAuthenticatedSignal.set(false);
    this.router.navigate(['/login']);
  }

  hasRole(role: 'manager' | 'agent'): boolean {
    const user = this.userSignal();
    return user?.role === role;
  }
}
