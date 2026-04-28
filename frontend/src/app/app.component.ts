import { Component, inject, signal, OnInit, OnDestroy } from '@angular/core';
import { RouterOutlet, Router, NavigationEnd } from '@angular/router';
import { SidebarComponent } from './presentation/components/layout/sidebar.component';
import { filter, Subscription } from 'rxjs';
import { CommonModule } from '@angular/common';
import { SessionService } from './core/services/session.service';
import { supabase } from './core/supabase';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, SidebarComponent, CommonModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent implements OnInit, OnDestroy {
  title = 'Stelard';
  showSidebar = true;
  sessionExpiredVisible = signal(false);

  private router = inject(Router);
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