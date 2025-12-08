/**
 * TellyAds Analytics Client
 *
 * Lightweight, GDPR-conscious event tracking for internal decision dashboards.
 * - Uses sendBeacon for reliable page-unload events
 * - Falls back to fetch for interactive events
 * - No PII collected; session rotates daily
 * - UA hash for unique visitor estimation (not fingerprinting)
 */

import { getSessionId } from './session';

// ============================================================================
// Event Taxonomy
// ============================================================================

/**
 * Event taxonomy for TellyAds analytics
 *
 * Naming convention: {domain}.{action}
 * - page.*     - Page navigation events
 * - search.*   - Search-related events
 * - advert.*   - Ad engagement events
 * - admin.*    - Admin actions (gated)
 */
export type AnalyticsEvent =
  // Page events
  | 'page.view'
  | 'page.scroll_depth'       // { depth: 25|50|75|100 }
  | 'page.exit'

  // Search events
  | 'search.performed'        // { query, results_count, latency_ms }
  | 'search.result_click'     // { query, ad_id, position, results_count }
  | 'search.zero_results'     // { query }
  | 'search.filter_applied'   // { filter_type, filter_value }

  // Advert engagement events
  | 'advert.view'             // { ad_id, brand, source }
  | 'advert.play'             // { ad_id, brand }
  | 'advert.pause'            // { ad_id, brand, watch_time_seconds }
  | 'advert.complete'         // { ad_id, brand, duration_seconds }
  | 'advert.like'             // { ad_id, brand, action: 'add'|'remove' }
  | 'advert.save'             // { ad_id, brand, action: 'add'|'remove' }
  | 'advert.share'            // { ad_id, brand, method }
  | 'advert.similar_click'    // { ad_id, clicked_ad_id, position }

  // Browse events
  | 'browse.era_click'        // { decade }
  | 'browse.brand_click'      // { brand }
  | 'browse.random_click'

  // Outbound
  | 'outbound.click'          // { url, context }

  // Error tracking
  | 'error.api'               // { endpoint, status, message }
  | 'error.client';           // { message, stack }

// ============================================================================
// Event Properties
// ============================================================================

export interface AnalyticsEventProps {
  // Search events
  query?: string;
  results_count?: number;
  latency_ms?: number;
  position?: number;
  filter_type?: string;
  filter_value?: string;

  // Advert events
  ad_id?: string;
  brand?: string;
  source?: 'search' | 'browse' | 'similar' | 'direct' | 'share';
  watch_time_seconds?: number;
  duration_seconds?: number;
  action?: 'add' | 'remove';
  method?: 'copy_link' | 'twitter' | 'facebook' | 'email';
  clicked_ad_id?: string;

  // Browse events
  decade?: string;

  // Page events
  depth?: 25 | 50 | 75 | 100;

  // Outbound
  url?: string;
  context?: string;

  // Error events
  endpoint?: string;
  status?: number;
  message?: string;
  stack?: string;

  // Generic extension
  [key: string]: unknown;
}

// ============================================================================
// Analytics Payload
// ============================================================================

interface AnalyticsPayload {
  event: AnalyticsEvent;
  path: string;
  referrer: string;
  session_id: string;
  props: AnalyticsEventProps;
  ua_hash: string;
  ts: string;
}

// ============================================================================
// UA Hash (privacy-safe device approximation)
// ============================================================================

let cachedUaHash: string | null = null;

/**
 * Generate privacy-safe hash for unique visitor estimation.
 * Based on: user agent + screen bucket (coarse) + timezone
 * NOT fingerprinting - intentionally coarse to preserve privacy
 */
async function getUaHash(): Promise<string> {
  if (cachedUaHash) return cachedUaHash;
  if (typeof window === 'undefined') return 'server';

  // Coarse screen bucket (e.g., "small", "medium", "large")
  const screenBucket = window.innerWidth < 768 ? 'small' :
                       window.innerWidth < 1280 ? 'medium' : 'large';

  // Combine with UA and timezone
  const data = [
    navigator.userAgent,
    screenBucket,
    Intl.DateTimeFormat().resolvedOptions().timeZone || 'unknown'
  ].join('|');

  // Hash with SHA-256
  const encoder = new TextEncoder();
  const hashBuffer = await crypto.subtle.digest('SHA-256', encoder.encode(data));
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  cachedUaHash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');

  return cachedUaHash;
}

// ============================================================================
// Daily Session (rotates at midnight)
// ============================================================================

const DAILY_SESSION_KEY = 'tellyads_daily_session';

function getDailySessionId(): string {
  if (typeof window === 'undefined') return 'server';

  const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
  const stored = localStorage.getItem(DAILY_SESSION_KEY);

  if (stored) {
    const [date, id] = stored.split(':');
    if (date === today) return id;
  }

  // Generate new daily session
  const newId = crypto.randomUUID();
  localStorage.setItem(DAILY_SESSION_KEY, `${today}:${newId}`);
  return newId;
}

