/**
 * Like Toggle API Route Handler
 *
 * POST /api/ads/[external_id]/like
 *
 * Toggles like status for an ad. Session-based.
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
    let isLiked = false;

    await transaction(async (client) => {
      // Check if already liked
      const existing = await client.query(
        `SELECT id FROM ad_likes WHERE ad_id = $1 AND session_id = $2`,
        [adId, sessionId]
      );

      if (existing.rows.length > 0) {
        // Unlike - remove the like
        await client.query(
          `DELETE FROM ad_likes WHERE ad_id = $1 AND session_id = $2`,
          [adId, sessionId]
        );

        // Decrement aggregate
        await client.query(
          `
          UPDATE ad_feedback_aggregates
          SET like_count = GREATEST(0, like_count - 1), updated_at = NOW()
          WHERE ad_id = $1
          `,
          [adId]
        );

        isLiked = false;
      } else {
        // Like - add like record
        await client.query(
          `INSERT INTO ad_likes (ad_id, session_id) VALUES ($1, $2)`,
          [adId, sessionId]
        );

        // Increment aggregate
        await client.query(
          `
          INSERT INTO ad_feedback_aggregates (ad_id, like_count)
          VALUES ($1, 1)
          ON CONFLICT (ad_id)
          DO UPDATE SET
            like_count = ad_feedback_aggregates.like_count + 1,
            updated_at = NOW()
          `,
          [adId]
        );

        isLiked = true;
      }
    });

    // Get updated count
    const result = await queryOne(
      'SELECT like_count FROM ad_feedback_aggregates WHERE ad_id = $1',
      [adId]
    );

    return NextResponse.json({
      success: true,
      is_liked: isLiked,
      like_count: result?.like_count || 0,
    });
  } catch (error) {
    console.error('Error toggling like:', error);
    return NextResponse.json(
      { error: 'Failed to toggle like' },
      { status: 500 }
    );
  }
}
