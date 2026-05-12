import { Injectable, computed, inject, signal } from '@angular/core';
import { catchError, of, take } from 'rxjs';

import { GuideStep, GuideTab } from '../models/guides.models';
import { GuidesApiService } from '../../infrastructure/repositories/guides.api.service';

@Injectable({ providedIn: 'root' })
export class GuideTourService {
  private readonly api = inject(GuidesApiService);

  private readonly _isActive = signal(false);
  private readonly _isLoading = signal(false);
  private readonly _error = signal<string | null>(null);
  private readonly _title = signal<string>('');
  private readonly _steps = signal<GuideStep[]>([]);
  private readonly _index = signal(0);

  readonly isActive = this._isActive.asReadonly();
  readonly isLoading = this._isLoading.asReadonly();
  readonly error = this._error.asReadonly();
  readonly title = this._title.asReadonly();
  readonly steps = this._steps.asReadonly();
  readonly index = this._index.asReadonly();
  readonly total = computed(() => this._steps().length);
  readonly currentStep = computed<GuideStep | null>(() => {
    const list = this._steps();
    const i = this._index();
    return list[i] ?? null;
  });

  start(tab: GuideTab): void {
    this._isLoading.set(true);
    this._error.set(null);
    this._index.set(0);
    this._isActive.set(true);
    this.api
      .getGuide(tab)
      .pipe(
        take(1),
        catchError(err => {
          const status = err?.status;
          const msg =
            status === 403
              ? 'Esta guía no está disponible para tu rol.'
              : 'No se pudo cargar la guía. Intenta nuevamente.';
          this._error.set(msg);
          this._steps.set([]);
          this._title.set('');
          return of(null);
        }),
      )
      .subscribe(response => {
        this._isLoading.set(false);
        if (!response) {
          return;
        }
        this._title.set(response.title);
        this._steps.set(response.steps ?? []);
        if ((response.steps?.length ?? 0) === 0) {
          this._error.set('Esta guía aún no tiene pasos configurados.');
        }
      });
  }

  next(): void {
    const i = this._index();
    if (i < this._steps().length - 1) {
      this._index.set(i + 1);
    } else {
      this.close();
    }
  }

  prev(): void {
    const i = this._index();
    if (i > 0) {
      this._index.set(i - 1);
    }
  }

  goTo(index: number): void {
    if (index >= 0 && index < this._steps().length) {
      this._index.set(index);
    }
  }

  close(): void {
    this._isActive.set(false);
    this._steps.set([]);
    this._title.set('');
    this._index.set(0);
    this._error.set(null);
    this._isLoading.set(false);
  }
}
