import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { SessionService, UserRole } from '../../../core/services/session.service';
import { supabase } from '../../../core/supabase';

interface AuthSession {
  access_token: string;
  user: { id: string; email: string };
}

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss'
})
export class LoginComponent implements OnInit {
  private session = inject(SessionService);
  private router = inject(Router);
  private http = inject(HttpClient);

  email = signal('');
  password = signal('');
  isLoading = signal(false);
  errorMessage = signal('');
  loginMode = signal<'google' | 'email'>('google');

  ngOnInit() {
    // Limpiar residuos de sesiones anteriores fallidas antes de cualquier chequeo
    localStorage.removeItem('session_expired');
    if (this.handleOAuthCallback()) return;
    this.checkExistingSession();
  }

  private handleOAuthCallback(): boolean {
    const hash = window.location.hash;
    if (!hash || !hash.includes('access_token')) return false;
    const params = new URLSearchParams(hash.substring(1));
    const accessToken = params.get('access_token');
    if (!accessToken) return false;
    history.replaceState(null, '', window.location.pathname);
    this.isLoading.set(true);
    this.verifyAndLogin(accessToken);
    return true;
  }

  private readonly apiBase = 'http://localhost:8000/api';

  private async verifyAndLogin(accessToken: string) {
    const email = this.extractEmailFromJwt(accessToken);
    const headers = new HttpHeaders()
      .set('Authorization', `Bearer ${accessToken}`)
      .set('X-User-ID', email);

    try {
      // Obtener el rol real del usuario desde el backend
      const me = await firstValueFrom(
        this.http.get<{ email: string; role: string }>(`${this.apiBase}/dashboard/me/`, { headers })
      );

      const role = this.mapRole(me.role);
      this.session.setToken(accessToken);
      this.session.setUserId(email);
      this.session.setRole(role);
      this.isLoading.set(false);
      this.router.navigate([role === 'manager' ? '/dashboard' : '/leads']);
    } catch (err: any) {
      this.isLoading.set(false);
      if (err.status === 403) {
        this.errorMessage.set(`El correo ${email} no tiene acceso a este sistema. Contacta al administrador.`);
      } else {
        this.errorMessage.set('Error al verificar el acceso. Intenta de nuevo.');
      }
      this.session.clear();
    }
  }

  // 'manager'|'admin' → 'manager' frontend   /   'salesperson' → 'sales' frontend
  private mapRole(backendRole: string): UserRole {
    return backendRole === 'salesperson' ? 'sales' : 'manager';
  }

  private extractEmailFromJwt(token: string): string {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      return payload.email || payload.sub || '';
    } catch {
      return '';
    }
  }

  private checkExistingSession() {
    supabase.auth.getSession().then(({ data }: { data: { session: AuthSession | null } }) => {
      if (data.session) {
        this.handleSession(data.session);
      }
    });
  }

  private handleSession(authSession: AuthSession) {
    const { access_token, user } = authSession;
    const email = user.email;
    const headers = new HttpHeaders()
      .set('Authorization', `Bearer ${access_token}`)
      .set('X-User-ID', email);

    firstValueFrom(
      this.http.get<{ email: string; role: string }>(`${this.apiBase}/dashboard/me/`, { headers })
    ).then(me => {
      const role = this.mapRole(me.role);
      this.session.setToken(access_token);
      this.session.setUserId(email);
      this.session.setRole(role);
      this.router.navigate([role === 'manager' ? '/dashboard' : '/leads']);
    }).catch(() => {
      this.session.clear();
    });
  }

  async loginWithGoogle() {
    this.isLoading.set(true);
    this.errorMessage.set('');
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin + '/login' }
    });
    this.isLoading.set(false);
    if (error) this.errorMessage.set('Error al iniciar sesión con Google');
  }

  async loginWithEmail() {
    const email = this.email();
    const password = this.password();
    if (!email || !password) {
      this.errorMessage.set('Email y contraseña son requeridos.');
      return;
    }
    this.isLoading.set(true);
    this.errorMessage.set('');
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    this.isLoading.set(false);
    if (error) {
      this.errorMessage.set(error.message);
    } else {
      const { data } = await supabase.auth.getSession();
      if (data.session) this.handleSession(data.session);
    }
  }

  toggleMode() {
    this.loginMode.set(this.loginMode() === 'google' ? 'email' : 'google');
    this.errorMessage.set('');
  }
}
