import { ErrorHandler, Injectable } from '@angular/core';
import * as Sentry from '@sentry/angular';

@Injectable()
export class GlobalErrorHandler implements ErrorHandler {
  handleError(error: unknown): void {
    const traceId = (window as any).__lastTraceId__;
    Sentry.withScope((scope) => {
      if (traceId) scope.setTag('trace_id', traceId);
      Sentry.captureException(error);
    });
    console.error('[Error]', error);
  }
}
