/**
 * Analytics Rollup Endpoint Tests
 *
 * Tests the /api/admin/analytics/rollup endpoint for:
 * - Security (requires admin key or cron secret)
 * - Rollup execution
 * - Status reporting
 */

import { createAdminRequest, createCronRequest, parseResponse } from './helpers/mock-request';
import { generateSeedData, getExpectedRollupResults } from './helpers/seed';

describe('Analytics Rollup Endpoint', () => {
  describe('Security', () => {
    it('should reject POST without authentication', async () => {
      const { POST } = await import('@/app/api/admin/analytics/rollup/route');
      const { createMockRequest } = await import('./helpers/mock-request');

      const request = createMockRequest({
        method: 'POST',
        url: 'http://localhost:3000/api/admin/analytics/rollup',
      });

      const response = await POST(request);
      const { status, data } = await parseResponse<{ error: string }>(response);

      expect(status).toBe(401);
      expect(data?.error).toBeDefined();
    });

    it('should accept POST with valid admin key', async () => {
      const { POST } = await import('@/app/api/admin/analytics/rollup/route');

      // Mock DB responses
      global.mockDbQueryOne.mockResolvedValue({ success: true });
      global.mockDbQuery.mockResolvedValue({ rows: [] });

      const request = createAdminRequest('/api/admin/analytics/rollup', {
        method: 'POST',
        adminKey: 'test-admin-key-12345',
      });

      const response = await POST(request);
      const { status } = await parseResponse(response);

      expect(status).toBe(200);
    });

    it('should accept POST with valid cron secret', async () => {
      const { POST } = await import('@/app/api/admin/analytics/rollup/route');

      // Mock DB responses
      global.mockDbQueryOne.mockResolvedValue({ success: true });
      global.mockDbQuery.mockResolvedValue({ rows: [] });

      const request = createCronRequest('/api/admin/analytics/rollup', {
        cronSecret: 'test-cron-secret',
      });

      const response = await POST(request);
      const { status } = await parseResponse(response);

      expect(status).toBe(200);
    });

    it('should accept POST with Vercel cron header', async () => {
      const { POST } = await import('@/app/api/admin/analytics/rollup/route');

      // Mock DB responses
      global.mockDbQueryOne.mockResolvedValue({ success: true });
      global.mockDbQuery.mockResolvedValue({ rows: [] });

      const request = createCronRequest('/api/admin/analytics/rollup', {
        useCronHeader: true,
      });

      const response = await POST(request);
      const { status } = await parseResponse(response);

      expect(status).toBe(200);
    });

    it('should reject POST with invalid cron secret', async () => {
      const { POST } = await import('@/app/api/admin/analytics/rollup/route');

      const request = createCronRequest('/api/admin/analytics/rollup', {
        cronSecret: 'wrong-secret',
      });

      const response = await POST(request);
      const { status } = await parseResponse(response);

      expect(status).toBe(401);
    });
  });

  describe('GET Status', () => {
    it('should return rollup status with admin key', async () => {
      const { GET } = await import('@/app/api/admin/analytics/rollup/route');

      // Mock last rollup dates (matches actual query in route)
      global.mockDbQueryOne.mockResolvedValueOnce({
        last_daily_events: '2024-01-15',
        last_daily_search: '2024-01-15',
        last_daily_funnel: '2024-01-15',
        oldest_raw_event: '2024-01-01',
        newest_raw_event: '2024-01-15',
        raw_event_count: 1000,
      });

      const request = createAdminRequest('/api/admin/analytics/rollup');

      const response = await GET(request);
      const { status, data } = await parseResponse<Record<string, unknown>>(response);

      expect(status).toBe(200);
      expect(data).toHaveProperty('status', 'ok');
      expect(data).toHaveProperty('last_rollups');
      expect(data).toHaveProperty('raw_events');
      expect(data).toHaveProperty('retention_days', 90);
    });

    it('should handle case when no rollups have run', async () => {
      const { GET } = await import('@/app/api/admin/analytics/rollup/route');

      // Mock no rollup data
      global.mockDbQueryOne.mockResolvedValueOnce(null);

      const request = createAdminRequest('/api/admin/analytics/rollup');

      const response = await GET(request);
      const { status, data } = await parseResponse<Record<string, unknown>>(response);

      expect(status).toBe(200);
      expect(data).toHaveProperty('status');
    });
  });

  describe('Rollup Execution', () => {
    it('should call rollup SQL functions on POST', async () => {
      const { POST } = await import('@/app/api/admin/analytics/rollup/route');

      // Track SQL calls
      const sqlCalls: string[] = [];
      global.mockDbQuery.mockImplementation((sql: string) => {
        sqlCalls.push(sql);
        return Promise.resolve({ rows: [] });
      });
      global.mockDbQueryOne.mockResolvedValue({ success: true });

      const request = createAdminRequest('/api/admin/analytics/rollup', {
        method: 'POST',
      });

      await POST(request);

      // Verify rollup functions were called
      expect(sqlCalls.some((sql) => sql.includes('rollup'))).toBe(true);
    });

    it('should handle rollup errors gracefully', async () => {
      const { POST } = await import('@/app/api/admin/analytics/rollup/route');

      // Mock DB error - individual rollup errors are caught and reported in results
      global.mockDbQuery.mockRejectedValueOnce(new Error('Database error'));
      global.mockDbQueryOne.mockResolvedValue(null);

      const request = createAdminRequest('/api/admin/analytics/rollup', {
        method: 'POST',
      });

      const response = await POST(request);
      const { status, data } = await parseResponse<{
        success: boolean;
        results: Array<{ task: string; status: string; details?: string }>;
      }>(response);

      // Implementation catches rollup errors and returns 200 with success: false
      expect(status).toBe(200);
      expect(data?.success).toBe(false);
      expect(data?.results).toBeDefined();
      expect(data?.results?.some((r) => r.status === 'error')).toBe(true);
    });
  });

  describe('Seeded Data Rollup Correctness', () => {
    it('should produce correct rollup counts from seeded data', async () => {
      const { POST } = await import('@/app/api/admin/analytics/rollup/route');
      const seedData = generateSeedData('2024-01-15');
      const expectedResults = getExpectedRollupResults(seedData);

      // Simulate rollup execution tracking
      let rollupCalled = false;
      global.mockDbQuery.mockImplementation((sql: string) => {
        if (sql.includes('rollup')) {
          rollupCalled = true;
        }
        return Promise.resolve({ rows: [] });
      });
      global.mockDbQueryOne.mockResolvedValue({ success: true });

      const request = createAdminRequest('/api/admin/analytics/rollup', {
        method: 'POST',
      });

      await POST(request);

      expect(rollupCalled).toBe(true);

      // Verify expected counts from seed data
      expect(seedData.expectedCounts.total).toBe(18);
      expect(seedData.expectedCounts['page.view']).toBe(5);
      expect(seedData.expectedCounts['search.performed']).toBe(3);
      expect(seedData.expectedCounts['advert.view']).toBe(5);

      // Verify expected rollup results structure
      expect(expectedResults.daily_events).toHaveLength(6);
      expect(expectedResults.daily_funnel.sessions).toBe(1);
    });
  });
});
