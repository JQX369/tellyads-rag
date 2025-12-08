/**
 * Job Timing Stats API Route
 *
 * GET /api/ingest/monitor/timing - Get job duration statistics
 *
 * Admin-only endpoint that returns data from job_timing_stats view.
 */

import { NextRequest, NextResponse } from 'next/server';
import { verifyAdminKey } from '@/lib/admin-auth';
import { queryAll } from '@/lib/db';

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
    const stats = await queryAll(`
      SELECT
        status,
        COUNT(*) as count,
        AVG(EXTRACT(EPOCH FROM (processing_completed_at - processing_started_at)))::int as avg_duration_seconds,
        MIN(EXTRACT(EPOCH FROM (processing_completed_at - processing_started_at)))::int as min_duration_seconds,
        MAX(EXTRACT(EPOCH FROM (processing_completed_at - processing_started_at)))::int as max_duration_seconds,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (processing_completed_at - processing_started_at)))::int as p50_seconds,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (processing_completed_at - processing_started_at)))::int as p95_seconds
      FROM ingestion_jobs
      WHERE processing_started_at IS NOT NULL
        AND processing_completed_at IS NOT NULL
      GROUP BY status
    `);

    // Get recent throughput (last 24h)
    const throughput = await queryAll(`
      SELECT
        date_trunc('hour', completed_at) as hour,
        COUNT(*) as completed,
        COUNT(*) FILTER (WHERE status = 'SUCCEEDED') as succeeded,
        COUNT(*) FILTER (WHERE status = 'FAILED') as failed
      FROM ingestion_jobs
      WHERE completed_at >= NOW() - INTERVAL '24 hours'
      GROUP BY date_trunc('hour', completed_at)
      ORDER BY hour DESC
    `);

    return NextResponse.json({ stats, throughput });
  } catch (error) {
    console.error('Error fetching timing stats:', error);
    return NextResponse.json(
      { error: 'Failed to fetch timing stats' },
      { status: 500 }
    );
  }
}
