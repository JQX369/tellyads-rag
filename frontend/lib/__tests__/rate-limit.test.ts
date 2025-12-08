/**
 * Tests for rate limiting
 *
 * Tests the in-memory fallback rate limiter.
 * Upstash Redis integration testing requires actual Redis instance.
 */

import {
  checkRateLimitSync,
  getRateLimitKey,
  hashString,
  isDistributedRateLimitEnabled,
} from '../rate-limit';

describe('hashString', () => {
  it('should produce consistent hashes', () => {
    const hash1 = hashString('test-string');
    const hash2 = hashString('test-string');
    expect(hash1).toBe(hash2);
  });

  it('should produce different hashes for different inputs', () => {
    const hash1 = hashString('string-a');
    const hash2 = hashString('string-b');
    expect(hash1).not.toBe(hash2);
  });

  it('should handle empty strings', () => {
    const hash = hashString('');
    expect(typeof hash).toBe('string');
    expect(hash.length).toBeGreaterThan(0);
  });
});

describe('getRateLimitKey', () => {
  it('should use session_id when provided', () => {
    const mockRequest = {
      headers: new Headers({ 'x-forwarded-for': '1.2.3.4' }),
    } as Request;

    const key = getRateLimitKey(mockRequest, 'session-123');
    expect(key).toMatch(/^rl:session:/);
  });

  it('should fall back to IP when no session_id', () => {
    const mockRequest = {
      headers: new Headers({ 'x-forwarded-for': '1.2.3.4' }),
    } as Request;

    const key = getRateLimitKey(mockRequest, null);
    expect(key).toMatch(/^rl:ip:/);
  });

  it('should use anonymous for missing IP', () => {
    const mockRequest = {
      headers: new Headers(),
    } as Request;

    const key = getRateLimitKey(mockRequest, null);
    expect(key).toMatch(/^rl:ip:/);
  });

  it('should handle multiple IPs in x-forwarded-for', () => {
    const mockRequest = {
      headers: new Headers({ 'x-forwarded-for': '1.2.3.4, 5.6.7.8, 9.10.11.12' }),
    } as Request;

    const key = getRateLimitKey(mockRequest, null);
    // Should use first IP only
    expect(key).toMatch(/^rl:ip:/);
  });
});

describe('checkRateLimitSync (in-memory fallback)', () => {
  const config = { windowMs: 60000, max: 3 };

  it('should allow requests within limit', () => {
    const identifier = `test-${Date.now()}-${Math.random()}`;

    const result1 = checkRateLimitSync(identifier, config);
    expect(result1.success).toBe(true);
    expect(result1.remaining).toBe(2);

    const result2 = checkRateLimitSync(identifier, config);
    expect(result2.success).toBe(true);
    expect(result2.remaining).toBe(1);

    const result3 = checkRateLimitSync(identifier, config);
    expect(result3.success).toBe(true);
    expect(result3.remaining).toBe(0);
  });

  it('should block requests exceeding limit', () => {
    const identifier = `test-block-${Date.now()}-${Math.random()}`;

    // Exhaust the limit
    checkRateLimitSync(identifier, config);
    checkRateLimitSync(identifier, config);
    checkRateLimitSync(identifier, config);

    // This should be blocked
    const result = checkRateLimitSync(identifier, config);
    expect(result.success).toBe(false);
    expect(result.remaining).toBe(0);
  });

  it('should return resetAt timestamp', () => {
    const identifier = `test-reset-${Date.now()}-${Math.random()}`;
    const beforeTime = Date.now();

    const result = checkRateLimitSync(identifier, config);

    expect(result.resetAt).toBeGreaterThan(beforeTime);
    expect(result.resetAt).toBeLessThanOrEqual(beforeTime + config.windowMs + 100);
  });

  it('should track different identifiers separately', () => {
    const id1 = `test-id1-${Date.now()}`;
    const id2 = `test-id2-${Date.now()}`;

    // Exhaust id1
    checkRateLimitSync(id1, config);
    checkRateLimitSync(id1, config);
    checkRateLimitSync(id1, config);
    const blockedResult = checkRateLimitSync(id1, config);
    expect(blockedResult.success).toBe(false);

    // id2 should still work
    const allowedResult = checkRateLimitSync(id2, config);
    expect(allowedResult.success).toBe(true);
  });
});

describe('isDistributedRateLimitEnabled', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
    delete process.env.UPSTASH_REDIS_REST_URL;
    delete process.env.UPSTASH_REDIS_REST_TOKEN;
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('should return false when Upstash not configured', () => {
    expect(isDistributedRateLimitEnabled()).toBe(false);
  });

  it('should return false when only URL configured', () => {
    process.env.UPSTASH_REDIS_REST_URL = 'https://example.upstash.io';
    expect(isDistributedRateLimitEnabled()).toBe(false);
  });

  it('should return false when only token configured', () => {
    process.env.UPSTASH_REDIS_REST_TOKEN = 'token123';
    expect(isDistributedRateLimitEnabled()).toBe(false);
  });

  it('should return true when both configured', () => {
    process.env.UPSTASH_REDIS_REST_URL = 'https://example.upstash.io';
    process.env.UPSTASH_REDIS_REST_TOKEN = 'token123';
    expect(isDistributedRateLimitEnabled()).toBe(true);
  });
});
