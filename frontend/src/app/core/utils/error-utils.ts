import { Observable, of } from 'rxjs';
import { HttpErrorResponse } from '@angular/common/http';
import * as Sentry from '@sentry/angular';

export function catchAndReport<T>(fallback: T) {
  return (err: unknown): Observable<T> => {
    if (err instanceof HttpErrorResponse && (err.status === 401 || err.status === 403)) {
      return of(fallback);
    }
    Sentry.captureException(err);
    return of(fallback);
  };
}
