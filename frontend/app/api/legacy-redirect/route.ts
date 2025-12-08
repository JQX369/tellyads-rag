/**
 * Legacy URL Redirect API Route Handler
 *
 * RUNS ON NODE.JS RUNTIME - HAS DATABASE ACCESS
 *
 * Handles multiple legacy URL patterns:
 *
 * GET /api/legacy-redirect?type=items&slug=ad-slug
 *   - Matches legacy /items/{slug} URLs from Wix store
 *
 * GET /api/legacy-redirect?type=post&slug=ad-slug
 *   - Matches legacy /post/{slug} URLs from Wix blog
 *
 * GET /api/legacy-redirect?type=external_id&id=abc123
 *   - Redirects /ads/{external_id} to canonical /advert/{brand}/{slug}
 *
 * Returns 301 redirect to canonical URL, or 302 to search on no match.
 *
 * CACHING: Results cached for 1 hour via Cache-Control header
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryOne, PUBLISH_GATE_CONDITION } from '@/lib/db';

export const runtime = 'nodejs';

// Use canonical host for all redirects
const CANONICAL_HOST = 'https://tellyads.com';

// In-memory LRU cache for redirect lookups
const redirectCache = new Map<string, { url: string; timestamp: number }>();
const CACHE_TTL = 60 * 60 * 1000; // 1 hour
const MAX_CACHE_SIZE = 10000;

function getCachedRedirect(key: string): string | null {
  const entry = redirectCache.get(key);
  if (entry && Date.now() - entry.timestamp < CACHE_TTL) {
    return entry.url;
  }
  if (entry) {
    redirectCache.delete(key);
  }
  return null;
}

function setCachedRedirect(key: string, url: string): void {
  // Simple LRU: delete oldest entries if cache is full
  if (redirectCache.size >= MAX_CACHE_SIZE) {
    const firstKey = redirectCache.keys().next().value;
    if (firstKey) redirectCache.delete(firstKey);
  }
  redirectCache.set(key, { url, timestamp: Date.now() });
}

/**
 * Normalize a slug for database matching
 */
