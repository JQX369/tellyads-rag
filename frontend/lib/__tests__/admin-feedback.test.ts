/**
 * Tests for Admin Feedback API routes
 *
 * Tests cover:
 * 1. Authentication requirements
 * 2. GET /api/admin/feedback - Leaderboard and stats
 * 3. POST /api/admin/feedback - Refresh metrics
 * 4. GET /api/admin/feedback/weights - Weight configs
 * 5. PUT /api/admin/feedback/weights - Update weights
 * 6. GET /api/admin/feedback/reviews - Review moderation
 * 7. POST /api/admin/feedback/reviews - Approve/reject reviews
 */

import { createMockRequest } from './mock-request';

// Mock the database module
jest.mock('../db', () => ({
  query: jest.fn(),
  queryOne: jest.fn(),
  queryAll: jest.fn(),
}));

// Mock admin-auth module
jest.mock('../admin-auth', () => ({
  verifyAdminKey: jest.fn(),
}));

import { query, queryAll, queryOne } from '../db';
import { verifyAdminKey } from '../admin-auth';

const mockQuery = query as jest.Mock;
const mockQueryAll = queryAll as jest.Mock;
const mockQueryOne = queryOne as jest.Mock;
const mockVerifyAdminKey = verifyAdminKey as jest.Mock;

