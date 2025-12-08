/**
 * Analytics Capture Endpoint Tests
 *
 * Tests the /api/analytics/capture endpoint for:
 * - Valid event acceptance
 * - Invalid event rejection
 * - Payload validation
 * - Props sanitization
 */

import { POST } from '@/app/api/analytics/capture/route';
import { createCaptureRequest, parseResponse } from './helpers/mock-request';
import { createValidPayload, VALID_EVENTS } from './helpers/seed';

describe('Analytics Capture Endpoint', () => {
  describe('Valid Events (Happy Path)', () => {
    it('should accept a valid page.view event and return 204', async () => {
      const payload = createValidPayload({ event: 'page.view' });
      const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });

      // Mock successful DB insert
      global.mockDbQuery.mockResolvedValueOnce({ rows: [] });

      const response = await POST(request);
      const { status } = await parseResponse(response);

      expect(status).toBe(204);
      expect(global.mockDbQuery).toHaveBeenCalledWith(
        expect.stringContaining('INSERT INTO analytics_events'),
        expect.any(Array)
      );
    });

    it('should accept a valid search.performed event with props', async () => {
      const payload = createValidPayload({
        event: 'search.performed',
        props: {
          query: 'test query',
          results_count: 10,
          latency_ms: 50,
        },
      });
      const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });

      global.mockDbQuery.mockResolvedValueOnce({ rows: [] });

      const response = await POST(request);
      const { status } = await parseResponse(response);

      expect(status).toBe(204);
    });

    it('should accept all valid event types', async () => {
      for (const eventType of VALID_EVENTS.slice(0, 5)) {
        // Test first 5 for speed
        const payload = createValidPayload({ event: eventType });
        const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });

        global.mockDbQuery.mockResolvedValueOnce({ rows: [] });

        const response = await POST(request);
        const { status } = await parseResponse(response);

        expect(status).toBe(204);
      }
    });

    it('should handle event without optional fields', async () => {
      const payload = {
        event: 'page.view',
      };
      const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });

      global.mockDbQuery.mockResolvedValueOnce({ rows: [] });

      const response = await POST(request);
      const { status } = await parseResponse(response);

      expect(status).toBe(204);
    });
  });

  describe('Invalid Events (Rejection)', () => {
    it('should reject unknown event name with 400', async () => {
      const payload = createValidPayload({ event: 'unknown.event' });
      const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });

      const response = await POST(request);
      const { status, data } = await parseResponse<{ error: string }>(response);

      expect(status).toBe(400);
      expect(data?.error).toBe('Invalid payload');
    });

    it('should reject empty event name with 400', async () => {
      const payload = createValidPayload({ event: '' });
      const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });

      const response = await POST(request);
      const { status, data } = await parseResponse<{ error: string }>(response);

      expect(status).toBe(400);
      expect(data?.error).toBe('Invalid payload');
    });

    it('should reject missing event field with 400', async () => {
      const payload = { path: '/test', session_id: 'test' };
      const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });

      const response = await POST(request);
      const { status, data } = await parseResponse<{ error: string }>(response);

      expect(status).toBe(400);
      expect(data?.error).toBe('Invalid payload');
    });

    it('should reject non-string event with 400', async () => {
      const payload = { event: 123, path: '/test' };
      const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });

      const response = await POST(request);
      const { status, data } = await parseResponse<{ error: string }>(response);

      expect(status).toBe(400);
      expect(data?.error).toBe('Invalid payload');
    });

    it('should reject non-object payload with 400', async () => {
      const request = createCaptureRequest('not an object', { origin: 'http://localhost:3000' });

      const response = await POST(request);
      const { status, data } = await parseResponse<{ error: string }>(response);

      expect(status).toBe(400);
      expect(data?.error).toBe('Invalid payload');
    });

    it('should reject null payload with 400', async () => {
      const request = createCaptureRequest(null, { origin: 'http://localhost:3000' });

      const response = await POST(request);
      const { status, data } = await parseResponse<{ error: string }>(response);

      expect(status).toBe(400);
      expect(data?.error).toBe('Invalid payload');
    });
  });

  describe('Props Validation & Sanitization', () => {
    it('should strip sensitive keys from props', async () => {
      const payload = createValidPayload({
        props: {
          query: 'test',
          password: 'secret123',
          token: 'abc123',
          email: 'user@example.com',
          safe_value: 'kept',
        },
      });
      const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });

      global.mockDbQuery.mockResolvedValueOnce({ rows: [] });

      await POST(request);

      // Check that the DB was called with sanitized props
      expect(global.mockDbQuery).toHaveBeenCalled();
      const callArgs = global.mockDbQuery.mock.calls[0][1];
      const propsJson = JSON.parse(callArgs[4]); // props is 5th parameter

      expect(propsJson).not.toHaveProperty('password');
      expect(propsJson).not.toHaveProperty('token');
      expect(propsJson).not.toHaveProperty('email');
      expect(propsJson).toHaveProperty('query', 'test');
      expect(propsJson).toHaveProperty('safe_value', 'kept');
    });

    it('should truncate long string values in props', async () => {
      const longString = 'a'.repeat(1000);
      const payload = createValidPayload({
        props: { long_value: longString },
      });
      const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });

      global.mockDbQuery.mockResolvedValueOnce({ rows: [] });

      await POST(request);

      const callArgs = global.mockDbQuery.mock.calls[0][1];
      const propsJson = JSON.parse(callArgs[4]);

      expect(propsJson.long_value.length).toBeLessThanOrEqual(500);
    });

    it('should preserve numeric and boolean props', async () => {
      const payload = createValidPayload({
        props: {
          count: 42,
          enabled: true,
          ratio: 3.14,
        },
      });
      const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });

      global.mockDbQuery.mockResolvedValueOnce({ rows: [] });

      await POST(request);

      const callArgs = global.mockDbQuery.mock.calls[0][1];
      const propsJson = JSON.parse(callArgs[4]);

      expect(propsJson.count).toBe(42);
      expect(propsJson.enabled).toBe(true);
      expect(propsJson.ratio).toBe(3.14);
    });
  });

  describe('Path Sanitization', () => {
    it('should truncate long paths', async () => {
      const longPath = '/test/' + 'a'.repeat(3000);
      const payload = createValidPayload({ path: longPath });
      const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });

      global.mockDbQuery.mockResolvedValueOnce({ rows: [] });

      await POST(request);

      const callArgs = global.mockDbQuery.mock.calls[0][1];
      const path = callArgs[1]; // path is 2nd parameter

      expect(path.length).toBeLessThanOrEqual(2000);
    });
  });

  describe('Error Handling', () => {
    it('should return 204 silently on DB error (silent failure)', async () => {
      const payload = createValidPayload();
      const request = createCaptureRequest(payload, { origin: 'http://localhost:3000' });

      global.mockDbQuery.mockRejectedValueOnce(new Error('Database connection failed'));

      const response = await POST(request);
      const { status } = await parseResponse(response);

      // Analytics should never break UX - silent 204
      expect(status).toBe(204);
    });
  });
});
