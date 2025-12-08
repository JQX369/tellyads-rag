/**
 * Tests for admin authentication
 *
 * Verifies that admin auth:
 * 1. Denies access when ADMIN_API_KEY is not configured
 * 2. Denies access when wrong key is provided
 * 3. Allows access with correct key
 * 4. Supports key rotation via comma-separated keys
 */

import { verifyAdminKey, isAdminConfigured } from '../admin-auth';

describe('verifyAdminKey', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    // Reset env before each test
    jest.resetModules();
    process.env = { ...originalEnv };
    delete process.env.ADMIN_API_KEY;
    delete process.env.ADMIN_API_KEYS;
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  describe('when ADMIN_API_KEY is not configured', () => {
    it('should deny access (never default-open)', () => {
      const result = verifyAdminKey('any-key');
      expect(result.verified).toBe(false);
      expect(result.error).toBe('Admin access not configured');
    });

    it('should deny access even with null key', () => {
      const result = verifyAdminKey(null);
      expect(result.verified).toBe(false);
      expect(result.error).toBe('Admin access not configured');
    });
  });

  describe('when ADMIN_API_KEY is configured', () => {
    beforeEach(() => {
      process.env.ADMIN_API_KEY = 'secret-admin-key-123';
    });

    it('should deny access when no key provided', () => {
      const result = verifyAdminKey(null);
      expect(result.verified).toBe(false);
      expect(result.error).toBe('X-Admin-Key header required');
    });

    it('should deny access when wrong key provided', () => {
      const result = verifyAdminKey('wrong-key');
      expect(result.verified).toBe(false);
      expect(result.error).toBe('Invalid admin key');
    });

    it('should allow access with correct key', () => {
      const result = verifyAdminKey('secret-admin-key-123');
      expect(result.verified).toBe(true);
      expect(result.error).toBeUndefined();
    });

    it('should deny access for partial key match', () => {
      const result = verifyAdminKey('secret-admin-key');
      expect(result.verified).toBe(false);
      expect(result.error).toBe('Invalid admin key');
    });
  });

  describe('key rotation (comma-separated keys)', () => {
    beforeEach(() => {
      process.env.ADMIN_API_KEYS = 'old-key-123, new-key-456, future-key-789';
    });

    it('should accept first key', () => {
      const result = verifyAdminKey('old-key-123');
      expect(result.verified).toBe(true);
    });

    it('should accept second key', () => {
      const result = verifyAdminKey('new-key-456');
      expect(result.verified).toBe(true);
    });

    it('should accept third key', () => {
      const result = verifyAdminKey('future-key-789');
      expect(result.verified).toBe(true);
    });

    it('should reject invalid key', () => {
      const result = verifyAdminKey('invalid-key');
      expect(result.verified).toBe(false);
    });
  });
});

describe('isAdminConfigured', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
    delete process.env.ADMIN_API_KEY;
    delete process.env.ADMIN_API_KEYS;
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('should return false when no keys configured', () => {
    expect(isAdminConfigured()).toBe(false);
  });

  it('should return true when ADMIN_API_KEY is set', () => {
    process.env.ADMIN_API_KEY = 'some-key';
    expect(isAdminConfigured()).toBe(true);
  });

  it('should return true when ADMIN_API_KEYS is set', () => {
    process.env.ADMIN_API_KEYS = 'key1, key2';
    expect(isAdminConfigured()).toBe(true);
  });
});
