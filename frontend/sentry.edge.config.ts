/**
 * Sentry Edge Runtime Configuration
 *
 * Initializes Sentry for edge functions (middleware).
 * Only enabled when SENTRY_DSN is set.
 */

import * as Sentry from '@sentry/nextjs';

const SENTRY_DSN = process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN;

if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,

    // Environment and release tracking
    environment: process.env.NODE_ENV,
    release: process.env.VERCEL_GIT_COMMIT_SHA,

    // Sampling for performance monitoring
    tracesSampleRate: process.env.NODE_ENV === 'production' ? 0.1 : 1.0,

    // Only send errors in production unless debug enabled
    enabled: process.env.NODE_ENV === 'production' || !!process.env.SENTRY_DEBUG,
  });
}
