/**
 * Next.js Middleware for SEO Redirects and Legacy URL Handling
 *
 * RUNS ON EDGE RUNTIME - NO DATABASE ACCESS ALLOWED
 *
 * Handles:
 * 1. Canonical host enforcement (www -> non-www)
 * 2. Legacy Wix URL redirects (/post/*, /items/*, /advert/*-n)
 * 3. Top-level page renames (/latestads -> /latest, /searchall -> /search)
 * 4. Query parameter cleanup (remove ?lightbox=)
 * 5. Slug normalization (unicode, dashes, etc.)
 *
 * IMPORTANT: For URLs requiring DB lookup (/items/*, /post/*),
 * we REWRITE to /api/legacy-redirect which runs on Node.js runtime.
 * The API route returns the 301 redirect to the browser.
 *
 * All redirects are 301 (permanent) for SEO equity transfer.
 */

import { NextRequest, NextResponse } from 'next/server';

// Canonical host configuration
const CANONICAL_HOST = 'tellyads.com';
const CANONICAL_PROTOCOL = 'https';

// Static redirect patterns - no DB lookup needed
const STATIC_REDIRECTS: Record<string, string> = {
  // Legacy page renames
  '/latestads': '/latest',
  '/searchall': '/search',
  '/telly-ads': '/',
  '/adsbydecade': '/browse',
  '/top30ads': '/browse',
  '/submit-a-ad': '/about',
  '/copy-of-home': '/',
  '/category/all-products': '/browse',

  // Alternative spellings/typos
  '/ads': '/browse',
  '/adverts': '/browse',
  '/archive': '/browse',
  '/tv-ads': '/browse',
  '/latest-ads': '/latest',
  '/search-all': '/search',

  // Wix system pages
  '/_api': '/',
  '/_partials': '/',

  // Legacy Wix sitemaps → canonical sitemap
  // Google may request these for weeks/months after migration
  '/dynamic-advert-sitemap.xml': '/sitemap.xml',
  '/dynamic-advert___1-sitemap.xml': '/sitemap.xml',
  '/dynamic-advert___2-sitemap.xml': '/sitemap.xml',
  '/dynamic-items-sitemap.xml': '/sitemap.xml',
  '/dynamic-items___1-sitemap.xml': '/sitemap.xml',
  '/dynamic-items___2-sitemap.xml': '/sitemap.xml',
  '/pages-sitemap.xml': '/sitemap.xml',
  '/sitemap_index.xml': '/sitemap.xml',
};

// Query parameters to strip (Wix artifacts)
const STRIP_PARAMS = ['lightbox', 'd', 'wix-vod-video-id'];

/**
 * Normalize a slug for matching
 * Handles unicode variants, repeated hyphens, etc.
 */
function normalizeSlug(slug: string): string {
  return slug
    // Decode URI components
    .replace(/%26/g, '&')
    .replace(/%27/g, "'")
    .replace(/%2C/g, ',')
    .replace(/%3F/g, '?')
    .replace(/%21/g, '!')
    // Normalize unicode dashes to ASCII hyphen
    .replace(/[\u2010-\u2015\u2212\uFE58\uFE63\uFF0D]/g, '-')
    // Normalize unicode apostrophes/quotes
    .replace(/[\u2018\u2019\u201A\u201B\u0060\u00B4]/g, "'")
    .replace(/[\u201C\u201D\u201E\u201F]/g, '"')
    // Collapse multiple hyphens
    .replace(/-{2,}/g, '-')
    // Remove leading/trailing hyphens
    .replace(/^-+|-+$/g, '')
    // Lowercase for consistency
    .toLowerCase();
}

export function middleware(request: NextRequest) {
  const { pathname, searchParams, host, protocol } = request.nextUrl;
  const url = request.nextUrl.clone();

  // 0. CANONICAL HOST REDIRECT (www -> non-www)
  // This MUST be first to prevent duplicate content
  const currentHost = host.replace(/:\d+$/, ''); // Remove port if present
  if (currentHost.startsWith('www.')) {
    const canonicalUrl = new URL(request.url);
    canonicalUrl.host = currentHost.replace(/^www\./, '');
    canonicalUrl.protocol = CANONICAL_PROTOCOL;
    return NextResponse.redirect(canonicalUrl.toString(), 301);
  }

  // 1. Strip Wix query parameters if present
  let paramsModified = false;
  for (const param of STRIP_PARAMS) {
    if (searchParams.has(param)) {
      searchParams.delete(param);
      paramsModified = true;
    }
  }

  if (paramsModified) {
    url.search = searchParams.toString();
    return NextResponse.redirect(url, 301);
  }

  // 2. Check static redirects first (case-insensitive)
  const lowercasePath = pathname.toLowerCase();
  if (STATIC_REDIRECTS[lowercasePath]) {
    return NextResponse.redirect(
      new URL(STATIC_REDIRECTS[lowercasePath], request.url),
      301
    );
  }

  // 3. Handle legacy /items/{slug} URLs
  // These need DB lookup to find the brand - REWRITE to API (not redirect)
  // The API route will return the 301 redirect
  if (pathname.startsWith('/items/')) {
    const slug = pathname.replace('/items/', '');
    if (slug) {
      const normalizedSlug = normalizeSlug(slug);
      return NextResponse.rewrite(
        new URL(`/api/legacy-redirect?type=items&slug=${encodeURIComponent(normalizedSlug)}`, request.url)
      );
    }
  }

  // 4. Handle /advert/{brand}/{slug}-n URLs (strip -n suffix)
  // Also handle slug normalization for /advert/* URLs
  if (pathname.startsWith('/advert/')) {
    const parts = pathname.split('/').filter(Boolean); // ['advert', brand, slug]
    if (parts.length >= 3) {
      const brand = parts[1];
      let slug = parts.slice(2).join('/'); // Handle potential nested paths

      // Check for -n suffix
      const hasNSuffix = slug.endsWith('-n');
      if (hasNSuffix) {
        slug = slug.slice(0, -2);
      }

      // Normalize the slug
      const normalizedBrand = normalizeSlug(brand);
      const normalizedSlug = normalizeSlug(slug);

      // If anything changed, redirect to normalized URL
      if (hasNSuffix || brand !== normalizedBrand || slug !== normalizedSlug) {
        return NextResponse.redirect(
          new URL(`/advert/${normalizedBrand}/${normalizedSlug}`, request.url),
          301
        );
      }
    }
  }

  // 5. Handle legacy Wix URLs - patterns like /post/brand-product-year
  // REWRITE to API route (Node.js runtime) for DB lookup
  if (pathname.startsWith('/post/')) {
    const slug = pathname.replace('/post/', '');
    const normalizedSlug = normalizeSlug(slug);
    return NextResponse.rewrite(
      new URL(`/api/legacy-redirect?type=post&slug=${encodeURIComponent(normalizedSlug)}`, request.url)
    );
  }

  // 6. Handle legacy /ads/{external_id} URLs
  // These pages exist but should redirect to canonical /advert/{brand}/{slug}
  if (pathname.match(/^\/ads\/[a-zA-Z0-9_-]+$/)) {
    const externalId = pathname.replace('/ads/', '');
    return NextResponse.rewrite(
      new URL(`/api/legacy-redirect?type=external_id&id=${encodeURIComponent(externalId)}`, request.url)
    );
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // Match ALL requests for canonical host check
    // Except static files and API routes
    '/((?!api|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt|.*\\.(?:png|jpg|jpeg|gif|svg|ico|webp)).*)',
  ],
};
