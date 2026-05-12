import { Component, Input, inject } from '@angular/core';
import { CommonModule } from '@angular/common';

import { GuideTab } from '../../../core/models/guides.models';
import { GuideTourService } from '../../../core/services/guide-tour.service';

@Component({
  selector: 'app-guide-button',
  standalone: true,
  imports: [CommonModule],
  template: `
    <button
      type="button"
      class="guide-btn"
      [attr.aria-label]="'Abrir guía de ' + tab"
      (click)="open()"
      [disabled]="tour.isLoading()"
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="10" />
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
      <span>Guía</span>
    </button>
  `,
  styles: [
    `
      :host {
        display: inline-flex;
      }

      .guide-btn {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.45rem 0.85rem;
        background: var(--color-primary, #3b82f6);
        color: #fff;
        border: none;
        border-radius: 999px;
        font-size: var(--font-sm, 0.875rem);
        font-weight: 600;
        font-family: inherit;
        cursor: pointer;
        transition: filter 0.15s ease, transform 0.15s ease;
        box-shadow: var(--shadow-card, 0 1px 2px rgba(0, 0, 0, 0.08));
      }

      .guide-btn:hover:not(:disabled) {
        filter: brightness(1.06);
      }

      .guide-btn:active:not(:disabled) {
        transform: translateY(1px);
      }

      .guide-btn:disabled {
        opacity: 0.6;
        cursor: progress;
      }

      .guide-btn svg {
        flex-shrink: 0;
      }
    `,
  ],
})
export class GuideButtonComponent {
  @Input({ required: true }) tab!: GuideTab;
  @Input() beforeStart?: () => void;

  protected readonly tour = inject(GuideTourService);

  open(): void {
    this.beforeStart?.();
    this.tour.start(this.tab);
  }
}
