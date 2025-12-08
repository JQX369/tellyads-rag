/**
 * Review Moderation API Route
 *
 * GET /api/admin/feedback/reviews - Get reviews (filterable by status)
 * POST /api/admin/feedback/reviews - Moderate a review (approve/reject)
 *
 * Admin-only endpoints for moderating user reviews.
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
    const status = searchParams.get('status') || 'pending';
    const limit = Math.min(parseInt(searchParams.get('limit') || '50', 10), 200);
    const offset = parseInt(searchParams.get('offset') || '0', 10);

    const reviews = await queryAll(
      `SELECT
        r.id, r.ad_id, r.rating, r.review_text, r.status,
        r.created_at, r.updated_at, r.helpful_count, r.reported_count,
        a.external_id, a.brand, a.title
      FROM ad_ratings r
      JOIN ads a ON r.ad_id = a.id
      WHERE r.status = $1 AND r.review_text IS NOT NULL
      ORDER BY r.created_at DESC
      LIMIT $2 OFFSET $3`,
      [status, limit, offset]
    );

    const countResult = await queryOne<{ count: string }>(
      `SELECT COUNT(*) as count FROM ad_ratings WHERE status = $1 AND review_text IS NOT NULL`,
      [status]
    );

    // Get status counts
    const statusCounts = await queryAll<{ status: string; count: string }>(
      `SELECT status, COUNT(*) as count
       FROM ad_ratings
       WHERE review_text IS NOT NULL
       GROUP BY status`
    );

    return NextResponse.json({
      reviews,
      total: parseInt(countResult?.count || '0', 10),
      limit,
      offset,
      statusCounts: Object.fromEntries(
        statusCounts.map((s) => [s.status, parseInt(s.count, 10)])
      ),
    });
  } catch (error) {
    console.error('Error fetching reviews:', error);
    return NextResponse.json(
      { error: 'Failed to fetch reviews' },
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
    const { review_id, action } = body;

    if (!review_id) {
      return NextResponse.json(
        { error: 'review_id is required' },
        { status: 400 }
      );
    }

    if (!['approve', 'reject', 'flag'].includes(action)) {
      return NextResponse.json(
        { error: 'action must be approve, reject, or flag' },
        { status: 400 }
      );
    }

    const statusMap: Record<string, string> = {
      approve: 'approved',
      reject: 'rejected',
      flag: 'flagged',
    };

    const result = await queryOne<{ id: string; status: string }>(
      `UPDATE ad_ratings
       SET status = $2, updated_at = now()
       WHERE id = $1
       RETURNING id, status`,
      [review_id, statusMap[action]]
    );

    if (!result) {
      return NextResponse.json(
        { error: 'Review not found' },
        { status: 404 }
      );
    }

    // If approved, refresh aggregate for that ad
    if (action === 'approve') {
      const review = await queryOne<{ ad_id: string }>(
        `SELECT ad_id FROM ad_ratings WHERE id = $1`,
        [review_id]
      );
      if (review) {
        await query(`SELECT refresh_ad_feedback_agg($1)`, [review.ad_id]);
      }
    }

    return NextResponse.json({
      success: true,
      review_id: result.id,
      new_status: result.status,
    });
  } catch (error) {
    console.error('Error moderating review:', error);
    return NextResponse.json(
      { error: 'Failed to moderate review' },
      { status: 500 }
    );
  }
}
