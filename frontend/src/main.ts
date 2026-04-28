import * as Sentry from '@sentry/angular';
import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';

const sentryDsn = (window as any).__SENTRY_DSN__ ?? '';
if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    environment: 'production',
    tracesSampleRate: 0.1,
    ignoreErrors: ['ResizeObserver loop limit exceeded'],
  });
}

bootstrapApplication(AppComponent, appConfig).catch((err) => {
  Sentry.captureException(err);
  console.error(err);
});
