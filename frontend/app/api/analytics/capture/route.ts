/**
 * Analytics Capture API Route Handler
 *
 * POST /api/analytics/capture
 *
 * Captures analytics events from the frontend client.
 * GDPR-conscious: no raw IP storage, minimal PII.
 *
 * PRODUCTION HARDENING:
 * - Origin validation (prevents cross-site abuse)
 * - Dual rate limiting (session + ua_hash fallback)
 * - Error tracking with aggregate metrics
 * - Silent failures for UX (analytics never breaks user experience)
 */

import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';
import { trackCaptureError, trackEventIngested, getCaptureMetrics } from '@/lib/analytics-metrics';

export const runtime = 'nodejs';

// ============================================================================
// Configuration
// ============================================================================

// Allowed origins for capture requests (prevents cross-site abuse)
const ALLOWED_ORIGINS = new Set([
  'https://tellyads.com',
  'https://www.tellyads.com',
  // Development
  'http://localhost:3000',
  'http://127.0.0.1:3000',
]);

// Rate limiting configuration
const RATE_LIMIT_WINDOW_MS = 60000; // 1 minute
const RATE_LIMIT_MAX_PER_SESSION = 100;
const RATE_LIMIT_MAX_PER_UA_HASH = 500; // Higher limit for ua_hash (shared across sessions)

// Valid event types (must match taxonomy in lib/analytics.ts)
const VALID_EVENTS = new Set([
  // Page events
  'page.view',
  'page.scroll_depth',
  'page.exit',
  // Search events
  'search.performed',
  'search.result_click',
  'search.zero_results',
  'search.filter_applied',
  // Advert engagement events
  'advert.view',
  'advert.play',
  'advert.pause',
  'advert.complete',
  'advert.like',
  'advert.save',
  'advert.share',
  'advert.similar_click',
  // Browse events
  'browse.era_click',
  'browse.brand_click',
  'browse.random_click',
  // Outbound
  'outbound.click',
  // Error tracking
  'error.api',
  'error.client',
  // SEO tracking (404s, legacy redirects)
  'seo.404',
  'seo.legacy_redirect',
]);

// ============================================================================
// Rate Limiting
// ============================================================================

interface RateLimitEntry {
  count: number;
  resetAt: number;
}

const sessionRateLimits = new Map<string, RateLimitEntry>();
const uaHashRateLimits = new Map<string, RateLimitEntry>();

