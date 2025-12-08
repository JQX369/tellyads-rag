/**
 * Similar Ads API Route Handler
 *
 * GET /api/ads/[external_id]/similar
 *
 * Returns similar ads based on embedding similarity.
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryOne, queryAll, PUBLISH_GATE_CONDITION } from '@/lib/db';

export const runtime = 'nodejs';

interface RouteContext {
  params: Promise<{ external_id: string }>;
}

export async function GET(request: NextRequest, context: RouteContext) {
  const { external_id } = await context.params;
  const { searchParams } = new URL(request.url);
  const limit = Math.min(parseInt(searchParams.get('limit') || '10', 10), 50);

  if (!external_id) {
    return NextResponse.json(
      { error: 'external_id is required' },
      { status: 400 }
    );
  }

  try {
    // Get source ad and its embedding from embedding_items
    const sourceAd = await queryOne(
      `SELECT a.id, ei.embedding
       FROM ads a
       LEFT JOIN embedding_items ei ON ei.ad_id = a.id AND ei.item_type = 'ad_summary'
       WHERE a.external_id = $1`,
      [external_id]
    );

    if (!sourceAd) {
      return NextResponse.json(
        { error: 'Ad not found' },
        { status: 404 }
      );
    }

    if (!sourceAd.embedding) {
      return NextResponse.json({
        external_id,
        total: 0,
        results: [],
        message: 'Source ad has no embedding',
      });
    }

    // Find similar ads by embedding using embedding_items table
    // Uses ad_summary embeddings as the canonical ad-level embedding
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
        a.s3_key,
        a.impact_scores,
        e.brand_slug,
        e.slug,
        e.headline,
        e.curated_tags,
        e.is_featured,
        1 - (ei.embedding <=> $1::vector) as similarity
      FROM embedding_items ei
      JOIN ads a ON a.id = ei.ad_id
      LEFT JOIN ad_editorial e ON e.ad_id = a.id AND ${PUBLISH_GATE_CONDITION}
      WHERE ei.item_type = 'ad_summary'
        AND a.id != $2
      ORDER BY ei.embedding <=> $1::vector
      LIMIT $3
      `,
      [sourceAd.embedding, sourceAd.id, limit]
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
      s3_key: row.s3_key,
      // Note: thumbnail_url/video_url not stored in ads table
      thumbnail_url: null,
      video_url: null,
      impact_scores: row.impact_scores,
      curated_tags: row.curated_tags || [],
      is_featured: row.is_featured || false,
      similarity: row.similarity,
      canonical_url: row.brand_slug && row.slug
        ? `/advert/${row.brand_slug}/${row.slug}`
        : `/ads/${row.external_id}`,
    }));

    return NextResponse.json({
      external_id,
      total: formattedResults.length,
      results: formattedResults,
    }, {
      headers: {
        'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600',
      },
    });
  } catch (error) {
    console.error('Error fetching similar ads:', error);
    return NextResponse.json(
      { error: 'Failed to fetch similar ads' },
      { status: 500 }
    );
  }
}
