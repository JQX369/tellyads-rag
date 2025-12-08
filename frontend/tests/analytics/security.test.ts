/**
 * Analytics Security Tests
 *
 * Tests origin validation and rate limiting for the capture endpoint.
 */

import { POST } from '@/app/api/analytics/capture/route';
import { createCaptureRequest, parseResponse } from './helpers/mock-request';
import { createValidPayload } from './helpers/seed';

describe('Analytics Security', () => {
  describe('Origin Validation', () => {
    // Note: Origin validation is bypassed in development mode
    // These tests verify behavior in development (process.env.NODE_ENV = 'test')

    it('should accept requests with allowed origin (localhost:3000)', async () => {
      const payload = createValidPayload();
      const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });

      global.mockDbQuery.mockResolvedValueOnce({ rows: [] });

      const response = await POST(request);
      const { status } = await parseResponse(response);

      expect(status).toBe(204);
    });

    it('should accept requests with production origin', async () => {
      const payload = createValidPayload();
      const request = createCaptureRequest(payload, { origin: 'https://tellyads.com' });

      global.mockDbQuery.mockResolvedValueOnce({ rows: [] });

      const response = await POST(request);
      const { status } = await parseResponse(response);

      expect(status).toBe(204);
    });

    it('should accept requests with www production origin', async () => {
      const payload = createValidPayload();
      const request = createCaptureRequest(payload, { origin: 'https://www.tellyads.com' });

      global.mockDbQuery.mockResolvedValueOnce({ rows: [] });

      const response = await POST(request);
      const { status } = await parseResponse(response);

      expect(status).toBe(204);
    });

    it('should accept requests using Referer header when Origin is missing', async () => {
      const payload = createValidPayload();
      const request = createCaptureRequest(payload, { referer: 'http://localhost:3000/page' });

      global.mockDbQuery.mockResolvedValueOnce({ rows: [] });

      const response = await POST(request);
      const { status } = await parseResponse(response);

      expect(status).toBe(204);
    });

    // Note: In test/development mode, origin validation is more permissive
    // Production behavior would reject invalid origins with 204 (silent rejection)
  });

  describe('Rate Limiting', () => {
    beforeEach(() => {
      // Reset any rate limit state between tests
      jest.resetModules();
    });

    it('should accept requests within rate limit', async () => {
      const payload = createValidPayload({ session_id: 'rate-limit-test-session' });
      const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });

      global.mockDbQuery.mockResolvedValueOnce({ rows: [] });

      const response = await POST(request);
      const { status } = await parseResponse(response);

      expect(status).toBe(204);
    });

    it('should return 429 when session rate limit is exceeded', async () => {
      // Import fresh module to reset rate limit state
      jest.resetModules();
      const { POST: freshPOST } = await import('@/app/api/analytics/capture/route');

      const sessionId = 'rate-limit-exceed-session-' + Date.now();

      // Mock DB to succeed
      global.mockDbQuery.mockResolvedValue({ rows: [] });

      // Send 101 requests (limit is 100)
      let lastStatus = 0;
      for (let i = 0; i < 101; i++) {
        const payload = createValidPayload({ session_id: sessionId });
        const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });

        const response = await freshPOST(request);
        const { status } = await parseResponse(response);
        lastStatus = status;

        if (status === 429) break;
      }

      expect(lastStatus).toBe(429);
    });

    it('should return 429 when ua_hash rate limit is exceeded', async () => {
      // Import fresh module to reset rate limit state
      jest.resetModules();
      const { POST: freshPOST } = await import('@/app/api/analytics/capture/route');

      const uaHash = 'ua-hash-exceed-test-' + Date.now();

      // Mock DB to succeed
      global.mockDbQuery.mockResolvedValue({ rows: [] });

      // Send 501 requests with different sessions but same ua_hash (limit is 500)
      let lastStatus = 0;
      for (let i = 0; i < 501; i++) {
        const payload = createValidPayload({
          session_id: `different-session-${i}`,
          ua_hash: uaHash,
        });
        const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });

        const response = await freshPOST(request);
        const { status } = await parseResponse(response);
        lastStatus = status;

        if (status === 429) break;
      }

      expect(lastStatus).toBe(429);
    });

    it('should use different rate limit buckets for different sessions', async () => {
      jest.resetModules();
      const { POST: freshPOST } = await import('@/app/api/analytics/capture/route');

      global.mockDbQuery.mockResolvedValue({ rows: [] });

      // Send requests with two different sessions
      const session1 = 'session-bucket-1-' + Date.now();
      const session2 = 'session-bucket-2-' + Date.now();

      // 50 requests for session 1
      for (let i = 0; i < 50; i++) {
        const payload = createValidPayload({ session_id: session1 });
        const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });
        await freshPOST(request);
      }

      // Session 2 should still work (different bucket)
      const payload = createValidPayload({ session_id: session2 });
      const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });
      const response = await freshPOST(request);
      const { status } = await parseResponse(response);

      expect(status).toBe(204);
    });
  });

  describe('Admin Endpoint Security', () => {
    it('should reject admin requests without x-admin-key header', async () => {
      const { GET } = await import('@/app/api/admin/analytics/overview/route');
      const { createMockRequest } = await import('./helpers/mock-request');

      // Use createMockRequest directly to avoid default adminKey
      const request = createMockRequest({
        url: 'http://localhost:3000/api/admin/analytics/overview',
        // No x-admin-key header
      });

      const response = await GET(request);
      const { status, data } = await parseResponse<{ error: string }>(response);

      expect(status).toBe(401);
      expect(data?.error).toBeDefined();
    });

    it('should reject admin requests with invalid key', async () => {
      const { GET } = await import('@/app/api/admin/analytics/overview/route');
      const { createAdminRequest } = await import('./helpers/mock-request');

      const request = createAdminRequest('/api/admin/analytics/overview', {
        adminKey: 'wrong-key',
      });

      const response = await GET(request);
      const { status, data } = await parseResponse<{ error: string }>(response);

      expect(status).toBe(401);
      expect(data?.error).toBe('Invalid admin key');
    });

    it('should accept admin requests with valid key', async () => {
      const { GET } = await import('@/app/api/admin/analytics/overview/route');
      const { createAdminRequest } = await import('./helpers/mock-request');

      // Mock DB responses for overview endpoint
      global.mockDbQueryOne.mockResolvedValue({ exists: false });

      const request = createAdminRequest('/api/admin/analytics/overview', {
        adminKey: 'test-admin-key-12345',
      });

      const response = await GET(request);
      const { status } = await parseResponse(response);

      expect(status).toBe(200);
    });
  });
});