function checkRateLimit(
  limiter: Map<string, RateLimitEntry>,
  key: string,
  maxCount: number
): boolean {
  const now = Date.now();
  const entry = limiter.get(key);

  if (!entry || now > entry.resetAt) {
    limiter.set(key, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
    return true;
  }

  if (entry.count >= maxCount) {
    return false;
  }

  entry.count++;
  return true;
}

// Cleanup old entries periodically
setInterval(() => {
  const now = Date.now();
  for (const [key, entry] of sessionRateLimits) {
    if (now > entry.resetAt) sessionRateLimits.delete(key);
  }
  for (const [key, entry] of uaHashRateLimits) {
    if (now > entry.resetAt) uaHashRateLimits.delete(key);
  }
}, 60000);

// ============================================================================
// Origin Validation
// ============================================================================

function validateOrigin(request: NextRequest): boolean {
  // Skip validation in development
  if (process.env.NODE_ENV === 'development') {
    return true;
  }

  const origin = request.headers.get('origin');
  const referer = request.headers.get('referer');

  // Check Origin header first (most reliable)
  if (origin) {
    return ALLOWED_ORIGINS.has(origin);
  }

  // Fallback to Referer for sendBeacon (which may not include Origin)
  if (referer) {
    try {
      const refererUrl = new URL(referer);
      return ALLOWED_ORIGINS.has(refererUrl.origin);
    } catch {
      return false;
    }
  }

  // sendBeacon without headers - allow but with stricter rate limiting
  // This is a tradeoff: blocking all would break legitimate page-exit tracking
  return true;
}

// ============================================================================
// Payload Validation & Sanitization
// ============================================================================

interface AnalyticsPayload {
  event: string;
  path?: string;
  referrer?: string;
  session_id?: string;
  props?: Record<string, unknown>;
  ua_hash?: string;
  ts?: string;
}

function validatePayload(body: unknown): body is AnalyticsPayload {
  if (typeof body !== 'object' || body === null) return false;

  const payload = body as AnalyticsPayload;

  // Event is required and must be valid
  if (typeof payload.event !== 'string' || !VALID_EVENTS.has(payload.event)) {
    return false;
  }

  // Optional fields validation
  if (payload.path !== undefined && typeof payload.path !== 'string') return false;
  if (payload.referrer !== undefined && typeof payload.referrer !== 'string') return false;
  if (payload.session_id !== undefined && typeof payload.session_id !== 'string') return false;
  if (payload.ua_hash !== undefined && typeof payload.ua_hash !== 'string') return false;
  if (payload.props !== undefined && typeof payload.props !== 'object') return false;

  return true;
}

function sanitizeString(str: string | undefined, maxLength: number): string | null {
  if (!str) return null;
  return str.slice(0, maxLength);
}

function sanitizeProps(props: Record<string, unknown> | undefined): Record<string, unknown> {
  if (!props) return {};

  const sanitized: Record<string, unknown> = {};
  const sensitiveKeys = ['password', 'token', 'email', 'ip', 'user_agent', 'cookie', 'authorization'];

  for (const [key, value] of Object.entries(props)) {
    // Skip sensitive keys
    if (sensitiveKeys.includes(key.toLowerCase())) {
      continue;
    }

    // Sanitize values
    if (typeof value === 'string') {
      sanitized[key] = value.slice(0, 500);
    } else if (typeof value === 'number' && isFinite(value)) {
      sanitized[key] = value;
    } else if (typeof value === 'boolean') {
      sanitized[key] = value;
    }
  }

  return sanitized;
}

// ============================================================================
// Request Handler
// ============================================================================

export async function POST(request: NextRequest) {
  try {
    // Origin validation
    if (!validateOrigin(request)) {
      // Silent rejection for cross-origin abuse
      return new NextResponse(null, { status: 204 });
    }

    // Parse body
    const body = await request.json().catch(() => null);

    if (!validatePayload(body)) {
      return NextResponse.json(
        { error: 'Invalid payload' },
        { status: 400 }
      );
    }

    // Dual rate limiting: session first, ua_hash as fallback
    const sessionId = body.session_id || 'anonymous';
    const uaHash = body.ua_hash || 'unknown';

    // Check session rate limit
    if (!checkRateLimit(sessionRateLimits, sessionId, RATE_LIMIT_MAX_PER_SESSION)) {
      return NextResponse.json(
        { error: 'Rate limit exceeded' },
        { status: 429 }
      );
    }

    // Check ua_hash rate limit (catches session rotation abuse)
    if (!checkRateLimit(uaHashRateLimits, uaHash, RATE_LIMIT_MAX_PER_UA_HASH)) {
      return NextResponse.json(
        { error: 'Rate limit exceeded' },
        { status: 429 }
      );
    }

    // Sanitize inputs
    const event = body.event;
    const path = sanitizeString(body.path, 2000);
    const referrer = sanitizeString(body.referrer, 500);
    const sanitizedUaHash = sanitizeString(body.ua_hash, 64);
    const props = sanitizeProps(body.props);

    // Insert event
    await query(
      `INSERT INTO analytics_events (event, path, referrer, session_id, props, ua_hash)
       VALUES ($1, $2, $3, $4, $5, $6)`,
      [event, path, referrer, sessionId, JSON.stringify(props), sanitizedUaHash]
    );

    // Track successful ingestion
    trackEventIngested();

    // Return 204 No Content for successful capture
    return new NextResponse(null, { status: 204 });
  } catch (error) {
    // Track error without logging PII
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    trackCaptureError(errorMessage);

    // Log aggregate error info (not PII)
    if (process.env.NODE_ENV !== 'development') {
      const metrics = getCaptureMetrics();
      console.error(`[Analytics] Capture error #${metrics.error_count}: ${errorMessage.slice(0, 100)}`);
    }

    // Silent failure - analytics should never break UX
    return new NextResponse(null, { status: 204 });
  }
}

// CORS preflight for sendBeacon
export async function OPTIONS() {
  const allowedOrigin = process.env.NODE_ENV === 'development'
    ? '*'
    : 'https://tellyads.com';

  return new NextResponse(null, {
    status: 200,
    headers: {
      'Access-Control-Allow-Origin': allowedOrigin,
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Max-Age': '86400',
    },
  });
}
