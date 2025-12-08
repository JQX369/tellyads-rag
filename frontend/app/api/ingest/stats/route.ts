/**
 * Ingest Queue Stats API Route
 *
 * GET /api/ingest/stats - Get job queue statistics
 *
 * Admin-only endpoint that returns queue health metrics.
 */

import { NextRequest, NextResponse } from 'next/server';
import { verifyAdminKey } from '@/lib/admin-auth';
import { getQueueStats, getDeadLetterJobs } from '@/lib/job-queue';

export const runtime = 'nodejs';

export async function GET(request: NextRequest) {
  // Verify admin authentication
  const adminKey = request.headers.get('x-admin-key');
  const auth = verifyAdminKey(adminKey);

  if (!auth.verified) {
    return NextResponse.json(
      { error: auth.error || 'Unauthorized' },
      { status: 401 }
    );
  }

  try {
    // Get queue stats
    const stats = await getQueueStats();

    // Get dead letter count
    const deadLetterJobs = await getDeadLetterJobs(1);
    const hasDeadLetter = deadLetterJobs.length > 0;

    // Calculate health status
    const running = stats.by_status.RUNNING || 0;
    const queued = stats.by_status.QUEUED || 0;
    const retry = stats.by_status.RETRY || 0;
    const failed = stats.by_status.FAILED || 0;

    let health: 'healthy' | 'degraded' | 'critical';
    if (failed > 10 || retry > 20) {
      health = 'critical';
    } else if (failed > 0 || retry > 5) {
      health = 'degraded';
    } else {
      health = 'healthy';
    }

    return NextResponse.json({
      stats,
      health,
      summary: {
        running,
        pending: queued + retry,
        failed,
        has_dead_letter: hasDeadLetter,
      },
    });
  } catch (error) {
    console.error('Error getting queue stats:', error);
    return NextResponse.json(
      { error: 'Failed to get queue stats' },
      { status: 500 }
    );
  }
}
