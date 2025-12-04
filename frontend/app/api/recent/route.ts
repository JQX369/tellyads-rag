/**
 * Recent Ads API Route Handler
 *
 * GET /api/recent
 *
 * Returns recently indexed ads with optional toxicity filtering.
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryAll, PUBLISH_GATE_CONDITION } from '@/lib/db';

export const runtime = 'nodejs';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const limit = Math.min(parseInt(searchParams.get('limit') || '20', 10), 100);
  const offset = parseInt(searchParams.get('offset') || '0', 10);
  const maxToxicity = parseFloat(searchParams.get('max_toxicity') || '0.7');
  const featured = searchParams.get('featured') === 'true';

  try {
    // Build conditions
    const conditions: string[] = [];
    const params: any[] = [];
    let paramIndex = 1;

    // Toxicity filter
    conditions.push(`COALESCE((a.toxicity_scores->>'toxicity_score')::float, 0) <= $${paramIndex}`);
    params.push(maxToxicity);
    paramIndex++;

    // Featured filter
    if (featured) {
      conditions.push(`e.is_featured = true`);
    }

    params.push(limit, offset);

    const whereClause = conditions.length > 0
      ? `WHERE ${conditions.join(' AND ')}`
      : '';

    const results = await queryAll(
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
        a.thumbnail_url,
        a.video_url,
        a.has_supers,
        a.impact_scores,
        a.toxicity_scores,
        a.created_at,
        e.brand_slug,
        e.slug,
        e.headline,
        e.curated_tags,
        e.is_featured,
        f.view_count,
        f.like_count,
        f.final_score
      FROM ads a
      LEFT JOIN ad_editorial e ON e.ad_id = a.id AND ${PUBLISH_GATE_CONDITION}
      LEFT JOIN ad_feedback_aggregates f ON f.ad_id = a.id
      ${whereClause}
      ORDER BY a.created_at DESC
      LIMIT $${paramIndex} OFFSET $${paramIndex + 1}
      `,
      params
    );

    const formattedResults = results.map((row) => ({
      id: row.id,
      external_id: row.external_id,
      brand_name: row.brand_name,
      brand_slug: row.brand_slug,
      slug: row.slug,
      headline: row.headline || row.one_line_summary,
      one_line_summary: row.one_line_summary,
      product_name: row.product_name,
      product_category: row.product_category,
      format_type: row.format_type,
      year: row.year,
      duration_seconds: row.duration_seconds,
      thumbnail_url: row.thumbnail_url,
      video_url: row.video_url,
      has_supers: row.has_supers,
      impact_scores: row.impact_scores,
      curated_tags: row.curated_tags || [],
      is_featured: row.is_featured || false,
      view_count: row.view_count || 0,
      like_count: row.like_count || 0,
      final_score: row.final_score,
      created_at: row.created_at,
      canonical_url: row.brand_slug && row.slug
        ? `/advert/${row.brand_slug}/${row.slug}`
        : `/ads/${row.external_id}`,
    }));

    return NextResponse.json({
      total: formattedResults.length,
      results: formattedResults,
    }, {
      headers: {
        'Cache-Control': 'public, s-maxage=30, stale-while-revalidate=60',
      },
    });
  } catch (error) {
    console.error('Error fetching recent ads:', error);
    return NextResponse.json(
      { error: 'Failed to fetch recent ads' },
      { status: 500 }
    );
  }
}
