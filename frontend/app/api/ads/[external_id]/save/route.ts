/**
 * Save Toggle API Route Handler
 *
 * POST /api/ads/[external_id]/save
 *
 * Toggles save status for an ad. Session-based.
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
    let isSaved = false;

    await transaction(async (client) => {
      // Check if already saved
      const existing = await client.query(
        `SELECT id FROM ad_saves WHERE ad_id = $1 AND session_id = $2`,
        [adId, sessionId]
      );

      if (existing.rows.length > 0) {
        // Unsave - remove the save
        await client.query(
          `DELETE FROM ad_saves WHERE ad_id = $1 AND session_id = $2`,
          [adId, sessionId]
        );

        // Decrement aggregate
        await client.query(
          `
          UPDATE ad_feedback_aggregates
          SET save_count = GREATEST(0, save_count - 1), updated_at = NOW()
          WHERE ad_id = $1
          `,
          [adId]
        );

        isSaved = false;
      } else {
        // Save - add save record
        await client.query(
          `INSERT INTO ad_saves (ad_id, session_id) VALUES ($1, $2)`,
          [adId, sessionId]
        );

        // Increment aggregate
        await client.query(
          `
          INSERT INTO ad_feedback_aggregates (ad_id, save_count)
          VALUES ($1, 1)
          ON CONFLICT (ad_id)
          DO UPDATE SET
            save_count = ad_feedback_aggregates.save_count + 1,
            updated_at = NOW()
          `,
          [adId]
        );

        isSaved = true;
      }
    });

    // Get updated count
    const result = await queryOne(
      'SELECT save_count FROM ad_feedback_aggregates WHERE ad_id = $1',
      [adId]
    );

    return NextResponse.json({
      success: true,
      is_saved: isSaved,
      save_count: result?.save_count || 0,
    });
  } catch (error) {
    console.error('Error toggling save:', error);
    return NextResponse.json(
      { error: 'Failed to toggle save' },
      { status: 500 }
    );
  }
}
