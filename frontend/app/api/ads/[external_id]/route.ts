/**
 * Ad Detail API Route Handler
 *
 * GET /api/ads/[external_id]
 *
 * Returns ad details by external_id.
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryOne, PUBLISH_GATE_CONDITION } from '@/lib/db';

export const runtime = 'nodejs';

interface RouteContext {
  params: Promise<{ external_id: string }>;
}

export async function GET(request: NextRequest, context: RouteContext) {
  const { external_id } = await context.params;

  if (!external_id) {
    return NextResponse.json(
      { error: 'external_id is required' },
      { status: 400 }
    );
  }

  try {
    const row = await queryOne(
      `
      SELECT
        a.id,
        a.external_id,
        a.brand_name,
        a.product_name,
        a.product_category,
        a.one_line_summary,
        a.format_type,
        a.year,
        a.duration_seconds,
        a.s3_key,
        a.has_supers,
        a.has_price_claims,
        a.impact_scores,
        a.hero_analysis,
        a.raw_transcript,
        a.analysis_json,
        a.created_at,
        -- Editorial fields
        e.brand_slug,
        e.slug,
        e.headline,
        e.editorial_summary,
        e.curated_tags,
        e.is_featured
      FROM ads a
      LEFT JOIN ad_editorial e ON e.ad_id = a.id AND ${PUBLISH_GATE_CONDITION}
      WHERE a.external_id = $1
      `,
      [external_id]
    );

    if (!row) {
      return NextResponse.json(
        { error: 'Ad not found' },
        { status: 404 }
      );
    }

    const response = {
      id: row.id,
      external_id: row.external_id,
      brand_name: row.brand_name,
      brand_slug: row.brand_slug,
      slug: row.slug,
      headline: row.headline || row.one_line_summary,
      one_line_summary: row.one_line_summary,
      // Map one_line_summary to description for AdDetail compatibility
      description: row.one_line_summary,
      summary: row.editorial_summary,
      product_name: row.product_name,
      product_category: row.product_category,
      format_type: row.format_type,
      year: row.year,
      duration_seconds: row.duration_seconds,
      // Note: video_url/thumbnail_url/image_url not stored in ads table
      video_url: null,
      thumbnail_url: null,
      image_url: null,
      s3_key: row.s3_key,
      has_supers: row.has_supers,
      has_price_claims: row.has_price_claims,
      impact_scores: row.impact_scores,
      hero_analysis: row.hero_analysis,
      transcript: row.raw_transcript,
      analysis: row.analysis_json,
      curated_tags: row.curated_tags || [],
      is_featured: row.is_featured || false,
      // Feedback not available (table doesn't exist)
      view_count: 0,
      like_count: 0,
      save_count: 0,
      final_score: null,
      created_at: row.created_at,
      canonical_url: row.brand_slug && row.slug
        ? `/advert/${row.brand_slug}/${row.slug}`
        : null,
    };

    return NextResponse.json(response, {
      headers: {
        'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=300',
      },
    });
  } catch (error) {
    console.error('Error fetching ad:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
