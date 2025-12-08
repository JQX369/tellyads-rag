/**
 * Running Jobs Monitor API Route
 *
 * GET /api/ingest/monitor/running - Get currently running jobs with timing info
 *
 * Admin-only endpoint that returns data from running_jobs_monitor view.
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
    const jobs = await queryAll(`
      SELECT
        id,
        created_at,
        processing_started_at,
        last_heartbeat_at,
        EXTRACT(EPOCH FROM (now() - processing_started_at))::int as running_seconds,
        EXTRACT(EPOCH FROM (now() - last_heartbeat_at))::int as heartbeat_age_seconds,
        stage,
        progress,
        attempts,
        max_attempts,
        locked_by,
        input->>'s3_key' as s3_key,
        input->>'external_id' as external_id,
        input->>'source_type' as source_type
      FROM ingestion_jobs
      WHERE status = 'RUNNING'
      ORDER BY processing_started_at ASC
    `);

    return NextResponse.json({ jobs });
  } catch (error) {
    console.error('Error fetching running jobs:', error);
    return NextResponse.json(
      { error: 'Failed to fetch running jobs' },
      { status: 500 }
    );
  }
}
