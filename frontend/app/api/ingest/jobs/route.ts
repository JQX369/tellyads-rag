/**
 * Ingest Jobs API Route
 *
 * GET /api/ingest/jobs - List ingestion jobs
 *
 * Admin-only endpoint that returns job queue status.
 * Supports filtering by status and pagination.
 */

import { NextRequest, NextResponse } from 'next/server';
import { verifyAdminKey } from '@/lib/admin-auth';
import { listJobs, getQueueStats, getDeadLetterJobs, JobStatus } from '@/lib/job-queue';

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
    const { searchParams } = new URL(request.url);

    // Parse query parameters
    const status = searchParams.get('status')?.toUpperCase() as JobStatus | undefined;
    const limit = Math.min(parseInt(searchParams.get('limit') || '50', 10), 200);
    const offset = parseInt(searchParams.get('offset') || '0', 10);
    const includeStats = searchParams.get('stats') === 'true';
    const deadLetter = searchParams.get('dead_letter') === 'true';

    // Validate status if provided
    const validStatuses: JobStatus[] = ['QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'RETRY'];
    if (status && !validStatuses.includes(status)) {
      return NextResponse.json(
        { error: `Invalid status. Must be one of: ${validStatuses.join(', ')}` },
        { status: 400 }
      );
    }

    // Get dead letter jobs if requested
    if (deadLetter) {
      const jobs = await getDeadLetterJobs(limit);
      return NextResponse.json({
        jobs,
        count: jobs.length,
        dead_letter: true,
      });
    }

    // Get jobs
    const jobs = await listJobs({ status, limit, offset });

    // Build response
    const response: Record<string, unknown> = {
      jobs,
      count: jobs.length,
      limit,
      offset,
    };

    // Include stats if requested
    if (includeStats) {
      response.stats = await getQueueStats();
    }

    return NextResponse.json(response);
  } catch (error) {
    console.error('Error listing jobs:', error);
    return NextResponse.json(
      { error: 'Failed to list jobs' },
      { status: 500 }
    );
  }
}
