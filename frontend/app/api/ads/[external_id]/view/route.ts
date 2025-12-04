/**
 * View Recording API Route Handler
 *
 * POST /api/ads/[external_id]/view
 *
 * Records a view for an ad. Session-based deduplication.
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryOne, transaction } from '@/lib/db';

export const runtime = 'nodejs';

interface RouteContext {
  params: Promise<{ external_id: string }>;
}

export async function POST(request: NextRequest, context: RouteContext) {
  const { external_id } = await context.params;

  if (!external_id) {
    return NextResponse.json(
      { error: 'external_id is required' },
      { status: 400 }
    );
  }

  try {
    const body = await request.json().catch(() => ({}));
    const sessionId = body.session_id;

    if (!sessionId) {
      return NextResponse.json(
        { error: 'session_id is required' },
        { status: 400 }
      );
    }

    // Get ad ID
    const ad = await queryOne(
      'SELECT id FROM ads WHERE external_id = $1',
      [external_id]
    );

    if (!ad) {
      return NextResponse.json(
        { error: 'Ad not found' },
        { status: 404 }
      );
    }

    const adId = ad.id;

    // Record view with session deduplication
    await transaction(async (client) => {
      // Check if already viewed in this session
      const existing = await client.query(
        `SELECT id FROM ad_views WHERE ad_id = $1 AND session_id = $2`,
        [adId, sessionId]
      );

      if (existing.rows.length === 0) {
        // Insert view record
        await client.query(
          `INSERT INTO ad_views (ad_id, session_id) VALUES ($1, $2)`,
          [adId, sessionId]
        );

        // Update aggregate
        await client.query(
          `
          INSERT INTO ad_feedback_aggregates (ad_id, view_count)
          VALUES ($1, 1)
          ON CONFLICT (ad_id)
          DO UPDATE SET
            view_count = ad_feedback_aggregates.view_count + 1,
            updated_at = NOW()
          `,
          [adId]
        );
      }
    });

    // Get updated count
    const result = await queryOne(
      'SELECT view_count FROM ad_feedback_aggregates WHERE ad_id = $1',
      [adId]
    );

    return NextResponse.json({
      success: true,
      view_count: result?.view_count || 1,
    });
  } catch (error) {
    console.error('Error recording view:', error);
    return NextResponse.json(
      { error: 'Failed to record view' },
      { status: 500 }
    );
  }
}
