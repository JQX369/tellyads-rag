/**
 * Mock Request Helper for API Route Testing
 *
 * Creates mock NextRequest objects for testing API routes.
 */

import { NextRequest } from 'next/server';

interface MockRequestOptions {
  method?: string;
  url?: string;
  headers?: Record<string, string>;
  body?: unknown;
  searchParams?: Record<string, string>;
}

/**
 * Create a mock NextRequest for testing
 */
export function createMockRequest(options: MockRequestOptions = {}): NextRequest {
  const {
    method = 'GET',
    url = 'http://localhost:3000/api/test',
    headers = {},
    body,
    searchParams = {},
  } = options;

  // Build URL with search params
  const urlObj = new URL(url);
  for (const [key, value] of Object.entries(searchParams)) {
    urlObj.searchParams.set(key, value);
  }

  // Create headers
  const headersList = new Headers();
  for (const [key, value] of Object.entries(headers)) {
    headersList.set(key, value);
  }

  // Create request init
  const init: RequestInit = {
    method,
    headers: headersList,
  };

  // Add body for non-GET requests
  if (body && method !== 'GET') {
    init.body = JSON.stringify(body);
    headersList.set('content-type', 'application/json');
  }

  // Create and return NextRequest
  return new NextRequest(urlObj.toString(), init);
}

/**
 * Create a mock capture request with proper headers
 */
export function createCaptureRequest(
  payload: unknown,
  options: {
    origin?: string;
    referer?: string;
  } = {}
): NextRequest {
  const headers: Record<string, string> = {
    'content-type': 'application/json',
  };

  if (options.origin) {
    headers['origin'] = options.origin;
  }

  if (options.referer) {
    headers['referer'] = options.referer;
  }

  return createMockRequest({
    method: 'POST',
    url: 'http://localhost:3000/api/analytics/capture',
    headers,
    body: payload,
  });
}

/**
 * Create a mock admin request with proper auth header
 */
export function createAdminRequest(
  endpoint: string,
  options: {
    method?: string;
    adminKey?: string;
    body?: unknown;
    searchParams?: Record<string, string>;
  } = {}
): NextRequest {
  const {
    method = 'GET',
    adminKey = 'test-admin-key-12345',
    body,
    searchParams = {},
  } = options;

  const headers: Record<string, string> = {};

  if (adminKey) {
    headers['x-admin-key'] = adminKey;
  }

  return createMockRequest({
    method,
    url: `http://localhost:3000${endpoint}`,
    headers,
    body,
    searchParams,
  });
}

/**
 * Create a mock cron request (Vercel cron)
 */
export function createCronRequest(
  endpoint: string,
  options: {
    cronSecret?: string;
    useCronHeader?: boolean;
  } = {}
): NextRequest {
  const { cronSecret, useCronHeader = false } = options;

  const headers: Record<string, string> = {};

  if (cronSecret) {
    headers['authorization'] = `Bearer ${cronSecret}`;
  }

  if (useCronHeader) {
    headers['x-vercel-cron'] = '1';
  }

  return createMockRequest({
    method: 'POST',
    url: `http://localhost:3000${endpoint}`,
    headers,
  });
}

/**
 * Parse JSON response from NextResponse
 */
export async function parseResponse<T = unknown>(response: Response): Promise<{
  status: number;
  data: T | null;
}> {
  const status = response.status;

  // Handle 204 No Content
  if (status === 204) {
    return { status, data: null };
  }

  try {
    const data = await response.json();
    return { status, data };
  } catch {
    return { status, data: null };
  }
}
