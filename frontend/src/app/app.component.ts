import { Component, inject, signal, OnInit, OnDestroy } from '@angular/core';
import { RouterOutlet, Router, NavigationEnd } from '@angular/router';
import { SidebarComponent } from './presentation/components/layout/sidebar.component';
import { filter, Subscription } from 'rxjs';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SessionService } from './core/services/session.service';
import { supabase } from './core/supabase';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, SidebarComponent, CommonModule, FormsModule],
  template: `
    <div class="app-layout" [class.no-sidebar]="!showSidebar">
      @if (showSidebar) {
        <app-sidebar></app-sidebar>
      }
      <main class="main-content">
        <router-outlet></router-outlet>
      </main>
    </div>

    @if (sessionExpiredVisible()) {
      <div class="session-overlay">
        <div class="session-modal">
          <div class="session-modal-icon">🔒</div>
          <h3>Sesión expirada</h3>
          <p>Tu sesión ha caducado. Vuelve a iniciar sesión para continuar donde estabas.</p>
          <button class="btn-reauth" (click)="reAuthenticate()">Iniciar sesión</button>
        </div>
      </div>
    }
  `,
  styles: [`
    .app-layout {
      display: flex;
      min-height: 100vh;
      background: #f3f4f6;
    }
    .main-content {
      flex: 1;
      margin-left: 220px;
      min-height: 100vh;
      transition: margin-left 0.3s ease;
    }
    .no-sidebar .main-content { margin-left: 0; }

    .session-overlay {
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.55);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 9999;
      backdrop-filter: blur(2px);
    }
    .session-modal {
      background: white;
      border-radius: 16px;
      padding: 2rem 2.5rem;
      max-width: 360px;
      width: 90%;
      text-align: center;
      box-shadow: 0 25px 50px rgba(0,0,0,0.2);
      animation: popIn 0.2s cubic-bezier(0.16,1,0.3,1);
    }
    .session-modal-icon { font-size: 2.5rem; margin-bottom: 0.75rem; }
    .session-modal h3 { margin: 0 0 0.5rem; font-size: 1.125rem; color: #111827; }
    .session-modal p  { color: #6b7280; font-size: 0.875rem; margin-bottom: 1rem; line-height: 1.5; }
    .btn-reauth {
      padding: 0.75rem 2rem;
      background: #4f46e5;
      color: white;
      border: none;
      border-radius: 8px;
      font-weight: 600;
      cursor: pointer;
      font-size: 0.875rem;
      width: 100%;
      transition: background 0.15s;
      &:hover { background: #4338ca; }
    }
    @keyframes popIn {
      from { transform: scale(0.9); opacity: 0; }
      to   { transform: scale(1);   opacity: 1; }
    }
  `]
})
export class AppComponent implements OnInit, OnDestroy {
  title = 'Stelard';
  showSidebar = true;
  sessionExpiredVisible = signal(false);
  reauthUserId = 'admin@dev.local';

  private router  = inject(Router);
  private session = inject(SessionService);
  private expiredSub?: Subscription;

  constructor() {
    this.router.events.pipe(
      filter(event => event instanceof NavigationEnd)
    ).subscribe((event: any) => {
      this.showSidebar = !event.urlAfterRedirects.startsWith('/login');
    });
  }

  ngOnInit() {
    this.expiredSub = this.session.sessionExpired$.subscribe(() => {
      this.sessionExpiredVisible.set(true);
    });
  }

  ngOnDestroy() {
    this.expiredSub?.unsubscribe();
  }

  async reAuthenticate() {
    this.sessionExpiredVisible.set(false);
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: window.location.origin + '/dashboard'
      }
    });
  }
}
      <main class="main-content">
        <router-outlet></router-outlet>
      </main>
    </div>

    @if (sessionExpiredVisible()) {
      <div class="session-overlay">
        <div class="session-modal">
          <div class="session-modal-icon">🔒</div>
          <h3>Sesión expirada</h3>
          <p>Tu sesión ha caducado. Vuelve a iniciar sesión para continuar donde estabas.</p>
          <select [(ngModel)]="reauthUserId" class="reauth-select">
            <option value="admin@dev.local">Gerencia (admin&#64;dev.local)</option>
            <option value="vendedor1@dev.local">Vendedor 1</option>
            <option value="vendedor2@dev.local">Vendedor 2</option>
          </select>
          <button class="btn-reauth" (click)="reAuthenticate()">Continuar sesión</button>
        </div>
      </div>
    }
  `,
  styles: [`
    .app-layout {
      display: flex;
      min-height: 100vh;
      background: #f3f4f6;
    }
    .main-content {
      flex: 1;
      margin-left: 220px;
      min-height: 100vh;
      transition: margin-left 0.3s ease;
    }
    .no-sidebar .main-content { margin-left: 0; }

    .session-overlay {
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.55);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 9999;
      backdrop-filter: blur(2px);
    }
    .session-modal {
      background: white;
      border-radius: 16px;
      padding: 2rem 2.5rem;
      max-width: 360px;
      width: 90%;
      text-align: center;
      box-shadow: 0 25px 50px rgba(0,0,0,0.2);
      animation: popIn 0.2s cubic-bezier(0.16,1,0.3,1);
    }
    .session-modal-icon { font-size: 2.5rem; margin-bottom: 0.75rem; }
    .session-modal h3 { margin: 0 0 0.5rem; font-size: 1.125rem; color: #111827; }
    .session-modal p  { color: #6b7280; font-size: 0.875rem; margin-bottom: 1rem; line-height: 1.5; }
    .reauth-select {
      width: 100%;
      padding: 0.625rem 0.75rem;
      border: 1px solid #d1d5db;
      border-radius: 8px;
      font-size: 0.875rem;
      margin-bottom: 1rem;
      outline: none;
      &:focus { border-color: #4f46e5; }
    }
    .btn-reauth {
      padding: 0.75rem 2rem;
      background: #4f46e5;
      color: white;
      border: none;
      border-radius: 8px;
      font-weight: 600;
      cursor: pointer;
      font-size: 0.875rem;
      width: 100%;
      transition: background 0.15s;
      &:hover { background: #4338ca; }
    }
    @keyframes popIn {
      from { transform: scale(0.9); opacity: 0; }
      to   { transform: scale(1);   opacity: 1; }
    }
  `]
})
export class AppComponent implements OnInit, OnDestroy {
  title = 'Stelard';
  showSidebar = true;
  sessionExpiredVisible = signal(false);
  reauthUserId = 'admin@dev.local';

  private router  = inject(Router);
  private session = inject(SessionService);
  private expiredSub?: Subscription;

  constructor() {
    this.router.events.pipe(
      filter(event => event instanceof NavigationEnd)
    ).subscribe((event: any) => {
      this.showSidebar = !event.urlAfterRedirects.startsWith('/login');
    });
  }

  ngOnInit() {
    this.expiredSub = this.session.sessionExpired$.subscribe(() => {
      this.reauthUserId = localStorage.getItem('user_id') || 'admin@dev.local';
      this.sessionExpiredVisible.set(true);
    });
  }

  ngOnDestroy() {
    this.expiredSub?.unsubscribe();
  }

  reAuthenticate() {
    const isManager = this.reauthUserId === 'admin@dev.local';
    const role: UserRole = isManager ? 'manager' : 'sales';
    this.session.replayWithToken('simulated-oidc-token', role, this.reauthUserId);
    this.sessionExpiredVisible.set(false);
  }
}