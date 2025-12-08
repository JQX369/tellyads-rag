/**
 * Admin Editorial API Route Handler
 *
 * GET /api/admin/editorial - List all ads with editorial status
 * POST /api/admin/editorial - Create/update editorial record
 */

import { NextRequest, NextResponse } from 'next/server';
import { query, queryAll, queryOne } from '@/lib/db';
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
  const filter = searchParams.get('filter') || 'all'; // all, published, draft, unpublished

  try {
    // Build filter condition
    let filterCondition = '';
    if (filter === 'published') {
      filterCondition = `AND e.status = 'published' AND e.is_hidden = false`;
    } else if (filter === 'draft') {
      filterCondition = `AND e.status = 'draft'`;
    } else if (filter === 'hidden') {
      filterCondition = `AND e.is_hidden = true`;
    } else if (filter === 'unpublished') {
      filterCondition = `AND e.id IS NULL`;
    }

    // Get ads with their editorial status
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
        a.created_at,
        -- Editorial fields
        e.id as editorial_id,
        e.brand_slug,
        e.slug,
        e.headline,
        e.status as editorial_status,
        e.is_hidden,
        e.is_featured,
        e.publish_date,
        e.created_at as editorial_created_at,
        e.updated_at as editorial_updated_at
      FROM ads a
      LEFT JOIN ad_editorial e ON e.ad_id = a.id
      WHERE 1=1 ${filterCondition}
      ORDER BY a.created_at DESC
      LIMIT $1 OFFSET $2
      `,
      [limit, offset]
    );

    // Get total counts
    const counts = await queryOne(`
      SELECT
        COUNT(*) as total,
        COUNT(e.id) as with_editorial,
        COUNT(CASE WHEN e.status = 'published' AND e.is_hidden = false THEN 1 END) as published,
        COUNT(CASE WHEN e.status = 'draft' THEN 1 END) as draft,
        COUNT(CASE WHEN e.is_hidden = true THEN 1 END) as hidden
      FROM ads a
      LEFT JOIN ad_editorial e ON e.ad_id = a.id
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
        created_at: row.created_at,
        // Editorial
        editorial_id: row.editorial_id,
        brand_slug: row.brand_slug,
        slug: row.slug,
        headline: row.headline,
        editorial_status: row.editorial_status || 'none',
        is_hidden: row.is_hidden || false,
        is_featured: row.is_featured || false,
        publish_date: row.publish_date,
        editorial_created_at: row.editorial_created_at,
        editorial_updated_at: row.editorial_updated_at,
      })),
      counts: {
        total: parseInt(counts?.total || '0'),
        with_editorial: parseInt(counts?.with_editorial || '0'),
        published: parseInt(counts?.published || '0'),
        draft: parseInt(counts?.draft || '0'),
        hidden: parseInt(counts?.hidden || '0'),
      },
      pagination: {
        limit,
        offset,
        filter,
      },
    });
  } catch (error) {
    console.error('Error fetching editorial list:', error);
    return NextResponse.json(
      { error: 'Failed to fetch editorial data' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  const adminKey = request.headers.get('x-admin-key');
  const auth = verifyAdminKey(adminKey);
  if (!auth.verified) {
    return NextResponse.json({ error: auth.error || 'Unauthorized' }, { status: 401 });
  }

  try {
    const body = await request.json();
    const { ad_id, status, is_hidden, is_featured, headline, brand_slug, slug } = body;

    if (!ad_id) {
      return NextResponse.json({ error: 'ad_id is required' }, { status: 400 });
    }

    // Check if ad exists
    const ad = await queryOne('SELECT id, brand_name, external_id FROM ads WHERE id = $1', [ad_id]);
    if (!ad) {
      return NextResponse.json({ error: 'Ad not found' }, { status: 404 });
    }

    // Generate slug if not provided
    const finalBrandSlug = brand_slug || ad.brand_name?.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'unknown';
    const finalSlug = slug || ad.external_id?.toLowerCase() || `ad-${ad_id}`;

    // Check if editorial record exists
    const existing = await queryOne('SELECT id FROM ad_editorial WHERE ad_id = $1', [ad_id]);

    if (existing) {
      // Update existing
      await query(
        `
        UPDATE ad_editorial
        SET
          status = COALESCE($2, status),
          is_hidden = COALESCE($3, is_hidden),
          is_featured = COALESCE($4, is_featured),
          headline = COALESCE($5, headline),
          brand_slug = COALESCE($6, brand_slug),
          slug = COALESCE($7, slug),
          updated_at = NOW()
        WHERE ad_id = $1
        `,
        [ad_id, status, is_hidden, is_featured, headline, finalBrandSlug, finalSlug]
      );
    } else {
      // Create new
      await query(
        `
        INSERT INTO ad_editorial (ad_id, brand_slug, slug, headline, status, is_hidden, is_featured, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW())
        `,
        [
          ad_id,
          finalBrandSlug,
          finalSlug,
          headline || ad.brand_name,
          status || 'draft',
          is_hidden ?? false,
          is_featured ?? false,
        ]
      );
    }

    return NextResponse.json({ success: true, ad_id });
  } catch (error) {
    console.error('Error updating editorial:', error);
    return NextResponse.json(
      { error: 'Failed to update editorial data' },
      { status: 500 }
    );
  }
}
