/**
 * Feedback Admin API Route
 *
 * GET /api/admin/feedback - Get feedback overview (leaderboard, stats)
 * POST /api/admin/feedback - Refresh aggregate metrics
 *
 * Admin-only endpoints for managing feedback and scoring.
 */

import { NextRequest, NextResponse } from 'next/server';
import { verifyAdminKey } from '@/lib/admin-auth';
import { queryAll, queryOne, query } from '@/lib/db';

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
    const limit = Math.min(parseInt(searchParams.get('limit') || '50', 10), 200);

    // Get leaderboard
    const leaderboard = await queryAll(
      `SELECT * FROM feedback_leaderboard LIMIT $1`,
      [limit]
    );

    // Get pending reviews
    const pendingReviews = await queryAll(
      `SELECT * FROM pending_reviews LIMIT 50`
    );

    // Get overall stats
    const stats = await queryOne(`
      SELECT
        COUNT(*) as total_ads,
        COUNT(*) FILTER (WHERE total_views > 0) as ads_with_views,
        COUNT(*) FILTER (WHERE rating_count > 0) as ads_with_ratings,
        SUM(total_views) as total_views,
        SUM(rating_count) as total_ratings,
        AVG(rating_avg) FILTER (WHERE rating_count > 0) as avg_rating,
        MAX(updated_at) as last_refresh
      FROM ad_feedback_agg
    `);

    // Get active weight config
    const config = await queryOne(
      `SELECT * FROM feedback_weight_configs WHERE is_active = true ORDER BY created_at DESC LIMIT 1`
    );

    return NextResponse.json({
      leaderboard,
      pendingReviews,
      stats,
      config,
    });
  } catch (error) {
    console.error('Error fetching feedback data:', error);
    return NextResponse.json(
      { error: 'Failed to fetch feedback data' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  const adminKey = request.headers.get('x-admin-key');
  const auth = verifyAdminKey(adminKey);

  if (!auth.verified) {
    return NextResponse.json(
      { error: auth.error || 'Unauthorized' },
      { status: 401 }
    );
  }

  try {
    const body = await request.json();
    const { action, ad_id } = body;

    if (action === 'refresh') {
      // Refresh aggregate metrics
      const result = await queryOne<{ refresh_ad_feedback_agg: number }>(
        `SELECT refresh_ad_feedback_agg($1)`,
        [ad_id || null]
      );

      return NextResponse.json({
        success: true,
        updated: result?.refresh_ad_feedback_agg || 0,
        message: ad_id
          ? `Refreshed metrics for ad ${ad_id}`
          : 'Refreshed all feedback metrics',
      });
    }

    return NextResponse.json(
      { error: 'Invalid action' },
      { status: 400 }
    );
  } catch (error) {
    console.error('Error processing feedback action:', error);
    return NextResponse.json(
      { error: 'Failed to process action' },
      { status: 500 }
    );
  }
}