describe('Admin Feedback API', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Authentication', () => {
    it('should reject requests without admin key', async () => {
      mockVerifyAdminKey.mockReturnValue({ verified: false, error: 'X-Admin-Key header required' });

      const { GET } = await import('../../app/api/admin/feedback/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/feedback',
      });

      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(401);
      expect(data.error).toBe('X-Admin-Key header required');
    });

    it('should reject POST requests without admin key', async () => {
      mockVerifyAdminKey.mockReturnValue({ verified: false, error: 'X-Admin-Key header required' });

      const { POST } = await import('../../app/api/admin/feedback/route');

      const request = createMockRequest({
        method: 'POST',
        url: 'http://localhost/api/admin/feedback',
        body: { action: 'refresh' },
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(401);
      expect(data.error).toBe('X-Admin-Key header required');
    });
  });

  describe('GET /api/admin/feedback', () => {
    beforeEach(() => {
      mockVerifyAdminKey.mockReturnValue({ verified: true });
    });

    it('should return leaderboard, stats, and pending reviews', async () => {
      const mockLeaderboard = [
        { ad_id: 'ad-1', title: 'Test Ad', weighted_score: 85.5, total_views: 100 },
      ];
      const mockPendingReviews = [
        { id: 'review-1', ad_id: 'ad-1', rating: 5, review_text: 'Great ad!' },
      ];
      const mockStats = {
        total_ads: 50,
        ads_with_views: 30,
        total_views: 1000,
        avg_rating: 4.2,
      };
      const mockConfig = {
        config_key: 'default',
        weight_views: 1.0,
        weight_likes: 2.0,
      };

      mockQueryAll
        .mockResolvedValueOnce(mockLeaderboard) // leaderboard
        .mockResolvedValueOnce(mockPendingReviews); // pending reviews
      mockQueryOne
        .mockResolvedValueOnce(mockStats) // stats
        .mockResolvedValueOnce(mockConfig); // config

      const { GET } = await import('../../app/api/admin/feedback/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/feedback',
        headers: { 'x-admin-key': 'valid-key' },
      });

      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.leaderboard).toEqual(mockLeaderboard);
      expect(data.pendingReviews).toEqual(mockPendingReviews);
      expect(data.stats).toEqual(mockStats);
      expect(data.config).toEqual(mockConfig);
    });

    it('should respect limit parameter', async () => {
      mockQueryAll.mockResolvedValue([]);
      mockQueryOne.mockResolvedValue(null);

      const { GET } = await import('../../app/api/admin/feedback/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/feedback',
        headers: { 'x-admin-key': 'valid-key' },
        searchParams: { limit: '25' },
      });

      await GET(request);

      const leaderboardQuery = mockQueryAll.mock.calls[0];
      expect(leaderboardQuery[1]).toEqual([25]);
    });

    it('should cap limit at 200', async () => {
      mockQueryAll.mockResolvedValue([]);
      mockQueryOne.mockResolvedValue(null);

      const { GET } = await import('../../app/api/admin/feedback/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/feedback',
        headers: { 'x-admin-key': 'valid-key' },
        searchParams: { limit: '500' },
      });

      await GET(request);

      const leaderboardQuery = mockQueryAll.mock.calls[0];
      expect(leaderboardQuery[1]).toEqual([200]);
    });
  });

  describe('POST /api/admin/feedback', () => {
    beforeEach(() => {
      mockVerifyAdminKey.mockReturnValue({ verified: true });
    });

    it('should refresh all metrics with action=refresh', async () => {
      mockQueryOne.mockResolvedValue({ refresh_ad_feedback_agg: 50 });

      const { POST } = await import('../../app/api/admin/feedback/route');

      const request = createMockRequest({
        method: 'POST',
        url: 'http://localhost/api/admin/feedback',
        headers: { 'x-admin-key': 'valid-key' },
        body: { action: 'refresh' },
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.updated).toBe(50);
      expect(data.message).toContain('Refreshed all feedback metrics');
    });

    it('should refresh single ad metrics when ad_id provided', async () => {
      mockQueryOne.mockResolvedValue({ refresh_ad_feedback_agg: 1 });

      const { POST } = await import('../../app/api/admin/feedback/route');

      const request = createMockRequest({
        method: 'POST',
        url: 'http://localhost/api/admin/feedback',
        headers: { 'x-admin-key': 'valid-key' },
        body: { action: 'refresh', ad_id: 'ad-123' },
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.message).toContain('ad-123');
    });

    it('should reject invalid action', async () => {
      const { POST } = await import('../../app/api/admin/feedback/route');

      const request = createMockRequest({
        method: 'POST',
        url: 'http://localhost/api/admin/feedback',
        headers: { 'x-admin-key': 'valid-key' },
        body: { action: 'invalid-action' },
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe('Invalid action');
    });
  });
});

describe('Admin Feedback Weights API', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('GET /api/admin/feedback/weights', () => {
    beforeEach(() => {
      mockVerifyAdminKey.mockReturnValue({ verified: true });
    });

    it('should return all weight configs', async () => {
      const mockConfigs = [
        {
          id: 'config-1',
          config_key: 'default',
          name: 'Default Config',
          is_active: true,
          weight_views: 1.0,
          weight_likes: 2.0,
        },
        {
          id: 'config-2',
          config_key: 'experimental',
          name: 'Experimental',
          is_active: false,
          weight_views: 0.5,
          weight_likes: 3.0,
        },
      ];

      mockQueryAll.mockResolvedValue(mockConfigs);

      const { GET } = await import('../../app/api/admin/feedback/weights/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/feedback/weights',
        headers: { 'x-admin-key': 'valid-key' },
      });

      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.configs).toEqual(mockConfigs);
    });
  });

  describe('PUT /api/admin/feedback/weights', () => {
    beforeEach(() => {
      mockVerifyAdminKey.mockReturnValue({ verified: true });
    });

    it('should update weight config', async () => {
      const updatedConfig = {
        id: 'config-1',
        config_key: 'default',
        weight_views: 1.5,
        weight_likes: 2.5,
      };

      mockQueryOne.mockResolvedValue(updatedConfig);

      const { PUT } = await import('../../app/api/admin/feedback/weights/route');

      const request = createMockRequest({
        method: 'PUT',
        url: 'http://localhost/api/admin/feedback/weights',
        headers: { 'x-admin-key': 'valid-key' },
        body: { config_key: 'default', weight_views: 1.5, weight_likes: 2.5 },
      });

      const response = await PUT(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.config).toEqual(updatedConfig);
    });

    it('should reject weight values outside 0-10 range', async () => {
      const { PUT } = await import('../../app/api/admin/feedback/weights/route');

      const request = createMockRequest({
        method: 'PUT',
        url: 'http://localhost/api/admin/feedback/weights',
        headers: { 'x-admin-key': 'valid-key' },
        body: { config_key: 'default', weight_views: 15 },
      });

      const response = await PUT(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toContain('weight_views must be between 0 and 10');
    });

    it('should reject negative weight values', async () => {
      const { PUT } = await import('../../app/api/admin/feedback/weights/route');

      const request = createMockRequest({
        method: 'PUT',
        url: 'http://localhost/api/admin/feedback/weights',
        headers: { 'x-admin-key': 'valid-key' },
        body: { config_key: 'default', weight_likes: -1 },
      });

      const response = await PUT(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toContain('weight_likes must be between 0 and 10');
    });

    it('should return 404 if config not found', async () => {
      mockQueryOne.mockResolvedValue(null);

      const { PUT } = await import('../../app/api/admin/feedback/weights/route');

      const request = createMockRequest({
        method: 'PUT',
        url: 'http://localhost/api/admin/feedback/weights',
        headers: { 'x-admin-key': 'valid-key' },
        body: { config_key: 'nonexistent', weight_views: 1.0 },
      });

      const response = await PUT(request);
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data.error).toBe('Config not found');
    });
  });
});

