/**
 * Stats API Route Handler
 *
 * GET /api/stats
 *
 * Returns public database statistics.
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryOne, queryAll, PUBLISH_GATE_CONDITION } from '@/lib/db';

export const runtime = 'nodejs';

export async function GET(request: NextRequest) {
  try {
    // Get basic counts
    const counts = await queryOne(`
      SELECT
        COUNT(*) as total_ads,
        COUNT(DISTINCT brand_name) as total_brands,
        COUNT(*) FILTER (WHERE embedding IS NOT NULL) as ads_with_embeddings,
        COUNT(*) FILTER (WHERE year IS NOT NULL) as ads_with_year,
        MIN(year) as earliest_year,
        MAX(year) as latest_year
      FROM ads
    `);

    // Get editorial counts
    const editorialCounts = await queryOne(`
      SELECT
        COUNT(*) as total_editorial,
        COUNT(*) FILTER (WHERE ${PUBLISH_GATE_CONDITION}) as published_editorial
      FROM ad_editorial
    `);

    // Get category breakdown
    const categories = await queryAll(`
      SELECT
        product_category,
        COUNT(*) as count
      FROM ads
      WHERE product_category IS NOT NULL AND product_category != ''
      GROUP BY product_category
      ORDER BY count DESC
      LIMIT 20
    `);

    // Get year breakdown
    const years = await queryAll(`
      SELECT
        year,
        COUNT(*) as count
      FROM ads
      WHERE year IS NOT NULL
      GROUP BY year
      ORDER BY year DESC
      LIMIT 20
    `);

    const stats = {
      total_ads: parseInt(counts?.total_ads ?? '0', 10),
      total_brands: parseInt(counts?.total_brands ?? '0', 10),
      ads_with_embeddings: parseInt(counts?.ads_with_embeddings ?? '0', 10),
      ads_with_year: parseInt(counts?.ads_with_year ?? '0', 10),
      earliest_year: counts?.earliest_year ?? null,
      latest_year: counts?.latest_year ?? null,
      total_editorial: parseInt(editorialCounts?.total_editorial ?? '0', 10),
      published_editorial: parseInt(editorialCounts?.published_editorial ?? '0', 10),
      categories: categories.map((row) => ({
        name: row.product_category,
        count: parseInt(row.count, 10),
      })),
      years: years.map((row) => ({
        year: row.year,
        count: parseInt(row.count, 10),
      })),
    };

    return NextResponse.json(stats, {
      headers: {
        'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600',
      },
    });
  } catch (error) {
    console.error('Error fetching stats:', error);
    return NextResponse.json(
      { error: 'Failed to fetch stats' },
      { status: 500 }
    );
  }
}
