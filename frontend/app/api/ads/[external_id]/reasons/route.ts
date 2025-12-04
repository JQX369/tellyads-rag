/**
 * Reasons API Route Handler
 *
 * GET /api/ads/[external_id]/reasons - Get reason counts
 * POST /api/ads/[external_id]/reasons - Submit a reason
 *
 * Reasons explain why users like an ad (e.g., "creative", "funny", "memorable").
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryOne, queryAll, transaction } from '@/lib/db';

export const runtime = 'nodejs';

interface RouteContext {
  params: Promise<{ external_id: string }>;
}

// Predefined reason labels
const VALID_REASONS = [
  'creative',
  'funny',
  'memorable',
  'emotional',
  'informative',
  'well_produced',
  'catchy_music',
  'good_acting',
  'clever_concept',
  'beautiful_visually',
];

export async function GET(request: NextRequest, context: RouteContext) {
  const { external_id } = await context.params;

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

    // Get reason aggregates
    const aggregates = await queryOne(
      `
      SELECT reason_counts, distinct_reason_sessions, reason_threshold_met
      FROM ad_feedback_aggregates
      WHERE ad_id = $1
      `,
      [ad.id]
    );

    return NextResponse.json({
      external_id,
      reason_counts: aggregates?.reason_counts || {},
      distinct_sessions: aggregates?.distinct_reason_sessions || 0,
      threshold_met: aggregates?.reason_threshold_met || false,
      valid_reasons: VALID_REASONS,
    });
  } catch (error) {
    console.error('Error fetching reasons:', error);
    return NextResponse.json(
      { error: 'Failed to fetch reasons' },
      { status: 500 }
    );
  }
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
    const body = await request.json();
    const { session_id, reason } = body;

    if (!session_id) {
      return NextResponse.json(
        { error: 'session_id is required' },
        { status: 400 }
      );
    }

    if (!reason || !VALID_REASONS.includes(reason)) {
      return NextResponse.json(
        { error: `Invalid reason. Must be one of: ${VALID_REASONS.join(', ')}` },
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

    await transaction(async (client) => {
      // Check if this session already submitted a reason
      const existing = await client.query(
        `SELECT id FROM ad_reasons WHERE ad_id = $1 AND session_id = $2`,
        [adId, session_id]
      );

      if (existing.rows.length > 0) {
        // Update existing reason
        await client.query(
          `UPDATE ad_reasons SET reason = $1, updated_at = NOW() WHERE ad_id = $2 AND session_id = $3`,
          [reason, adId, session_id]
        );
      } else {
        // Insert new reason
        await client.query(
          `INSERT INTO ad_reasons (ad_id, session_id, reason) VALUES ($1, $2, $3)`,
          [adId, session_id, reason]
        );
      }

      // Recompute aggregates
      const reasonCounts = await client.query(
        `
        SELECT reason, COUNT(*) as count
        FROM ad_reasons
        WHERE ad_id = $1
        GROUP BY reason
        `,
        [adId]
      );

      const distinctSessions = await client.query(
        `SELECT COUNT(DISTINCT session_id) as count FROM ad_reasons WHERE ad_id = $1`,
        [adId]
      );

      const counts: Record<string, number> = {};
      for (const row of reasonCounts.rows) {
        counts[row.reason] = parseInt(row.count, 10);
      }

      const sessionCount = parseInt(distinctSessions.rows[0]?.count || '0', 10);
      const thresholdMet = sessionCount >= 3; // Require at least 3 unique sessions

      // Update aggregate
      await client.query(
        `
        INSERT INTO ad_feedback_aggregates (ad_id, reason_counts, distinct_reason_sessions, reason_threshold_met)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (ad_id)
        DO UPDATE SET
          reason_counts = $2,
          distinct_reason_sessions = $3,
          reason_threshold_met = $4,
          updated_at = NOW()
        `,
        [adId, JSON.stringify(counts), sessionCount, thresholdMet]
      );
    });

    // Get updated aggregates
    const aggregates = await queryOne(
      `
      SELECT reason_counts, distinct_reason_sessions, reason_threshold_met
      FROM ad_feedback_aggregates
      WHERE ad_id = $1
      `,
      [adId]
    );

    return NextResponse.json({
      success: true,
      reason_counts: aggregates?.reason_counts || {},
      distinct_sessions: aggregates?.distinct_reason_sessions || 0,
      threshold_met: aggregates?.reason_threshold_met || false,
    });
  } catch (error) {
    console.error('Error submitting reason:', error);
    return NextResponse.json(
      { error: 'Failed to submit reason' },
      { status: 500 }
    );
  }
}
