/**
 * Admin authentication utilities.
 *
 * Uses timing-safe comparison to prevent timing attacks.
 * Server-side only - never expose admin keys to client.
 */

import { timingSafeEqual } from 'crypto';

/**
 * Timing-safe string comparison.
 * Prevents timing attacks by ensuring constant-time comparison.
 */
function timingSafeCompare(a: string, b: string): boolean {
  if (typeof a !== 'string' || typeof b !== 'string') {
    return false;
  }

  // Pad to same length to avoid length-based timing leaks
  const aBuffer = Buffer.from(a.padEnd(256, '\0'));
  const bBuffer = Buffer.from(b.padEnd(256, '\0'));

  try {
    return timingSafeEqual(aBuffer, bBuffer) && a.length === b.length;
  } catch {
    return false;
  }
}

/**
 * Get configured admin keys (supports rotation via comma-separated list).
 * Returns null if admin auth is not configured.
 */
function getAdminKeys(): string[] | null {
  const keysEnv = process.env.ADMIN_API_KEY || process.env.ADMIN_API_KEYS;
  if (!keysEnv) {
    return null;
  }

  // Support comma-separated keys for rotation
  return keysEnv.split(',').map((k) => k.trim()).filter(Boolean);
}

/**
 * Verify admin API key from request header.
 *
 * @param headerValue - Value of X-Admin-Key header
 * @returns Object with verified status and error message if any
 */
export function verifyAdminKey(headerValue: string | null): {
  verified: boolean;
  error?: string;
} {
  const adminKeys = getAdminKeys();

  // Not configured
  if (!adminKeys || adminKeys.length === 0) {
    console.warn('Admin authentication not configured. Set ADMIN_API_KEY or ADMIN_API_KEYS env var.');
    return {
      verified: false,
      error: 'Admin authentication not configured',
    };
  }

  // No key provided
  if (!headerValue) {
    return {
      verified: false,
      error: 'X-Admin-Key header required',
    };
  }

  // Check against all valid keys (for rotation support)
  for (const validKey of adminKeys) {
    if (timingSafeCompare(headerValue, validKey)) {
      return { verified: true };
    }
  }

  return {
    verified: false,
    error: 'Invalid admin key',
  };
}

/**
 * Check if admin auth is configured at all.
 */
export function isAdminConfigured(): boolean {
  const adminKeys = getAdminKeys();
  return adminKeys !== null && adminKeys.length > 0;
}
