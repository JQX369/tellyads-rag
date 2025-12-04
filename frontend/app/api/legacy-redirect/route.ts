/**
 * Legacy URL Redirect API Route Handler
 *
 * GET /api/legacy-redirect?path=/post/brand-product-year
 *
 * Matches legacy Wix URLs by slug patterns and returns a 301 redirect
 * to the canonical URL.
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryOne, PUBLISH_GATE_CONDITION } from '@/lib/db';

export const runtime = 'nodejs';

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://tellyads.com';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const legacyPath = searchParams.get('path');

  if (!legacyPath) {
    return NextResponse.json(
      { error: 'path parameter required' },
      { status: 400 }
    );
  }

  try {
    const normalizedPath = legacyPath.startsWith('/') ? legacyPath : `/${legacyPath}`;

    // Extract slug from legacy URL pattern: /post/brand-product-year
    const slugFromPath = normalizedPath
      .replace('/post/', '')
      .replace(/^\//, '')
      .toLowerCase();

    // Try exact slug match first
    const exactMatch = await queryOne(
      `
      SELECT
        e.brand_slug,
        e.slug
      FROM ad_editorial e
      WHERE e.slug = $1
        AND ${PUBLISH_GATE_CONDITION}
      LIMIT 1
      `,
      [slugFromPath]
    );

    if (exactMatch) {
      const canonicalUrl = `${BASE_URL}/advert/${exactMatch.brand_slug}/${exactMatch.slug}`;
      return NextResponse.redirect(canonicalUrl, 301);
    }

    // Try fuzzy matching by slug
    const fuzzyMatch = await queryOne(
      `
      SELECT
        e.brand_slug,
        e.slug
      FROM ad_editorial e
      WHERE e.slug ILIKE $1
        AND ${PUBLISH_GATE_CONDITION}
      LIMIT 1
      `,
      [`%${slugFromPath}%`]
    );

    if (fuzzyMatch) {
      const canonicalUrl = `${BASE_URL}/advert/${fuzzyMatch.brand_slug}/${fuzzyMatch.slug}`;
      return NextResponse.redirect(canonicalUrl, 301);
    }

    // No match found - redirect to search with the slug as query
    const searchUrl = `${BASE_URL}/search?q=${encodeURIComponent(slugFromPath.replace(/-/g, ' '))}`;
    return NextResponse.redirect(searchUrl, 302);

  } catch (error) {
    console.error('Legacy redirect error:', error);
    // On error, redirect to home
    return NextResponse.redirect(BASE_URL, 302);
  }
}
