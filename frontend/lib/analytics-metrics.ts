/**
 * Analytics Capture Metrics
 *
 * Shared in-memory metrics for observability.
 * Used by capture endpoint and admin overview.
 */

export interface CaptureMetrics {
  errorCount: number;
  lastError: string;
  lastErrorAt: number;
  eventsIngested24h: number;
  lastCountReset: number;
}

const EVENT_COUNT_RESET_INTERVAL = 86400000; // 24 hours

// Singleton metrics store
const metrics: CaptureMetrics = {
  errorCount: 0,
  lastError: '',
  lastErrorAt: 0,
  eventsIngested24h: 0,
  lastCountReset: Date.now(),
};

/**
 * Track a capture error
 */
export function trackCaptureError(error: string): void {
  metrics.errorCount++;
  metrics.lastError = error.slice(0, 200);
  metrics.lastErrorAt = Date.now();
}

/**
 * Track successful event ingestion
 */
export function trackEventIngested(): void {
  const now = Date.now();
  if (now - metrics.lastCountReset > EVENT_COUNT_RESET_INTERVAL) {
    metrics.eventsIngested24h = 0;
    metrics.errorCount = 0;
    metrics.lastCountReset = now;
  }
  metrics.eventsIngested24h++;
}

/**
 * Get current capture metrics for admin display
 */
export function getCaptureMetrics(): {
  error_count: number;
  last_error: string;
  last_error_at: number;
  events_24h: number;
  error_rate_pct: number;
} {
  const total = metrics.eventsIngested24h + metrics.errorCount;
  const errorRate = total > 0 ? (metrics.errorCount / total) * 100 : 0;

  return {
    error_count: metrics.errorCount,
    last_error: metrics.lastError,
    last_error_at: metrics.lastErrorAt,
    events_24h: metrics.eventsIngested24h,
    error_rate_pct: Math.round(errorRate * 100) / 100,
  };
}

/**
 * Reset metrics (for testing)
 */
export function resetCaptureMetrics(): void {
  metrics.errorCount = 0;
  metrics.lastError = '';
  metrics.lastErrorAt = 0;
  metrics.eventsIngested24h = 0;
  metrics.lastCountReset = Date.now();
}
