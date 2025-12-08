/**
 * Admin Single Ad API Route Handler
 *
 * GET /api/admin/ads/[id] - Get single ad details
 * PUT /api/admin/ads/[id] - Update ad metadata
 * DELETE /api/admin/ads/[id] - Delete ad
 */

import { NextRequest, NextResponse } from 'next/server';
import { query, queryOne } from '@/lib/db';
import { verifyAdminKey } from '@/lib/admin-auth';

export const runtime = 'nodejs';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const adminKey = request.headers.get('x-admin-key');
  const auth = verifyAdminKey(adminKey);
  if (!auth.verified) {
    return NextResponse.json({ error: auth.error || 'Unauthorized' }, { status: 401 });
  }

  const { id } = await params;

  try {
    const ad = await queryOne(
      `
      SELECT
        a.*,
        e.id as editorial_id,
        e.brand_slug,
        e.slug,
        e.headline,
        e.editorial_summary,
        e.curated_tags,
        e.status as editorial_status,
        e.is_hidden,
        e.is_featured,
        e.publish_date
      FROM ads a
      LEFT JOIN ad_editorial e ON e.ad_id = a.id
      WHERE a.external_id = $1 OR a.id::text = $1
      `,
      [id]
    );

    if (!ad) {
      return NextResponse.json({ error: 'Ad not found' }, { status: 404 });
    }

    return NextResponse.json({ ad });
  } catch (error) {
    console.error('Error fetching ad:', error);
    return NextResponse.json(
      { error: 'Failed to fetch ad' },
      { status: 500 }
    );
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const adminKey = request.headers.get('x-admin-key');
  const auth = verifyAdminKey(adminKey);
  if (!auth.verified) {
    return NextResponse.json({ error: auth.error || 'Unauthorized' }, { status: 401 });
  }

  const { id } = await params;

  try {
    const body = await request.json();
    const {
      brand_name,
      product_name,
      product_category,
      one_line_summary,
      year,
    } = body;

    // Find the ad first
    const existing = await queryOne(
      'SELECT id FROM ads WHERE external_id = $1 OR id::text = $1',
      [id]
    );

    if (!existing) {
      return NextResponse.json({ error: 'Ad not found' }, { status: 404 });
    }

    // Update the ad
    await query(
      `
      UPDATE ads
      SET
        brand_name = COALESCE($2, brand_name),
        product_name = COALESCE($3, product_name),
        product_category = COALESCE($4, product_category),
        one_line_summary = COALESCE($5, one_line_summary),
        year = COALESCE($6, year),
        updated_at = NOW()
      WHERE id = $1
      `,
      [existing.id, brand_name, product_name, product_category, one_line_summary, year]
    );

    return NextResponse.json({ success: true, id: existing.id });
  } catch (error) {
    console.error('Error updating ad:', error);
    return NextResponse.json(
      { error: 'Failed to update ad' },
      { status: 500 }
    );
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const adminKey = request.headers.get('x-admin-key');
  const auth = verifyAdminKey(adminKey);
  if (!auth.verified) {
    return NextResponse.json({ error: auth.error || 'Unauthorized' }, { status: 401 });
  }

  const { id } = await params;

  try {
    // Find the ad first
    const existing = await queryOne(
      'SELECT id FROM ads WHERE external_id = $1 OR id::text = $1',
      [id]
    );

    if (!existing) {
      return NextResponse.json({ error: 'Ad not found' }, { status: 404 });
    }

    // Delete editorial record first (foreign key constraint)
    await query('DELETE FROM ad_editorial WHERE ad_id = $1', [existing.id]);

    // Delete the ad
    await query('DELETE FROM ads WHERE id = $1', [existing.id]);

    return NextResponse.json({ success: true, deleted_id: id });
  } catch (error) {
    console.error('Error deleting ad:', error);
    return NextResponse.json(
      { error: 'Failed to delete ad' },
      { status: 500 }
    );
  }
}
