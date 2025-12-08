/**
 * Sentry Client-side Configuration
 *
 * Initializes Sentry in the browser for capturing client-side errors.
 * Only enabled when NEXT_PUBLIC_SENTRY_DSN is set.
 */

import * as Sentry from '@sentry/nextjs';

const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,

    // Environment and release tracking
    environment: process.env.NODE_ENV,
    release: process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA,

    // Sampling for performance monitoring
    tracesSampleRate: process.env.NODE_ENV === 'production' ? 0.1 : 1.0,

    // Session replay (optional, disabled by default)
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0,

    // Only send errors in production unless debug enabled
    enabled: process.env.NODE_ENV === 'production' || !!process.env.SENTRY_DEBUG,

    // Don't send errors from localhost
    beforeSend(event) {
      if (typeof window !== 'undefined') {
        const hostname = window.location.hostname;
        if (hostname === 'localhost' || hostname === '127.0.0.1') {
          return null;
        }
      }
      return event;
    },

    // Ignore common non-actionable errors
    ignoreErrors: [
      // Network errors
      'Network request failed',
      'Failed to fetch',
      'Load failed',
      // Browser extensions
      /^chrome-extension:\/\//,
      /^moz-extension:\/\//,
      // User-cancelled
      'AbortError',
    ],
  });
}
