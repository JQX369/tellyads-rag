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
        a.thumbnail_url,
        a.video_url,
        a.has_supers,
        a.has_price_claims,
        a.impact_scores,
        a.emotional_metrics,
        a.effectiveness,
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
        e.is_featured,
        -- Feedback
        f.view_count,
        f.like_count,
        f.save_count,
        f.final_score
      FROM ads a
      LEFT JOIN ad_editorial e ON e.ad_id = a.id AND ${PUBLISH_GATE_CONDITION}
      LEFT JOIN ad_feedback_aggregates f ON f.ad_id = a.id
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
      summary: row.editorial_summary,
      product_name: row.product_name,
      product_category: row.product_category,
      format_type: row.format_type,
      year: row.year,
      duration_seconds: row.duration_seconds,
      video_url: row.video_url,
      thumbnail_url: row.thumbnail_url,
      s3_key: row.s3_key,
      has_supers: row.has_supers,
      has_price_claims: row.has_price_claims,
      impact_scores: row.impact_scores,
      emotional_metrics: row.emotional_metrics,
      effectiveness: row.effectiveness,
      hero_analysis: row.hero_analysis,
      transcript: row.raw_transcript,
      analysis: row.analysis_json,
      curated_tags: row.curated_tags || [],
      is_featured: row.is_featured || false,
      view_count: row.view_count || 0,
      like_count: row.like_count || 0,
      save_count: row.save_count || 0,
      final_score: row.final_score,
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
