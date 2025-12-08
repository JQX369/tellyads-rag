/**
 * Analytics Capture API Route Handler
 *
 * POST /api/analytics/capture
 *
 * Captures analytics events from the frontend client.
 * GDPR-conscious: no raw IP storage, minimal PII.
 */

import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';

export const runtime = 'nodejs';

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
]);

// Rate limiting: max events per session per minute
const RATE_LIMIT_WINDOW_MS = 60000;
const RATE_LIMIT_MAX_EVENTS = 100;
const sessionEventCounts = new Map<string, { count: number; resetAt: number }>();

function checkRateLimit(sessionId: string): boolean {
  const now = Date.now();
  const entry = sessionEventCounts.get(sessionId);

  if (!entry || now > entry.resetAt) {
    sessionEventCounts.set(sessionId, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
    return true;
  }

  if (entry.count >= RATE_LIMIT_MAX_EVENTS) {
    return false;
  }

  entry.count++;
  return true;
}

// Cleanup old rate limit entries periodically
setInterval(() => {
  const now = Date.now();
  for (const [key, entry] of sessionEventCounts) {
    if (now > entry.resetAt) {
      sessionEventCounts.delete(key);
    }
  }
}, 60000);

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

  for (const [key, value] of Object.entries(props)) {
    // Skip sensitive keys
    if (['password', 'token', 'email', 'ip', 'user_agent'].includes(key.toLowerCase())) {
      continue;
    }

    // Sanitize values
    if (typeof value === 'string') {
      sanitized[key] = value.slice(0, 500); // Truncate strings
    } else if (typeof value === 'number' && isFinite(value)) {
      sanitized[key] = value;
    } else if (typeof value === 'boolean') {
      sanitized[key] = value;
    }
    // Skip other types (objects, arrays, null, undefined)
  }

  return sanitized;
}

export async function POST(request: NextRequest) {
  try {
    // Parse body
    const body = await request.json().catch(() => null);

    if (!validatePayload(body)) {
      return NextResponse.json(
        { error: 'Invalid payload' },
        { status: 400 }
      );
    }

    // Rate limit check
    const sessionId = body.session_id || 'anonymous';
    if (!checkRateLimit(sessionId)) {
      return NextResponse.json(
        { error: 'Rate limit exceeded' },
        { status: 429 }
      );
    }

    // Sanitize inputs
    const event = body.event;
    const path = sanitizeString(body.path, 2000);
    const referrer = sanitizeString(body.referrer, 500);
    const uaHash = sanitizeString(body.ua_hash, 64);
    const props = sanitizeProps(body.props);

    // Insert event
    await query(
      `INSERT INTO analytics_events (event, path, referrer, session_id, props, ua_hash)
       VALUES ($1, $2, $3, $4, $5, $6)`,
      [event, path, referrer, sessionId, JSON.stringify(props), uaHash]
    );

    // Return 204 No Content for successful capture (minimal response)
    return new NextResponse(null, { status: 204 });
  } catch (error) {
    console.error('Analytics capture error:', error);

    // Don't expose internal errors - just return 204 to not break client
    // Analytics should never cause visible errors for users
    return new NextResponse(null, { status: 204 });
  }
}

// Support for sendBeacon which sends as text/plain
export async function OPTIONS() {
  return new NextResponse(null, {
    status: 200,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    },
  });
}
