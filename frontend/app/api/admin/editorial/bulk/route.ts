/**
 * Admin Editorial Bulk Actions API
 *
 * POST /api/admin/editorial/bulk
 *
 * Bulk publish, unpublish, or hide multiple ads at once.
 */

import { NextRequest, NextResponse } from 'next/server';
import { query, queryAll } from '@/lib/db';
import { verifyAdminKey } from '@/lib/admin-auth';

export const runtime = 'nodejs';

export async function POST(request: NextRequest) {
  const adminKey = request.headers.get('x-admin-key');
  const auth = verifyAdminKey(adminKey);
  if (!auth.verified) {
    return NextResponse.json({ error: auth.error || 'Unauthorized' }, { status: 401 });
  }

  try {
    const body = await request.json();
    const { ad_ids, action } = body;

    if (!ad_ids || !Array.isArray(ad_ids) || ad_ids.length === 0) {
      return NextResponse.json({ error: 'ad_ids array is required' }, { status: 400 });
    }

    if (!['publish', 'unpublish', 'hide', 'unhide', 'feature', 'unfeature'].includes(action)) {
      return NextResponse.json({ error: 'Invalid action. Use: publish, unpublish, hide, unhide, feature, unfeature' }, { status: 400 });
    }

    const results = {
      success: 0,
      failed: 0,
      errors: [] as string[],
    };

    for (const ad_id of ad_ids) {
      try {
        // Get ad info for generating slugs
        const ad = await queryAll('SELECT id, brand_name, external_id FROM ads WHERE id = $1', [ad_id]);
        if (ad.length === 0) {
          results.failed++;
          results.errors.push(`Ad ${ad_id} not found`);
          continue;
        }

        // Check if editorial record exists
        const existing = await queryAll('SELECT id FROM ad_editorial WHERE ad_id = $1', [ad_id]);

        if (existing.length === 0 && (action === 'publish' || action === 'feature')) {
          // Create editorial record for publish/feature
          const brandSlug = ad[0].brand_name?.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'unknown';
          const slug = ad[0].external_id?.toLowerCase() || `ad-${ad_id}`;

          await query(
            `
            INSERT INTO ad_editorial (ad_id, brand_slug, slug, headline, status, is_hidden, is_featured, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, false, $6, NOW(), NOW())
            `,
            [
              ad_id,
              brandSlug,
              slug,
              ad[0].brand_name || 'Untitled',
              action === 'publish' ? 'published' : 'draft',
              action === 'feature',
            ]
          );
        } else if (existing.length > 0) {
          // Update existing record
          let updateQuery = '';
          switch (action) {
            case 'publish':
              updateQuery = `UPDATE ad_editorial SET status = 'published', is_hidden = false, updated_at = NOW() WHERE ad_id = $1`;
              break;
            case 'unpublish':
              updateQuery = `UPDATE ad_editorial SET status = 'draft', updated_at = NOW() WHERE ad_id = $1`;
              break;
            case 'hide':
              updateQuery = `UPDATE ad_editorial SET is_hidden = true, updated_at = NOW() WHERE ad_id = $1`;
              break;
            case 'unhide':
              updateQuery = `UPDATE ad_editorial SET is_hidden = false, updated_at = NOW() WHERE ad_id = $1`;
              break;
            case 'feature':
              updateQuery = `UPDATE ad_editorial SET is_featured = true, updated_at = NOW() WHERE ad_id = $1`;
              break;
            case 'unfeature':
              updateQuery = `UPDATE ad_editorial SET is_featured = false, updated_at = NOW() WHERE ad_id = $1`;
              break;
          }
          await query(updateQuery, [ad_id]);
        }

        results.success++;
      } catch (error) {
        results.failed++;
        results.errors.push(`Error processing ad ${ad_id}: ${error}`);
      }
    }

    return NextResponse.json({
      success: true,
      results,
    });
  } catch (error) {
    console.error('Bulk editorial action error:', error);
    return NextResponse.json(
      { error: 'Failed to process bulk action' },
      { status: 500 }
    );
  }
}
