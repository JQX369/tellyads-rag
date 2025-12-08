/**
 * Catalog API Route
 *
 * GET /api/admin/catalog - List catalog entries with filters
 *
 * Admin-only endpoint for viewing and managing the ad catalog.
 */

import { NextRequest, NextResponse } from 'next/server';
import { verifyAdminKey } from '@/lib/admin-auth';
import { queryAll, queryOne } from '@/lib/db';

export const runtime = 'nodejs';

export async function GET(request: NextRequest) {
  const adminKey = request.headers.get('x-admin-key');
  const auth = verifyAdminKey(adminKey);

  if (!auth.verified) {
    return NextResponse.json(
      { error: auth.error || 'Unauthorized' },
      { status: 401 }
    );
  }

  try {
    const { searchParams } = new URL(request.url);

    // Filters
    const filter = searchParams.get('filter'); // 'unmapped', 'not_ingested', 'low_confidence', 'all'
    const brand = searchParams.get('brand');
    const decade = searchParams.get('decade');
    const country = searchParams.get('country');
    const search = searchParams.get('search');

    // Pagination
    const limit = Math.min(parseInt(searchParams.get('limit') || '50', 10), 200);
    const offset = parseInt(searchParams.get('offset') || '0', 10);

    // Build WHERE clause
    const conditions: string[] = [];
    const params: (string | number)[] = [];
    let paramIndex = 1;

    if (filter === 'unmapped') {
      conditions.push('NOT is_mapped');
    } else if (filter === 'not_ingested') {
      conditions.push('NOT is_ingested');
    } else if (filter === 'low_confidence') {
      conditions.push('date_parse_confidence < 0.8');
    }

    if (brand) {
      conditions.push(`brand_name ILIKE $${paramIndex}`);
      params.push(`%${brand}%`);
      paramIndex++;
    }

    if (decade) {
      conditions.push(`decade = $${paramIndex}`);
      params.push(decade);
      paramIndex++;
    }

    if (country) {
      conditions.push(`country ILIKE $${paramIndex}`);
      params.push(`%${country}%`);
      paramIndex++;
    }

    if (search) {
      conditions.push(`(
        external_id ILIKE $${paramIndex} OR
        brand_name ILIKE $${paramIndex} OR
        title ILIKE $${paramIndex}
      )`);
      params.push(`%${search}%`);
      paramIndex++;
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';

    // Get catalog entries
    const entries = await queryAll(
      `SELECT
        id, external_id, brand_name, title,
        air_date, air_date_raw, date_parse_confidence, date_parse_warning,
        year, decade, country, language,
        s3_key, video_url, views_seeded,
        is_mapped, is_ingested, ad_id,
        created_at, updated_at
      FROM ad_catalog
      ${whereClause}
      ORDER BY created_at DESC
      LIMIT $${paramIndex} OFFSET $${paramIndex + 1}`,
      [...params, limit, offset]
    );

    // Get total count
    const countResult = await queryOne<{ count: string }>(
      `SELECT COUNT(*) as count FROM ad_catalog ${whereClause}`,
      params
    );

    // Get summary stats
    const summary = await queryOne(`SELECT * FROM catalog_summary`);

    // Get filter options
    const brands = await queryAll(
      `SELECT brand_name, COUNT(*) as count
       FROM ad_catalog
       WHERE brand_name IS NOT NULL
       GROUP BY brand_name
       ORDER BY count DESC
       LIMIT 50`
    );

    const decades = await queryAll(`SELECT * FROM catalog_by_decade`);

    const countries = await queryAll(
      `SELECT country, COUNT(*) as count
       FROM ad_catalog
       WHERE country IS NOT NULL
       GROUP BY country
       ORDER BY count DESC
       LIMIT 30`
    );

    return NextResponse.json({
      entries,
      total: parseInt(countResult?.count || '0', 10),
      limit,
      offset,
      summary,
      filters: {
        brands,
        decades,
        countries,
      },
    });
  } catch (error) {
    console.error('Error fetching catalog:', error);
    return NextResponse.json(
      { error: 'Failed to fetch catalog' },
      { status: 500 }
    );
  }
}
