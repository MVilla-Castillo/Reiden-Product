import { Component, inject } from '@angular/core';
import { RouterOutlet, Router, NavigationEnd } from '@angular/router';
import { SidebarComponent } from './presentation/components/layout/sidebar.component';
import { filter } from 'rxjs';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, SidebarComponent, CommonModule],
  template: `
    <div class="app-layout" [class.no-sidebar]="!showSidebar">
      @if (showSidebar) {
        <app-sidebar></app-sidebar>
      }
      <main class="main-content">
        <router-outlet></router-outlet>
      </main>
    </div>
  `,
  styles: [`
    .app-layout {
      display: flex;
      min-height: 100vh;
      background: #f3f4f6;
    }
    
    .main-content {
      flex: 1;
      margin-left: 260px;
      min-height: 100vh;
      transition: margin-left 0.3s ease;
    }

    .no-sidebar .main-content {
      margin-left: 0;
    }
  `]
})
export class AppComponent {
  title = 'CCRM';
  showSidebar = true;
  private router = inject(Router);

  constructor() {
    this.router.events.pipe(
      filter(event => event instanceof NavigationEnd)
    ).subscribe((event: any) => {
      this.showSidebar = !event.urlAfterRedirects.startsWith('/login');
    });
  }
}