import { Component, inject, signal, OnInit, OnDestroy } from '@angular/core';
import { RouterOutlet, Router, NavigationEnd } from '@angular/router';
import { SidebarComponent } from './presentation/components/layout/sidebar.component';
import { GuideOverlayComponent } from './presentation/components/shared/guide-overlay.component';
import { filter, Subscription } from 'rxjs';
import { CommonModule } from '@angular/common';
import { SessionService } from './core/services/session.service';
import { supabase } from './core/supabase';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, SidebarComponent, GuideOverlayComponent, CommonModule],
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
  private navSub?: Subscription;

  constructor() {
    this.showSidebar = !this.shouldHideSidebar(this.router.url);
    this.navSub = this.router.events.pipe(
      filter(event => event instanceof NavigationEnd)
    ).subscribe((event: any) => {
      this.showSidebar = !this.shouldHideSidebar(event.urlAfterRedirects);
    });
  }

  ngOnInit() {
    this.expiredSub = this.session.sessionExpired$.subscribe(() => {
      this.sessionExpiredVisible.set(true);
    });
  }

  ngOnDestroy() {
    this.expiredSub?.unsubscribe();
    this.navSub?.unsubscribe();
  }

  private shouldHideSidebar(url: string): boolean {
    const cleanUrl = url.split('?')[0];
    return cleanUrl === '/'
      || cleanUrl.startsWith('/login')
      || cleanUrl.startsWith('/terminos-y-condiciones')
      || cleanUrl.startsWith('/politica-de-privacidad')
      || cleanUrl.startsWith('/contacto');
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