describe('Admin Feedback Reviews API', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('GET /api/admin/feedback/reviews', () => {
    beforeEach(() => {
      mockVerifyAdminKey.mockReturnValue({ verified: true });
    });

    it('should return pending reviews by default', async () => {
      const mockReviews = [
        {
          id: 'review-1',
          ad_id: 'ad-1',
          rating: 5,
          review_text: 'Great ad!',
          status: 'pending',
          external_id: 'TA001',
          brand: 'Test Brand',
        },
      ];
      const mockCount = { count: '1' };
      const mockStatusCounts = [
        { status: 'pending', count: '3' },
        { status: 'approved', count: '10' },
        { status: 'rejected', count: '2' },
      ];

      mockQueryAll
        .mockResolvedValueOnce(mockReviews) // reviews
        .mockResolvedValueOnce(mockStatusCounts); // status counts
      mockQueryOne.mockResolvedValue(mockCount);

      const { GET } = await import('../../app/api/admin/feedback/reviews/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/feedback/reviews',
        headers: { 'x-admin-key': 'valid-key' },
      });

      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.reviews).toEqual(mockReviews);
      expect(data.total).toBe(1);
      expect(data.statusCounts).toEqual({
        pending: 3,
        approved: 10,
        rejected: 2,
      });
    });

    it('should filter by status', async () => {
      mockQueryAll.mockResolvedValue([]);
      mockQueryOne.mockResolvedValue({ count: '0' });

      const { GET } = await import('../../app/api/admin/feedback/reviews/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/feedback/reviews',
        headers: { 'x-admin-key': 'valid-key' },
        searchParams: { status: 'approved' },
      });

      await GET(request);

      const reviewsQuery = mockQueryAll.mock.calls[0];
      expect(reviewsQuery[1]).toContain('approved');
    });

    it('should respect pagination parameters', async () => {
      mockQueryAll.mockResolvedValue([]);
      mockQueryOne.mockResolvedValue({ count: '0' });

      const { GET } = await import('../../app/api/admin/feedback/reviews/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/feedback/reviews',
        headers: { 'x-admin-key': 'valid-key' },
        searchParams: { limit: '25', offset: '50' },
      });

      const response = await GET(request);
      const data = await response.json();

      expect(data.limit).toBe(25);
      expect(data.offset).toBe(50);
    });
  });

  describe('POST /api/admin/feedback/reviews', () => {
    beforeEach(() => {
      mockVerifyAdminKey.mockReturnValue({ verified: true });
    });

    it('should approve a review', async () => {
      mockQueryOne
        .mockResolvedValueOnce({ id: 'review-1', status: 'approved' }) // update result
        .mockResolvedValueOnce({ ad_id: 'ad-1' }); // get ad_id for refresh
      mockQuery.mockResolvedValue({ rows: [] }); // refresh call

      const { POST } = await import('../../app/api/admin/feedback/reviews/route');

      const request = createMockRequest({
        method: 'POST',
        url: 'http://localhost/api/admin/feedback/reviews',
        headers: { 'x-admin-key': 'valid-key' },
        body: { review_id: 'review-1', action: 'approve' },
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.new_status).toBe('approved');
    });

    it('should reject a review', async () => {
      mockQueryOne.mockResolvedValue({ id: 'review-1', status: 'rejected' });

      const { POST } = await import('../../app/api/admin/feedback/reviews/route');

      const request = createMockRequest({
        method: 'POST',
        url: 'http://localhost/api/admin/feedback/reviews',
        headers: { 'x-admin-key': 'valid-key' },
        body: { review_id: 'review-1', action: 'reject' },
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.new_status).toBe('rejected');
    });

    it('should flag a review', async () => {
      mockQueryOne.mockResolvedValue({ id: 'review-1', status: 'flagged' });

      const { POST } = await import('../../app/api/admin/feedback/reviews/route');

      const request = createMockRequest({
        method: 'POST',
        url: 'http://localhost/api/admin/feedback/reviews',
        headers: { 'x-admin-key': 'valid-key' },
        body: { review_id: 'review-1', action: 'flag' },
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.new_status).toBe('flagged');
    });

    it('should require review_id', async () => {
      const { POST } = await import('../../app/api/admin/feedback/reviews/route');

      const request = createMockRequest({
        method: 'POST',
        url: 'http://localhost/api/admin/feedback/reviews',
        headers: { 'x-admin-key': 'valid-key' },
        body: { action: 'approve' },
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toBe('review_id is required');
    });

    it('should reject invalid action', async () => {
      const { POST } = await import('../../app/api/admin/feedback/reviews/route');

      const request = createMockRequest({
        method: 'POST',
        url: 'http://localhost/api/admin/feedback/reviews',
        headers: { 'x-admin-key': 'valid-key' },
        body: { review_id: 'review-1', action: 'invalid' },
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toContain('action must be');
    });

    it('should return 404 if review not found', async () => {
      mockQueryOne.mockResolvedValue(null);

      const { POST } = await import('../../app/api/admin/feedback/reviews/route');

      const request = createMockRequest({
        method: 'POST',
        url: 'http://localhost/api/admin/feedback/reviews',
        headers: { 'x-admin-key': 'valid-key' },
        body: { review_id: 'nonexistent', action: 'approve' },
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data.error).toBe('Review not found');
    });
  });
});
