/**
 * Stage Distribution API Route
 *
 * GET /api/ingest/monitor/stages - Get job distribution by stage
 *
 * Admin-only endpoint that returns data from stage_distribution view.
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
    const distribution = await queryAll(`
      SELECT
        stage,
        status,
        COUNT(*) as count
      FROM ingestion_jobs
      WHERE stage IS NOT NULL
      GROUP BY stage, status
      ORDER BY count DESC
    `);

    // Also get stage failure rates
    const stageFailures = await queryAll(`
      SELECT
        stage,
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE status = 'FAILED') as failed,
        ROUND(
          COUNT(*) FILTER (WHERE status = 'FAILED')::numeric /
          NULLIF(COUNT(*), 0) * 100, 2
        ) as failure_rate
      FROM ingestion_jobs
      WHERE stage IS NOT NULL
        AND status IN ('SUCCEEDED', 'FAILED')
      GROUP BY stage
      ORDER BY failure_rate DESC NULLS LAST
    `);

    return NextResponse.json({ distribution, stageFailures });
  } catch (error) {
    console.error('Error fetching stage distribution:', error);
    return NextResponse.json(
      { error: 'Failed to fetch stage distribution' },
      { status: 500 }
    );
  }
}
