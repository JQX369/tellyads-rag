/**
 * Brands API Route Handler
 *
 * GET /api/brands
 *
 * Returns list of brands with ad counts.
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryAll } from '@/lib/db';

export const runtime = 'nodejs';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const limit = Math.min(parseInt(searchParams.get('limit') || '100', 10), 500);

  try {
    const results = await queryAll(
      `
      SELECT
        brand_name,
        COUNT(*) as ad_count,
        MIN(year) as first_year,
        MAX(year) as last_year,
        ARRAY_AGG(DISTINCT product_category) FILTER (WHERE product_category IS NOT NULL) as categories
      FROM ads
      WHERE brand_name IS NOT NULL AND brand_name != ''
      GROUP BY brand_name
      ORDER BY ad_count DESC, brand_name ASC
      LIMIT $1
      `,
      [limit]
    );

    const brands = results.map((row) => ({
      brand_name: row.brand_name,
      ad_count: parseInt(row.ad_count, 10),
      first_year: row.first_year,
      last_year: row.last_year,
      categories: row.categories || [],
    }));

    return NextResponse.json({
      total: brands.length,
      brands,
    }, {
      headers: {
        'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600',
      },
    });
  } catch (error) {
    console.error('Error fetching brands:', error);
    return NextResponse.json(
      { error: 'Failed to fetch brands' },
      { status: 500 }
    );
  }
}