// ============================================================================
// Track Function
// ============================================================================

const CAPTURE_ENDPOINT = '/api/analytics/capture';

/**
 * Track an analytics event
 *
 * @param event - Event type from taxonomy
 * @param props - Event-specific properties
 * @param options - { beacon: true } for page-unload events
 */
export async function track(
  event: AnalyticsEvent,
  props: AnalyticsEventProps = {},
  options: { beacon?: boolean } = {}
): Promise<void> {
  // Skip in development unless explicitly enabled
  if (process.env.NODE_ENV === 'development' && !process.env.NEXT_PUBLIC_ANALYTICS_DEV) {
    console.debug('[Analytics]', event, props);
    return;
  }

  // Skip server-side
  if (typeof window === 'undefined') return;

  try {
    const payload: AnalyticsPayload = {
      event,
      path: window.location.pathname,
      referrer: document.referrer ? new URL(document.referrer).pathname : '',
      session_id: getDailySessionId(),
      props,
      ua_hash: await getUaHash(),
      ts: new Date().toISOString(),
    };

    // Use sendBeacon for page-unload events (more reliable)
    if (options.beacon && navigator.sendBeacon) {
      navigator.sendBeacon(CAPTURE_ENDPOINT, JSON.stringify(payload));
      return;
    }

    // Use fetch for interactive events
    fetch(CAPTURE_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      // Don't wait for response
      keepalive: true,
    }).catch(() => {
      // Silently fail - analytics should never break user experience
    });
  } catch {
    // Silently fail
  }
}

// ============================================================================
// Convenience Functions
// ============================================================================

/**
 * Track page view (call on route change)
 */
export function trackPageView(): void {
  track('page.view');
}

/**
 * Track search performed
 */
export function trackSearch(query: string, resultsCount: number, latencyMs?: number): void {
  track('search.performed', {
    query: query.slice(0, 200), // Truncate long queries
    results_count: resultsCount,
    latency_ms: latencyMs,
  });

  if (resultsCount === 0) {
    track('search.zero_results', { query: query.slice(0, 200) });
  }
}

/**
 * Track search result click
 */
export function trackSearchClick(query: string, adId: string, position: number, resultsCount: number): void {
  track('search.result_click', {
    query: query.slice(0, 200),
    ad_id: adId,
    position,
    results_count: resultsCount,
  });
}

/**
 * Track ad view
 */
export function trackAdView(adId: string, brand: string, source: AnalyticsEventProps['source']): void {
  track('advert.view', { ad_id: adId, brand, source });
}

/**
 * Track ad play
 */
export function trackAdPlay(adId: string, brand: string): void {
  track('advert.play', { ad_id: adId, brand });
}

/**
 * Track ad complete
 */
export function trackAdComplete(adId: string, brand: string, durationSeconds: number): void {
  track('advert.complete', { ad_id: adId, brand, duration_seconds: durationSeconds });
}

/**
 * Track ad engagement (like/save)
 */
export function trackAdEngagement(
  type: 'like' | 'save',
  adId: string,
  brand: string,
  action: 'add' | 'remove'
): void {
  track(type === 'like' ? 'advert.like' : 'advert.save', {
    ad_id: adId,
    brand,
    action,
  });
}

/**
 * Track page exit (use with beforeunload)
 */
export function trackPageExit(): void {
  track('page.exit', {}, { beacon: true });
}

/**
 * Track scroll depth milestone
 */
export function trackScrollDepth(depth: 25 | 50 | 75 | 100): void {
  track('page.scroll_depth', { depth });
}

/**
 * Track API error
 */
export function trackApiError(endpoint: string, status: number, message?: string): void {
  track('error.api', { endpoint, status, message });
}

// ============================================================================
// React Hook for automatic page tracking
// ============================================================================

/**
 * Initialize analytics event listeners
 * Call once in your app layout/provider
 */
export function initAnalytics(): () => void {
  if (typeof window === 'undefined') return () => {};

  // Track initial page view
  trackPageView();

  // Track page exit
  const handleBeforeUnload = () => trackPageExit();
  window.addEventListener('beforeunload', handleBeforeUnload);

  // Track scroll depth (debounced)
  const scrollMilestones = new Set<number>();
  let scrollTimeout: ReturnType<typeof setTimeout>;

  const handleScroll = () => {
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(() => {
      const scrollPercent = Math.round(
        (window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 100
      );

      [25, 50, 75, 100].forEach(milestone => {
        if (scrollPercent >= milestone && !scrollMilestones.has(milestone)) {
          scrollMilestones.add(milestone);
          trackScrollDepth(milestone as 25 | 50 | 75 | 100);
        }
      });
    }, 100);
  };

  window.addEventListener('scroll', handleScroll, { passive: true });

  // Cleanup function
  return () => {
    window.removeEventListener('beforeunload', handleBeforeUnload);
    window.removeEventListener('scroll', handleScroll);
    clearTimeout(scrollTimeout);
  };
}
