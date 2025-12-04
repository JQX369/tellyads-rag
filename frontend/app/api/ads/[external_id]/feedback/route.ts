/**
 * Feedback Metrics API Route Handler
 *
 * GET /api/ads/[external_id]/feedback
 *
 * Returns aggregated feedback metrics for an ad,
 * plus whether current session has liked/saved.
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryOne } from '@/lib/db';

export const runtime = 'nodejs';

interface RouteContext {
  params: Promise<{ external_id: string }>;
}

export async function GET(request: NextRequest, context: RouteContext) {
  const { external_id } = await context.params;
  const { searchParams } = new URL(request.url);
  const sessionId = searchParams.get('session_id');

  if (!external_id) {
    return NextResponse.json(
      { error: 'external_id is required' },
      { status: 400 }
    );
  }

  try {
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

    // Get aggregate metrics
    const aggregates = await queryOne(
      `
      SELECT
        view_count,
        like_count,
        save_count,
        ai_score,
        user_score,
        confidence_weight,
        final_score,
        reason_counts,
        distinct_reason_sessions,
        reason_threshold_met
      FROM ad_feedback_aggregates
      WHERE ad_id = $1
      `,
      [adId]
    );

    // Check session interactions if session provided
    let sessionInteractions = {
      has_liked: false,
      has_saved: false,
      has_viewed: false,
    };

    if (sessionId) {
      const liked = await queryOne(
        'SELECT id FROM ad_likes WHERE ad_id = $1 AND session_id = $2',
        [adId, sessionId]
      );

      const saved = await queryOne(
        'SELECT id FROM ad_saves WHERE ad_id = $1 AND session_id = $2',
        [adId, sessionId]
      );

      const viewed = await queryOne(
        'SELECT id FROM ad_views WHERE ad_id = $1 AND session_id = $2',
        [adId, sessionId]
      );

      sessionInteractions = {
        has_liked: !!liked,
        has_saved: !!saved,
        has_viewed: !!viewed,
      };
    }

    return NextResponse.json({
      external_id,
      metrics: {
        view_count: aggregates?.view_count || 0,
        like_count: aggregates?.like_count || 0,
        save_count: aggregates?.save_count || 0,
        ai_score: aggregates?.ai_score,
        user_score: aggregates?.user_score,
        confidence_weight: aggregates?.confidence_weight,
        final_score: aggregates?.final_score,
        reason_counts: aggregates?.reason_counts || {},
        distinct_reason_sessions: aggregates?.distinct_reason_sessions || 0,
        reason_threshold_met: aggregates?.reason_threshold_met || false,
      },
      session: sessionInteractions,
    });
  } catch (error) {
    console.error('Error fetching feedback:', error);
    return NextResponse.json(
      { error: 'Failed to fetch feedback' },
      { status: 500 }
    );
  }
}
