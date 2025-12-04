/**
 * TellyAds Anonymous Session Management
 *
 * Uses a random UUID stored in localStorage (NOT fingerprinting).
 * This is privacy-respecting:
 * - No PII collected
 * - No cross-site tracking
 * - User can reset by clearing localStorage
 * - GDPR-compliant
 */

const SESSION_KEY = 'tellyads_anon_id';

/**
 * Get or create anonymous session ID
 * Returns consistent ID for the same browser session
 */
export function getSessionId(): string {
  if (typeof window === 'undefined') {
    // Server-side rendering - return placeholder
    // This won't be used for API calls (those happen client-side)
    return 'server-side-no-session';
  }

  // Check localStorage first
  let sessionId = localStorage.getItem(SESSION_KEY);
  if (sessionId) {
    return sessionId;
  }

  // Generate new random UUID
  sessionId = crypto.randomUUID();
  localStorage.setItem(SESSION_KEY, sessionId);
  return sessionId;
}

/**
 * Clear session ID (for testing or user-requested reset)
 */
export function clearSessionId(): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem(SESSION_KEY);
  }
}

/**
 * Check if user has an existing session
 */
export function hasSession(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }
  return localStorage.getItem(SESSION_KEY) !== null;
}
