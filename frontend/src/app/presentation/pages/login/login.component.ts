import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { SessionService } from '../../../core/services/session.service';
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

  email = signal('');
  password = signal('');
  isLoading = signal(false);
  errorMessage = signal('');
  loginMode = signal<'google' | 'email'>('google');

  ngOnInit() {
    this.checkExistingSession();
    if (localStorage.getItem('session_expired')) {
      this.errorMessage.set('Tu sesión ha expirado. Vuelve a iniciar sesión.');
      localStorage.removeItem('session_expired');
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
    this.session.setToken(access_token);
    this.session.setUserId(user.email);
    this.session.setRole('sales');
    this.router.navigate(['/dashboard']);
  }

  async loginWithGoogle() {
    this.isLoading.set(true);
    this.errorMessage.set('');

    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: window.location.origin + '/dashboard'
      }
    });

    this.isLoading.set(false);
    if (error) {
      this.errorMessage.set('Error al iniciar sesión con Google');
    }
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

    const { error } = await supabase.auth.signInWithPassword({
      email,
      password
    });

    this.isLoading.set(false);
    if (error) {
      this.errorMessage.set(error.message);
    } else {
      const { data } = await supabase.auth.getSession();
      if (data.session) {
        this.handleSession(data.session);
      }
    }
  }

  toggleMode() {
    this.loginMode.set(this.loginMode() === 'google' ? 'email' : 'google');
    this.errorMessage.set('');
  }
}