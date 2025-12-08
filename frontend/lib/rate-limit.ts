/**
 * Distributed rate limiter using Upstash Redis.
 *
 * Uses sliding window algorithm with Redis for consistency across
 * serverless instances.
 *
 * Falls back to in-memory rate limiting if UPSTASH_REDIS_REST_URL
 * is not configured (dev/test environments).
 */

import { Ratelimit } from '@upstash/ratelimit';
import { Redis } from '@upstash/redis';

export interface RateLimitConfig {
  windowMs: number;  // Time window in milliseconds
  max: number;       // Max requests per window
}

export interface RateLimitResult {
  success: boolean;
  remaining: number;
  resetAt: number;
}

// Lazy-initialize Upstash Redis client
let redis: Redis | null = null;
let ratelimit: Ratelimit | null = null;

function getRedis(): Redis | null {
  if (redis) return redis;

  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;

  if (!url || !token) {
    return null;
  }

  redis = new Redis({ url, token });
  return redis;
}

function getRatelimit(config: RateLimitConfig): Ratelimit | null {
  const redisClient = getRedis();
  if (!redisClient) return null;

  // Create Ratelimit instance with sliding window
  // Note: windowMs is in milliseconds, Ratelimit uses "Xs" or "Xm" format
  const windowSeconds = Math.ceil(config.windowMs / 1000);
  const windowStr = windowSeconds >= 60
    ? `${Math.ceil(windowSeconds / 60)} m`
    : `${windowSeconds} s`;

  return new Ratelimit({
    redis: redisClient,
    limiter: Ratelimit.slidingWindow(config.max, windowStr as `${number} s` | `${number} m`),
    analytics: true,
    prefix: 'tellyads:ratelimit',
  });
}

// ============================================================================
// Fallback in-memory rate limiter (for dev/test without Redis)
// ============================================================================

interface RateLimitEntry {
  count: number;
  resetAt: number;
}

const memoryCache = new Map<string, RateLimitEntry>();

// Clean up old entries periodically
if (typeof setInterval !== 'undefined') {
  setInterval(() => {
    const now = Date.now();
    for (const [key, entry] of memoryCache.entries()) {
      if (entry.resetAt < now) {
        memoryCache.delete(key);
      }
    }
  }, 60000);
}

function checkRateLimitMemory(
  identifier: string,
  config: RateLimitConfig
): RateLimitResult {
  const now = Date.now();
  const entry = memoryCache.get(identifier);

  if (!entry || entry.resetAt < now) {
    memoryCache.set(identifier, {
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

// ============================================================================
// Main rate limit function
// ============================================================================

/**
 * Check rate limit for an identifier.
 *
 * Uses Upstash Redis if configured, falls back to in-memory.
 * WARNING: In-memory fallback is per-instance and can be bypassed
 * across serverless instances. Always configure UPSTASH_REDIS_* in production.
 */
export async function checkRateLimit(
  identifier: string,
  config: RateLimitConfig
): Promise<RateLimitResult> {
  const limiter = getRatelimit(config);

  if (!limiter) {
    // Fallback to in-memory (log warning in production)
    if (process.env.NODE_ENV === 'production') {
      console.warn(
        'SECURITY: Rate limiting using in-memory fallback. ' +
        'Configure UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN for distributed rate limiting.'
      );
    }
    return checkRateLimitMemory(identifier, config);
  }

  try {
    const result = await limiter.limit(identifier);
    return {
      success: result.success,
      remaining: result.remaining,
      resetAt: result.reset,
    };
  } catch (error) {
    // If Redis fails, fall back to memory but log error
    console.error('Rate limit Redis error, falling back to memory:', error);
    return checkRateLimitMemory(identifier, config);
  }
}

/**
 * Synchronous rate limit check (in-memory only).
 * Use this only when async is not possible.
 * WARNING: This bypasses distributed rate limiting.
 */
export function checkRateLimitSync(
  identifier: string,
  config: RateLimitConfig
): RateLimitResult {
  return checkRateLimitMemory(identifier, config);
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

/**
 * Check if distributed rate limiting is configured.
 */
export function isDistributedRateLimitEnabled(): boolean {
  return !!(
    process.env.UPSTASH_REDIS_REST_URL &&
    process.env.UPSTASH_REDIS_REST_TOKEN
  );
}
