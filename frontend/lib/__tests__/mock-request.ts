/**
 * Test helpers for mocking Next.js requests and responses
 */

import { NextRequest } from 'next/server';

/**
 * Create a mock NextRequest for testing API routes
 */
export function createMockRequest(options: {
  method?: string;
  url?: string;
  headers?: Record<string, string>;
  body?: unknown;
  searchParams?: Record<string, string>;
}): NextRequest {
  const { method = 'GET', url = 'http://localhost/api/test', headers = {}, body, searchParams = {} } = options;

  // Build URL with search params
  const urlObj = new URL(url);
  for (const [key, value] of Object.entries(searchParams)) {
    urlObj.searchParams.set(key, value);
  }

  // Create request options
  const init: RequestInit = {
    method,
    headers: new Headers(headers),
  };

  // Add body for non-GET requests
  if (body && method !== 'GET') {
    init.body = JSON.stringify(body);
    (init.headers as Headers).set('Content-Type', 'application/json');
  }

  return new NextRequest(urlObj.toString(), init);
}

/**
 * Create a mock form data request for file uploads
 */
export function createMockFormDataRequest(options: {
  url?: string;
  headers?: Record<string, string>;
  formData: FormData;
}): NextRequest {
  const { url = 'http://localhost/api/test', headers = {}, formData } = options;

  return new NextRequest(url, {
    method: 'POST',
    headers: new Headers(headers),
    body: formData,
  });
}
