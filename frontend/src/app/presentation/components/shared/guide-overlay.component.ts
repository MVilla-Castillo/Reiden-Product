import {
  Component,
  HostListener,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';

import { GuidePlacement } from '../../../core/models/guides.models';
import { GuideTourService } from '../../../core/services/guide-tour.service';

interface TargetRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

const HOLE_PADDING = 8;
const TOOLTIP_GAP = 14;
const TOOLTIP_WIDTH = 340;
const TOOLTIP_MIN_HEIGHT = 180;
const VIEWPORT_MARGIN = 16;

@Component({
  selector: 'app-guide-overlay',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './guide-overlay.component.html',
  styleUrls: ['./guide-overlay.component.scss'],
})
export class GuideOverlayComponent {
  protected readonly tour = inject(GuideTourService);

  protected readonly rect = signal<TargetRect | null>(null);
  protected readonly missingTarget = signal(false);
  protected readonly expanded = signal(false);

  protected readonly viewportWidth = signal<number>(
    typeof window !== 'undefined' ? window.innerWidth : 1024,
  );
  protected readonly viewportHeight = signal<number>(
    typeof window !== 'undefined' ? window.innerHeight : 768,
  );

  protected readonly holeStyle = computed(() => {
    const r = this.rect();
    if (!r) return null;
    return {
      x: r.x - HOLE_PADDING,
      y: r.y - HOLE_PADDING,
      width: r.width + HOLE_PADDING * 2,
      height: r.height + HOLE_PADDING * 2,
    };
  });

  protected readonly tooltipPos = computed(() => {
    const r = this.rect();
    const step = this.tour.currentStep();
    if (!r || !step) return null;

    const vw = this.viewportWidth();
    const vh = this.viewportHeight();
    const placement = step.placement;

    const positions: Record<GuidePlacement, { top: number; left: number }> = {
      bottom: { top: r.y + r.height + TOOLTIP_GAP, left: r.x + r.width / 2 - TOOLTIP_WIDTH / 2 },
      top: { top: r.y - TOOLTIP_GAP - TOOLTIP_MIN_HEIGHT, left: r.x + r.width / 2 - TOOLTIP_WIDTH / 2 },
      right: { top: r.y + r.height / 2 - TOOLTIP_MIN_HEIGHT / 2, left: r.x + r.width + TOOLTIP_GAP },
      left: { top: r.y + r.height / 2 - TOOLTIP_MIN_HEIGHT / 2, left: r.x - TOOLTIP_WIDTH - TOOLTIP_GAP },
    };

    let chosen = positions[placement] ?? positions['bottom'];
    let actualPlacement: GuidePlacement = placement;

    const fits = (p: { top: number; left: number }) =>
      p.left >= VIEWPORT_MARGIN &&
      p.left + TOOLTIP_WIDTH <= vw - VIEWPORT_MARGIN &&
      p.top >= VIEWPORT_MARGIN &&
      p.top + TOOLTIP_MIN_HEIGHT <= vh - VIEWPORT_MARGIN;

    if (!fits(chosen)) {
      const fallbackOrder: GuidePlacement[] = ['bottom', 'top', 'right', 'left'];
      for (const candidate of fallbackOrder) {
        if (candidate === placement) continue;
        const c = positions[candidate];
        if (fits(c)) {
          chosen = c;
          actualPlacement = candidate;
          break;
        }
      }
    }

    const clampedLeft = Math.max(
      VIEWPORT_MARGIN,
      Math.min(chosen.left, vw - TOOLTIP_WIDTH - VIEWPORT_MARGIN),
    );

    if (actualPlacement === 'top') {
      const bottomCss = Math.min(
        vh - (r.y - HOLE_PADDING - TOOLTIP_GAP),
        vh - VIEWPORT_MARGIN,
      );
      return { bottom: bottomCss, left: clampedLeft, placement: actualPlacement };
    }

    if (actualPlacement === 'bottom') {
      let clampedTop = Math.max(
        VIEWPORT_MARGIN,
        Math.min(chosen.top, vh - TOOLTIP_MIN_HEIGHT - VIEWPORT_MARGIN),
      );
      clampedTop = Math.max(clampedTop, r.y + r.height + HOLE_PADDING + TOOLTIP_GAP);
      return { top: clampedTop, left: clampedLeft, placement: actualPlacement };
    }

    const clampedTop = Math.max(
      VIEWPORT_MARGIN,
      Math.min(chosen.top, vh - TOOLTIP_MIN_HEIGHT - VIEWPORT_MARGIN),
    );

    return { top: clampedTop, left: clampedLeft, placement: actualPlacement };
  });

  constructor() {
    effect(() => {
      const step = this.tour.currentStep();
      const active = this.tour.isActive();
      if (!active || !step) {
        this.rect.set(null);
        this.missingTarget.set(false);
        return;
      }
      this.expanded.set(false);
      queueMicrotask(() => this.locateTarget(step.selector));
    }, { allowSignalWrites: true });
  }

  private locateTarget(selector: string): void {
    const el = document.querySelector(selector) as HTMLElement | null;
    if (!el) {
      this.rect.set(null);
      this.missingTarget.set(true);
      console.warn(`[GuideTour] Elemento no encontrado para selector: ${selector}`);
      return;
    }

    el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });

    requestAnimationFrame(() => {
      const b = el.getBoundingClientRect();
      this.rect.set({ x: b.left, y: b.top, width: b.width, height: b.height });
      this.missingTarget.set(false);
    });
  }

  protected toggleExpand(): void {
    this.expanded.update(v => !v);
  }

  protected onSkipMissing(): void {
    if (this.tour.index() < this.tour.total() - 1) {
      this.tour.next();
    } else {
      this.tour.close();
    }
  }

  protected onBackdropClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      this.tour.close();
    }
  }

  @HostListener('window:keydown.escape')
  protected onEscape(): void {
    if (this.tour.isActive()) {
      this.tour.close();
    }
  }

  @HostListener('window:resize')
  @HostListener('window:scroll')
  protected onViewportChange(): void {
    this.viewportWidth.set(window.innerWidth);
    this.viewportHeight.set(window.innerHeight);
    const step = this.tour.currentStep();
    if (step) {
      this.locateTarget(step.selector);
    }
  }
}
