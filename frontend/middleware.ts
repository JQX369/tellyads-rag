/**
 * Next.js Middleware for Legacy URL Redirects
 *
 * Handles redirects from old Wix URLs to new canonical URLs.
 * Legacy URLs are matched by slug patterns via API route.
 */

import { NextRequest, NextResponse } from 'next/server';

// Static redirect patterns (no DB lookup needed)
const STATIC_REDIRECTS: Record<string, string> = {
  '/ads': '/browse',
  '/adverts': '/browse',
  '/archive': '/browse',
  '/tv-ads': '/browse',
};

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Check static redirects first
  if (STATIC_REDIRECTS[pathname]) {
    return NextResponse.redirect(
      new URL(STATIC_REDIRECTS[pathname], request.url),
      301 // Permanent redirect for SEO
    );
  }

  // Handle legacy Wix URLs - patterns like /post/brand-product-year
  // These need dynamic lookup via API route
  if (pathname.startsWith('/post/')) {
    const slug = pathname.replace('/post/', '');
    // Redirect to legacy lookup API which will 301 redirect to canonical
    return NextResponse.rewrite(
      new URL(`/api/legacy-redirect?path=${encodeURIComponent(pathname)}`, request.url)
    );
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // Match legacy URL patterns
    '/ads',
    '/adverts',
    '/archive',
    '/tv-ads',
    '/post/:path*',
    // Add other legacy patterns as needed
  ],
};