function normalizeSlug(slug: string): string {
  return decodeURIComponent(slug)
    .toLowerCase()
    // Normalize quotes
    .replace(/[''`´]/g, "'")
    .replace(/[""]|&quot;/g, '"')
    // Normalize dashes
    .replace(/[\u2010-\u2015\u2212\uFE58\uFE63\uFF0D]/g, '-')
    // Collapse multiple hyphens
    .replace(/-{2,}/g, '-')
    // Remove -n suffix if present
    .replace(/-n$/, '')
    // Spaces to hyphens
    .replace(/\s+/g, '-')
    // Remove leading/trailing hyphens
    .replace(/^-+|-+$/g, '');
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const type = searchParams.get('type');
  const slug = searchParams.get('slug');
  const externalId = searchParams.get('id');

  // Legacy support for old ?path= parameter
  const legacyPath = searchParams.get('path');
  if (legacyPath) {
    const extractedSlug = legacyPath.replace(/^\/post\//, '').replace(/^\//, '');
    return handleSlugLookup(extractedSlug, 'post');
  }

  try {
    if (type === 'items' && slug) {
      return handleSlugLookup(slug, 'items');
    }

    if (type === 'post' && slug) {
      return handleSlugLookup(slug, 'post');
    }

    if (type === 'external_id' && externalId) {
      return handleExternalIdLookup(externalId);
    }

    return NextResponse.json(
      { error: 'Invalid request. Provide type with slug/id.' },
      { status: 400 }
    );
  } catch (error) {
    console.error('Legacy redirect error:', error);
    return createRedirectResponse(`${CANONICAL_HOST}/browse`, 302);
  }
}

/**
 * Handle /items/{slug} and /post/{slug} URLs
 * Both need to look up the ad by slug and find the canonical brand/slug
 */
async function handleSlugLookup(slug: string, source: 'items' | 'post'): Promise<NextResponse> {
  const normalizedSlug = normalizeSlug(slug);
  const cacheKey = `slug:${normalizedSlug}`;

  // Check cache first
  const cachedUrl = getCachedRedirect(cacheKey);
  if (cachedUrl) {
    return createRedirectResponse(cachedUrl, 301);
  }

  // Try exact slug match
  let match = await queryOne(
    `
    SELECT e.brand_slug, e.slug
    FROM ad_editorial e
    WHERE LOWER(e.slug) = $1
      AND ${PUBLISH_GATE_CONDITION}
    LIMIT 1
    `,
    [normalizedSlug]
  );

  // Try slug with common suffix patterns
  if (!match) {
    match = await queryOne(
      `
      SELECT e.brand_slug, e.slug
      FROM ad_editorial e
      WHERE (
        LOWER(e.slug) = $1
        OR LOWER(e.slug) LIKE $2
        OR LOWER(e.slug) LIKE $3
      )
      AND ${PUBLISH_GATE_CONDITION}
      ORDER BY
        CASE WHEN LOWER(e.slug) = $1 THEN 0 ELSE 1 END
      LIMIT 1
      `,
      [normalizedSlug, `${normalizedSlug}-%`, `%-${normalizedSlug}`]
    );
  }

  // Try fuzzy match on headline or product name
  if (!match) {
    const searchTerm = normalizedSlug.replace(/-/g, ' ');
    match = await queryOne(
      `
      SELECT e.brand_slug, e.slug
      FROM ad_editorial e
      JOIN ads a ON a.id = e.ad_id
      WHERE (
        LOWER(e.headline) LIKE $1
        OR LOWER(a.product_name) LIKE $1
        OR LOWER(a.one_line_summary) LIKE $1
      )
      AND ${PUBLISH_GATE_CONDITION}
      LIMIT 1
      `,
      [`%${searchTerm}%`]
    );
  }

  if (match) {
    const canonicalUrl = `${CANONICAL_HOST}/advert/${match.brand_slug}/${match.slug}`;
    setCachedRedirect(cacheKey, canonicalUrl);
    return createRedirectResponse(canonicalUrl, 301);
  }

  // No match - redirect to search (302 = temporary, so we can try again later)
  const searchUrl = `${CANONICAL_HOST}/search?q=${encodeURIComponent(slug.replace(/-/g, ' '))}`;
  return createRedirectResponse(searchUrl, 302);
}

/**
 * Handle /ads/{external_id} URLs
 */
async function handleExternalIdLookup(externalId: string): Promise<NextResponse> {
  const cacheKey = `ext:${externalId}`;

  // Check cache first
  const cachedUrl = getCachedRedirect(cacheKey);
  if (cachedUrl) {
    return createRedirectResponse(cachedUrl, 301);
  }

  const match = await queryOne(
    `
    SELECT e.brand_slug, e.slug
    FROM ad_editorial e
    JOIN ads a ON a.id = e.ad_id
    WHERE a.external_id = $1
      AND ${PUBLISH_GATE_CONDITION}
    LIMIT 1
    `,
    [externalId]
  );

  if (match) {
    const canonicalUrl = `${CANONICAL_HOST}/advert/${match.brand_slug}/${match.slug}`;
    setCachedRedirect(cacheKey, canonicalUrl);
    return createRedirectResponse(canonicalUrl, 301);
  }

  // Check if ad exists but isn't published
  const adExists = await queryOne(
    `SELECT external_id FROM ads WHERE external_id = $1 LIMIT 1`,
    [externalId]
  );

  if (adExists) {
    return createRedirectResponse(`${CANONICAL_HOST}/browse`, 302);
  }

  return createRedirectResponse(`${CANONICAL_HOST}/browse`, 302);
}

/**
 * Create a redirect response with appropriate caching headers
 */
function createRedirectResponse(url: string, status: 301 | 302): NextResponse {
  const response = NextResponse.redirect(url, status);

  // Add caching headers for CDN
  if (status === 301) {
    // Permanent redirects can be cached longer
    response.headers.set('Cache-Control', 'public, max-age=3600, s-maxage=86400');
  } else {
    // Temporary redirects shouldn't be cached as long
    response.headers.set('Cache-Control', 'public, max-age=60, s-maxage=300');
  }

  return response;
}
