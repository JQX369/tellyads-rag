/**
 * Admin Analytics API Schema Tests
 *
 * Verifies that admin analytics endpoints return correct schema
 * and handle empty datasets gracefully.
 */

import { createAdminRequest, parseResponse } from './helpers/mock-request';

describe('Admin Analytics API Schema', () => {
  describe('GET /api/admin/analytics/overview', () => {
    it('should return expected schema with zeros when tables do not exist', async () => {
      const { GET } = await import('@/app/api/admin/analytics/overview/route');

      // Mock: tables do not exist
      global.mockDbQueryOne.mockResolvedValueOnce({ exists: false });

      const request = createAdminRequest('/api/admin/analytics/overview');
      const response = await GET(request);
      const { status, data } = await parseResponse<Record<string, unknown>>(response);

      expect(status).toBe(200);
      expect(data).toMatchObject({
        events_today: 0,
        sessions_today: 0,
        pageviews_today: 0,
        searches_today: 0,
        pageviews_7d: 0,
        sessions_7d: 0,
        searches_7d: 0,
        ad_views_7d: 0,
        pageviews_trend: null,
        sessions_trend: null,
        searches_trend: null,
        avg_search_rate: null,
        avg_view_rate: null,
        avg_engagement_rate: null,
        // Observability metrics
        capture_error_count: expect.any(Number),
        capture_error_rate_pct: expect.any(Number),
        capture_events_24h: expect.any(Number),
        capture_last_error: expect.toBeOneOf([null, expect.any(String)]),
      });
    });

    it('should return data when tables exist and have data', async () => {
      const { GET } = await import('@/app/api/admin/analytics/overview/route');

      // Mock: tables exist
      global.mockDbQueryOne
        .mockResolvedValueOnce({ exists: true }) // analytics_events exists
        .mockResolvedValueOnce({
          // today metrics
          events_today: 100,
          sessions_today: 25,
          pageviews_today: 50,
          searches_today: 10,
        })
        .mockResolvedValueOnce({ exists: true }) // rollup tables exist
        .mockResolvedValueOnce({
          // 7d metrics
          pageviews_7d: 350,
          sessions_7d: 100,
          searches_7d: 50,
          ad_views_7d: 200,
        })
        .mockResolvedValueOnce({
          // prev 7d metrics
          pageviews_prev: 300,
          sessions_prev: 90,
          searches_prev: 40,
        })
        .mockResolvedValueOnce({ exists: false }); // funnel table doesn't exist

      const request = createAdminRequest('/api/admin/analytics/overview');
      const response = await GET(request);
      const { status, data } = await parseResponse<Record<string, unknown>>(response);

      expect(status).toBe(200);
      expect(data).toHaveProperty('events_today', 100);
      expect(data).toHaveProperty('sessions_today', 25);
      expect(data).toHaveProperty('pageviews_7d', 350);
    });
  });

  describe('GET /api/admin/analytics/search', () => {
    it('should return expected schema with empty arrays', async () => {
      const { GET } = await import('@/app/api/admin/analytics/search/route');

      // Mock: tables don't exist
      global.mockDbQueryOne.mockResolvedValueOnce({ exists: false });

      const request = createAdminRequest('/api/admin/analytics/search', {
        searchParams: { days: '7' },
      });
      const response = await GET(request);
      const { status, data } = await parseResponse<Record<string, unknown>>(response);

      expect(status).toBe(200);
      // Route returns: top_queries, zero_result_queries, total_searches, unique_queries, zero_result_rate
      expect(data).toHaveProperty('top_queries');
      expect(data).toHaveProperty('zero_result_queries');
      expect(data).toHaveProperty('total_searches');
      expect(Array.isArray(data?.top_queries)).toBe(true);
      expect(Array.isArray(data?.zero_result_queries)).toBe(true);
    });

    it('should return search data when available', async () => {
      const { GET } = await import('@/app/api/admin/analytics/search/route');

      // Mock: tables exist with data
      global.mockDbQueryOne.mockResolvedValueOnce({ exists: true });
      global.mockDbQueryAll
        .mockResolvedValueOnce([
          // top queries
          { query: 'test query', count: 50, click_rate: 0.25 },
        ])
        .mockResolvedValueOnce([
          // zero result queries
          { query: 'no results', count: 10 },
        ])
        .mockResolvedValueOnce([
          // search volume
          { date: '2024-01-15', count: 100 },
        ]);

      const request = createAdminRequest('/api/admin/analytics/search', {
        searchParams: { days: '7' },
      });
      const response = await GET(request);
      const { status, data } = await parseResponse<Record<string, unknown>>(response);

      expect(status).toBe(200);
      expect(Array.isArray(data?.top_queries)).toBe(true);
    });
  });

  describe('GET /api/admin/analytics/seo', () => {
    beforeEach(() => {
      // Ensure clean mock state
      jest.clearAllMocks();
    });

    it('should return expected schema for SEO hygiene', async () => {
      const { GET } = await import('@/app/api/admin/analytics/seo/route');

      // Mock: SEO tables don't exist, fallback to main table
      global.mockDbQueryOne.mockResolvedValueOnce({ exists: false });
      global.mockDbQueryAll
        .mockResolvedValueOnce([]) // fallback 404s
        .mockResolvedValueOnce([]); // fallback redirects

      const request = createAdminRequest('/api/admin/analytics/seo', {
        searchParams: { days: '7' },
      });
      const response = await GET(request);
      const { status, data } = await parseResponse<Record<string, unknown>>(response);

      expect(status).toBe(200);
      expect(data).toHaveProperty('top_404s');
      expect(data).toHaveProperty('legacy_redirects');
      expect(data).toHaveProperty('total_404s_7d');
      expect(data).toHaveProperty('total_redirects_7d');
      expect(Array.isArray(data?.top_404s)).toBe(true);
      expect(Array.isArray(data?.legacy_redirects)).toBe(true);
    });

    it('should return SEO data from dedicated table when available', async () => {
      const { GET } = await import('@/app/api/admin/analytics/seo/route');

      // Mock: SEO table exists
      global.mockDbQueryOne.mockResolvedValueOnce({ exists: true });
      global.mockDbQueryAll
        .mockResolvedValueOnce([
          // top 404s
          { path: '/missing-page', count: 100, last_seen: '2024-01-15', referrers: [] },
        ])
        .mockResolvedValueOnce([
          // legacy redirects
          { path: '/old/url', redirect_to: '/new/url', count: 50, last_seen: '2024-01-15' },
        ]);
      global.mockDbQueryOne.mockResolvedValueOnce({
        total_404s: 150,
        total_redirects: 75,
        unique_404_paths: 10,
      });

      const request = createAdminRequest('/api/admin/analytics/seo', {
        searchParams: { days: '7' },
      });
      const response = await GET(request);
      const { status, data } = await parseResponse<Record<string, unknown>>(response);

      expect(status).toBe(200);
      expect(Array.isArray(data?.top_404s)).toBe(true);
      expect(Array.isArray(data?.legacy_redirects)).toBe(true);
    });
  });

  describe('GET /api/admin/analytics/content-requests', () => {
    beforeEach(() => {
      // Ensure clean mock state
      jest.clearAllMocks();
    });

    it('should return expected schema for content requests', async () => {
      const { GET } = await import('@/app/api/admin/analytics/content-requests/route');

      // Mock: table doesn't exist
      global.mockDbQueryOne.mockResolvedValueOnce({ exists: false });

      const request = createAdminRequest('/api/admin/analytics/content-requests');
      const response = await GET(request);
      const { status, data } = await parseResponse<Record<string, unknown>>(response);

      expect(status).toBe(200);
      // Route returns { requests: [], total: 0, message: '...' } when table doesn't exist
      expect(data).toHaveProperty('requests');
      expect(Array.isArray(data?.requests)).toBe(true);
      expect((data as { requests: unknown[] }).requests).toHaveLength(0);
    });

    it('should return content requests with counts when available', async () => {
      const { GET } = await import('@/app/api/admin/analytics/content-requests/route');

      // Mock: table exists
      global.mockDbQueryOne.mockResolvedValueOnce({ exists: true });
      global.mockDbQueryAll.mockResolvedValueOnce([
        {
          id: 'uuid-1',
          query: 'requested content',
          status: 'new',
          priority: 5,
          search_count: 10,
          notes: null,
          created_at: '2024-01-15',
          updated_at: '2024-01-15',
        },
      ]);
      global.mockDbQueryOne.mockResolvedValueOnce({
        total: 1,
        new_count: 1,
        queued_count: 0,
        in_progress_count: 0,
        done_count: 0,
        rejected_count: 0,
      });

      const request = createAdminRequest('/api/admin/analytics/content-requests');
      const response = await GET(request);
      const { status, data } = await parseResponse<Record<string, unknown>>(response);

      expect(status).toBe(200);
      expect(data).toHaveProperty('requests');
      expect(data).toHaveProperty('counts');
      expect((data as { counts: { total: number } }).counts.total).toBe(1);
    });
  });

  describe('GET /api/admin/analytics/content', () => {
    beforeEach(() => {
      // Ensure clean mock state
      jest.clearAllMocks();
    });

    it('should return expected schema for content analytics', async () => {
      const { GET } = await import('@/app/api/admin/analytics/content/route');

      // Mock: tables don't exist
      global.mockDbQueryOne.mockResolvedValueOnce({ exists: false });

      const request = createAdminRequest('/api/admin/analytics/content', {
        searchParams: { days: '7' },
      });
      const response = await GET(request);
      const { status, data } = await parseResponse<Record<string, unknown>>(response);

      expect(status).toBe(200);
      expect(data).toHaveProperty('top_ads');
      expect(data).toHaveProperty('top_brands');
      expect(Array.isArray(data?.top_ads)).toBe(true);
      expect(Array.isArray(data?.top_brands)).toBe(true);
    });
  });
});

// Custom matcher for nullable values
expect.extend({
  toBeOneOf(received: unknown, expected: unknown[]) {
    const pass = expected.some((exp) => {
      if (exp === null) return received === null;
      if (typeof exp === 'function') return exp(received);
      return received === exp;
    });
    return {
      pass,
      message: () => `expected ${received} to be one of ${expected}`,
    };
  },
});

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace jest {
    interface Matchers<R> {
      toBeOneOf(expected: unknown[]): R;
    }
  }
}
