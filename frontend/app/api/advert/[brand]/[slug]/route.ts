/**
 * SEO Advert API Route Handler
 *
 * GET /api/advert/[brand]/[slug]
 *
 * Returns ad details with editorial data, with publish gating.
 * Only returns ads that are published, not hidden, and past publish_date.
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryOne, PUBLISH_GATE_CONDITION } from '@/lib/db';

export const runtime = 'nodejs';

interface RouteContext {
  params: Promise<{ brand: string; slug: string }>;
}

export async function GET(request: NextRequest, context: RouteContext) {
  const { brand, slug } = await context.params;

  if (!brand || !slug) {
    return NextResponse.json(
      { error: 'brand and slug are required' },
      { status: 400 }
    );
  }

  try {
    // Query for editorial + ad data with publish gating
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
        a.created_at,
        -- Editorial fields (override extractor data)
        e.brand_slug,
        e.slug,
        e.headline,
        e.editorial_summary,
        e.curated_tags,
        e.is_featured,
        e.seo_title,
        e.seo_description,
        e.legacy_url,
        e.status as editorial_status,
        e.publish_date,
        -- Feedback metrics
        f.view_count,
        f.like_count,
        f.save_count,
        f.ai_score,
        f.user_score,
        f.confidence_weight,
        f.final_score,
        f.reason_counts,
        f.distinct_reason_sessions,
        f.reason_threshold_met
      FROM ad_editorial e
      JOIN ads a ON a.id = e.ad_id
      LEFT JOIN ad_feedback_aggregates f ON f.ad_id = a.id
      WHERE e.brand_slug = $1
        AND e.slug = $2
        AND ${PUBLISH_GATE_CONDITION}
      `,
      [brand, slug]
    );

    if (!row) {
      return NextResponse.json(
        { error: 'Ad not found or not published' },
        { status: 404 }
      );
    }

    // Build response with editorial overrides
    const response = {
      id: row.id,
      external_id: row.external_id,
      brand_name: row.brand_name,
      brand_slug: row.brand_slug,
      slug: row.slug,
      // Editorial fields take precedence
      headline: row.headline || row.one_line_summary,
      summary: row.editorial_summary,
      extracted_summary: row.one_line_summary,
      one_line_summary: row.one_line_summary,
      // Metadata
      product_name: row.product_name,
      product_category: row.product_category,
      format_type: row.format_type,
      year: row.year,
      duration_seconds: row.duration_seconds,
      // Media
      video_url: row.video_url,
      thumbnail_url: row.thumbnail_url,
      s3_key: row.s3_key,
      // Analysis
      has_supers: row.has_supers,
      has_price_claims: row.has_price_claims,
      impact_scores: row.impact_scores,
      emotional_metrics: row.emotional_metrics,
      effectiveness: row.effectiveness,
      hero_analysis: row.hero_analysis,
      // Editorial
      curated_tags: row.curated_tags || [],
      is_featured: row.is_featured || false,
      seo_title: row.seo_title,
      seo_description: row.seo_description,
      legacy_url: row.legacy_url,
      // Feedback metrics
      view_count: row.view_count || 0,
      like_count: row.like_count || 0,
      save_count: row.save_count || 0,
      ai_score: row.ai_score,
      user_score: row.user_score,
      confidence_weight: row.confidence_weight,
      final_score: row.final_score,
      reason_counts: row.reason_counts,
      distinct_reason_sessions: row.distinct_reason_sessions,
      reason_threshold_met: row.reason_threshold_met || false,
      // Timestamps
      created_at: row.created_at,
    };

    return NextResponse.json(response, {
      headers: {
        'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=300',
      },
    });
  } catch (error) {
    console.error('Error fetching advert:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
