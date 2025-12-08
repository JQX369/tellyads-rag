/**
 * Admin Ads API Route Handler
 *
 * GET /api/admin/ads - List all ads with full details for CMS
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryAll, queryOne } from '@/lib/db';
import { verifyAdminKey } from '@/lib/admin-auth';

export const runtime = 'nodejs';

export async function GET(request: NextRequest) {
  const adminKey = request.headers.get('x-admin-key');
  const auth = verifyAdminKey(adminKey);
  if (!auth.verified) {
    return NextResponse.json({ error: auth.error || 'Unauthorized' }, { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const limit = Math.min(parseInt(searchParams.get('limit') || '50', 10), 200);
  const offset = parseInt(searchParams.get('offset') || '0', 10);
  const search = searchParams.get('search') || '';
  const sortField = searchParams.get('sort') || 'created_at';
  const sortOrder = searchParams.get('order') === 'asc' ? 'ASC' : 'DESC';
  const category = searchParams.get('category') || '';

  try {
    // Build filter conditions
    const conditions: string[] = ['1=1'];
    const params: any[] = [];
    let paramIndex = 1;

    if (search) {
      conditions.push(`(
        a.brand_name ILIKE $${paramIndex} OR
        a.product_name ILIKE $${paramIndex} OR
        a.external_id ILIKE $${paramIndex} OR
        a.one_line_summary ILIKE $${paramIndex}
      )`);
      params.push(`%${search}%`);
      paramIndex++;
    }

    if (category) {
      conditions.push(`a.product_category = $${paramIndex}`);
      params.push(category);
      paramIndex++;
    }

    // Validate sort field to prevent SQL injection
    const allowedSortFields = ['created_at', 'brand_name', 'product_name', 'year', 'product_category'];
    const safeSortField = allowedSortFields.includes(sortField) ? sortField : 'created_at';

    // Get ads with all management fields
    const results = await queryAll(
      `
      SELECT
        a.id,
        a.external_id,
        a.brand_name,
        a.product_name,
        a.product_category,
        a.one_line_summary,
        a.year,
        a.duration_seconds,
        a.s3_key,
        a.created_at,
        a.updated_at,
        -- Check if ad has embeddings
        EXISTS(SELECT 1 FROM embedding_items ei WHERE ei.ad_id = a.id) as has_embedding,
        -- Editorial join
        e.id as editorial_id,
        e.status as editorial_status,
        e.is_hidden,
        e.is_featured
      FROM ads a
      LEFT JOIN ad_editorial e ON e.ad_id = a.id
      WHERE ${conditions.join(' AND ')}
      ORDER BY a.${safeSortField} ${sortOrder}
      LIMIT $${paramIndex} OFFSET $${paramIndex + 1}
      `,
      [...params, limit, offset]
    );

    // Get total count for pagination
    const countResult = await queryOne(
      `SELECT COUNT(*) as total FROM ads a WHERE ${conditions.join(' AND ')}`,
      params
    );

    // Get distinct categories for filter dropdown
    const categories = await queryAll(`
      SELECT DISTINCT product_category, COUNT(*) as count
      FROM ads
      WHERE product_category IS NOT NULL AND product_category != ''
      GROUP BY product_category
      ORDER BY count DESC
    `);

    return NextResponse.json({
      ads: results.map(row => ({
        id: row.id,
        external_id: row.external_id,
        brand_name: row.brand_name,
        product_name: row.product_name,
        product_category: row.product_category,
        one_line_summary: row.one_line_summary,
        year: row.year,
        duration_seconds: row.duration_seconds,
        s3_key: row.s3_key,
        created_at: row.created_at,
        updated_at: row.updated_at,
        has_embedding: row.has_embedding,
        editorial_id: row.editorial_id,
        editorial_status: row.editorial_status || 'none',
        is_hidden: row.is_hidden || false,
        is_featured: row.is_featured || false,
      })),
      pagination: {
        total: parseInt(countResult?.total || '0'),
        limit,
        offset,
        hasMore: offset + results.length < parseInt(countResult?.total || '0'),
      },
      filters: {
        categories: categories.map(c => ({
          name: c.product_category,
          count: parseInt(c.count),
        })),
      },
    });
  } catch (error) {
    console.error('Error fetching ads:', error);
    return NextResponse.json(
      { error: 'Failed to fetch ads' },
      { status: 500 }
    );
  }
}
