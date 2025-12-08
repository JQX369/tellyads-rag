/**
 * Tests for Admin Catalog API routes
 *
 * Tests cover:
 * 1. Authentication requirements
 * 2. Query parameter handling
 * 3. Database query construction
 * 4. Response format
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

import { queryAll, queryOne } from '../db';
import { verifyAdminKey } from '../admin-auth';

const mockQueryAll = queryAll as jest.Mock;
const mockQueryOne = queryOne as jest.Mock;
const mockVerifyAdminKey = verifyAdminKey as jest.Mock;

describe('Admin Catalog API', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Authentication', () => {
    it('should reject requests without admin key', async () => {
      mockVerifyAdminKey.mockReturnValue({ verified: false, error: 'X-Admin-Key header required' });

      // Import route handler dynamically after mocking
      const { GET } = await import('../../app/api/admin/catalog/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/catalog',
      });

      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(401);
      expect(data.error).toBe('X-Admin-Key header required');
    });

    it('should reject requests with invalid admin key', async () => {
      mockVerifyAdminKey.mockReturnValue({ verified: false, error: 'Invalid admin key' });

      const { GET } = await import('../../app/api/admin/catalog/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/catalog',
        headers: { 'x-admin-key': 'wrong-key' },
      });

      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(401);
      expect(data.error).toBe('Invalid admin key');
    });

    it('should accept requests with valid admin key', async () => {
      mockVerifyAdminKey.mockReturnValue({ verified: true });
      mockQueryAll.mockResolvedValue([]);
      mockQueryOne.mockResolvedValue({ count: '0' });

      const { GET } = await import('../../app/api/admin/catalog/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/catalog',
        headers: { 'x-admin-key': 'valid-key' },
      });

      const response = await GET(request);

      expect(response.status).toBe(200);
    });
  });

  describe('GET /api/admin/catalog', () => {
    beforeEach(() => {
      mockVerifyAdminKey.mockReturnValue({ verified: true });
    });

    it('should return catalog entries with default pagination', async () => {
      const mockEntries = [
        {
          id: 'entry-1',
          external_id: 'TA001',
          brand_name: 'Test Brand',
          title: 'Test Ad',
          is_mapped: true,
          is_ingested: false,
        },
      ];

      mockQueryAll
        .mockResolvedValueOnce(mockEntries) // entries query
        .mockResolvedValueOnce([{ brand_name: 'Test Brand', count: 1 }]) // brands filter
        .mockResolvedValueOnce([{ decade: '2020s', count: 1 }]) // decades filter
        .mockResolvedValueOnce([{ country: 'USA', count: 1 }]); // countries filter

      mockQueryOne
        .mockResolvedValueOnce({ count: '1' }) // count query
        .mockResolvedValueOnce({ total_entries: 1 }); // summary query

      const { GET } = await import('../../app/api/admin/catalog/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/catalog',
        headers: { 'x-admin-key': 'valid-key' },
      });

      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.entries).toEqual(mockEntries);
      expect(data.total).toBe(1);
      expect(data.limit).toBe(50); // default limit
      expect(data.offset).toBe(0);
    });

    it('should apply filter=unmapped correctly', async () => {
      mockQueryAll.mockResolvedValue([]);
      mockQueryOne.mockResolvedValue({ count: '0' });

      const { GET } = await import('../../app/api/admin/catalog/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/catalog',
        headers: { 'x-admin-key': 'valid-key' },
        searchParams: { filter: 'unmapped' },
      });

      await GET(request);

      // Check that the unmapped filter was applied
      const entriesQuery = mockQueryAll.mock.calls[0][0];
      expect(entriesQuery).toContain('NOT is_mapped');
    });

    it('should apply filter=not_ingested correctly', async () => {
      mockQueryAll.mockResolvedValue([]);
      mockQueryOne.mockResolvedValue({ count: '0' });

      const { GET } = await import('../../app/api/admin/catalog/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/catalog',
        headers: { 'x-admin-key': 'valid-key' },
        searchParams: { filter: 'not_ingested' },
      });

      await GET(request);

      const entriesQuery = mockQueryAll.mock.calls[0][0];
      expect(entriesQuery).toContain('NOT is_ingested');
    });

    it('should apply filter=low_confidence correctly', async () => {
      mockQueryAll.mockResolvedValue([]);
      mockQueryOne.mockResolvedValue({ count: '0' });

      const { GET } = await import('../../app/api/admin/catalog/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/catalog',
        headers: { 'x-admin-key': 'valid-key' },
        searchParams: { filter: 'low_confidence' },
      });

      await GET(request);

      const entriesQuery = mockQueryAll.mock.calls[0][0];
      expect(entriesQuery).toContain('date_parse_confidence < 0.8');
    });

    it('should apply brand filter correctly', async () => {
      mockQueryAll.mockResolvedValue([]);
      mockQueryOne.mockResolvedValue({ count: '0' });

      const { GET } = await import('../../app/api/admin/catalog/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/catalog',
        headers: { 'x-admin-key': 'valid-key' },
        searchParams: { brand: 'Coca-Cola' },
      });

      await GET(request);

      const entriesParams = mockQueryAll.mock.calls[0][1];
      expect(entriesParams).toContain('%Coca-Cola%');
    });

    it('should respect limit and offset parameters', async () => {
      mockQueryAll.mockResolvedValue([]);
      mockQueryOne.mockResolvedValue({ count: '0' });

      const { GET } = await import('../../app/api/admin/catalog/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/catalog',
        headers: { 'x-admin-key': 'valid-key' },
        searchParams: { limit: '25', offset: '50' },
      });

      const response = await GET(request);
      const data = await response.json();

      expect(data.limit).toBe(25);
      expect(data.offset).toBe(50);
    });

    it('should cap limit at 200', async () => {
      mockQueryAll.mockResolvedValue([]);
      mockQueryOne.mockResolvedValue({ count: '0' });

      const { GET } = await import('../../app/api/admin/catalog/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/catalog',
        headers: { 'x-admin-key': 'valid-key' },
        searchParams: { limit: '500' },
      });

      const response = await GET(request);
      const data = await response.json();

      expect(data.limit).toBe(200);
    });
  });
});

describe('Admin Catalog Imports API', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('GET /api/admin/catalog/imports', () => {
    it('should return import jobs', async () => {
      mockVerifyAdminKey.mockReturnValue({ verified: true });

      const mockImports = [
        {
          id: 'import-1',
          original_filename: 'catalog.csv',
          status: 'SUCCEEDED',
          rows_total: 100,
          rows_ok: 98,
          rows_failed: 2,
        },
      ];

      mockQueryAll.mockResolvedValue(mockImports);

      const { GET } = await import('../../app/api/admin/catalog/imports/route');

      const request = createMockRequest({
        method: 'GET',
        url: 'http://localhost/api/admin/catalog/imports',
        headers: { 'x-admin-key': 'valid-key' },
      });

      const response = await GET(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.imports).toEqual(mockImports);
    });
  });
});

describe('Admin Catalog Enqueue API', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('POST /api/admin/catalog/enqueue', () => {
    it('should enqueue catalog entries for ingestion', async () => {
      mockVerifyAdminKey.mockReturnValue({ verified: true });

      const mockEntries = [
        { id: 'entry-1', external_id: 'TA001', s3_key: 'videos/TA001.mp4', video_url: null },
        { id: 'entry-2', external_id: 'TA002', s3_key: 'videos/TA002.mp4', video_url: null },
      ];

      mockQueryAll.mockResolvedValue(mockEntries);
      mockQueryOne.mockResolvedValue({ job_id: 'job-1', already_existed: false });

      const { POST } = await import('../../app/api/admin/catalog/enqueue/route');

      const request = createMockRequest({
        method: 'POST',
        url: 'http://localhost/api/admin/catalog/enqueue',
        headers: { 'x-admin-key': 'valid-key' },
        body: { catalog_ids: ['entry-1', 'entry-2'] },
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.success).toBe(true);
      expect(data.enqueued).toBe(2);
    });

    it('should skip already enqueued entries', async () => {
      mockVerifyAdminKey.mockReturnValue({ verified: true });

      const mockEntries = [
        { id: 'entry-1', external_id: 'TA001', s3_key: 'videos/TA001.mp4', video_url: null },
      ];

      mockQueryAll.mockResolvedValue(mockEntries);
      mockQueryOne.mockResolvedValue({ job_id: 'job-1', already_existed: true });

      const { POST } = await import('../../app/api/admin/catalog/enqueue/route');

      const request = createMockRequest({
        method: 'POST',
        url: 'http://localhost/api/admin/catalog/enqueue',
        headers: { 'x-admin-key': 'valid-key' },
        body: { catalog_ids: ['entry-1'] },
      });

      const response = await POST(request);
      const data = await response.json();

      expect(data.skipped).toBe(1);
      expect(data.enqueued).toBe(0);
    });

    it('should require catalog_ids or filter', async () => {
      mockVerifyAdminKey.mockReturnValue({ verified: true });

      const { POST } = await import('../../app/api/admin/catalog/enqueue/route');

      const request = createMockRequest({
        method: 'POST',
        url: 'http://localhost/api/admin/catalog/enqueue',
        headers: { 'x-admin-key': 'valid-key' },
        body: {},
      });

      const response = await POST(request);
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toContain('catalog_ids');
    });
  });
});
