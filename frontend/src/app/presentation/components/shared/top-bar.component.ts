import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-top-bar',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="top-bar">
      <div class="top-bar-left">
        @if (breadcrumb) {
          <nav class="breadcrumb" aria-label="Breadcrumb">
            <a routerLink="/">Inicio</a>
            <span class="breadcrumb-separator">/</span>
            <span class="breadcrumb-current">{{ breadcrumb }}</span>
          </nav>
        }
        <h1 class="page-title">{{ title }}</h1>
      </div>
      <div class="top-bar-right">
        <ng-content></ng-content>
      </div>
    </div>
  `,
  styles: [`
    :host {
      display: block;
    }

    .top-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 1rem 2rem;
      background: var(--color-surface);
      border-bottom: 1px solid var(--color-border);
      position: sticky;
      top: 0;
      z-index: 50;
    }

    .top-bar-left {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }

    .breadcrumb {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-size: var(--font-xs);
      color: var(--color-muted);
    }

    .breadcrumb a {
      color: var(--color-muted);
      text-decoration: none;
      transition: color 0.15s;
    }

    .breadcrumb a:hover {
      color: var(--color-primary);
    }

    .breadcrumb-separator {
      color: var(--color-border);
    }

    .breadcrumb-current {
      color: var(--color-text);
    }

    .page-title {
      font-size: var(--font-xl);
      font-weight: 600;
      color: #111827;
      margin: 0;
      line-height: 1.2;
    }

    .top-bar-right {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
  `]
})
export class TopBarComponent {
  @Input() title = '';
  @Input() breadcrumb?: string;
}