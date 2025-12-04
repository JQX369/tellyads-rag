/**
 * Simple in-memory rate limiter for Vercel serverless.
 * Uses sliding window counter algorithm.
 *
 * Note: This is per-instance. For distributed rate limiting,
 * consider Vercel KV or Upstash Redis in the future.
 */

interface RateLimitEntry {
  count: number;
  resetAt: number;
}

// In-memory cache (per serverless instance)
const cache = new Map<string, RateLimitEntry>();

// Clean up old entries periodically (every 60 seconds)
if (typeof setInterval !== 'undefined') {
  setInterval(() => {
    const now = Date.now();
    for (const [key, entry] of cache.entries()) {
      if (entry.resetAt < now) {
        cache.delete(key);
      }
    }
  }, 60000);
}

export interface RateLimitConfig {
  windowMs: number;  // Time window in milliseconds
  max: number;       // Max requests per window
}

export interface RateLimitResult {
  success: boolean;
  remaining: number;
  resetAt: number;
}

/**
 * Check rate limit for an identifier.
 */
export function checkRateLimit(
  identifier: string,
  config: RateLimitConfig
): RateLimitResult {
  const now = Date.now();

  const entry = cache.get(identifier);

  if (!entry || entry.resetAt < now) {
    // New window
    cache.set(identifier, {
      count: 1,
      resetAt: now + config.windowMs,
    });
    return {
      success: true,
      remaining: config.max - 1,
      resetAt: now + config.windowMs,
    };
  }

  if (entry.count >= config.max) {
    return {
      success: false,
      remaining: 0,
      resetAt: entry.resetAt,
    };
  }

  entry.count++;
  return {
    success: true,
    remaining: config.max - entry.count,
    resetAt: entry.resetAt,
  };
}

/**
 * Hash a string to avoid storing raw identifiers (e.g., IPs).
 * Simple djb2 hash - not cryptographic but sufficient for rate limiting keys.
 */
export function hashString(str: string): string {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) + hash) ^ str.charCodeAt(i);
  }
  return Math.abs(hash).toString(36);
}

/**
 * Get rate limit key from request.
 * Uses session_id from body/query, or hashed IP as fallback.
 */
export function getRateLimitKey(
  request: Request,
  sessionId?: string | null
): string {
  // Prefer session_id if available
  if (sessionId) {
    return `rl:session:${hashString(sessionId)}`;
  }

  // Fallback to hashed IP (Vercel provides X-Forwarded-For)
  const forwarded = request.headers.get('x-forwarded-for');
  const ip = forwarded?.split(',')[0]?.trim() || 'anonymous';
  return `rl:ip:${hashString(ip)}`;
}
