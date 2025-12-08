/**
 * Analytics Test Setup
 *
 * Sets up mocks and environment for analytics tests.
 * This file is run before each test file in the analytics suite.
 */

// Set test environment
process.env.NODE_ENV = 'test';
process.env.ADMIN_API_KEY = 'test-admin-key-12345';
process.env.CRON_SECRET = 'test-cron-secret';

// Mock the database module
jest.mock('@/lib/db', () => ({
  query: jest.fn(),
  queryOne: jest.fn(),
  queryAll: jest.fn(),
}));

// Reset mocks between tests
beforeEach(() => {
  jest.clearAllMocks();
});

// Global test utilities
declare global {
  // eslint-disable-next-line no-var
  var mockDbQuery: jest.Mock;
  // eslint-disable-next-line no-var
  var mockDbQueryOne: jest.Mock;
  // eslint-disable-next-line no-var
  var mockDbQueryAll: jest.Mock;
}

// Export mock access
import { query, queryOne, queryAll } from '@/lib/db';
global.mockDbQuery = query as jest.Mock;
global.mockDbQueryOne = queryOne as jest.Mock;
global.mockDbQueryAll = queryAll as jest.Mock;
