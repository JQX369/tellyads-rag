/**
 * Ingest Job Detail API Route
 *
 * GET /api/ingest/jobs/:id - Get job details
 * POST /api/ingest/jobs/:id - Actions: cancel, retry
 *
 * Admin-only endpoint for job management.
 */

import { NextRequest, NextResponse } from 'next/server';
import { verifyAdminKey } from '@/lib/admin-auth';
import { getJob, cancelJob, retryJob } from '@/lib/job-queue';

export const runtime = 'nodejs';

// UUID v4 regex pattern
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

interface RouteParams {
  params: Promise<{ id: string }>;
}

export async function GET(request: NextRequest, { params }: RouteParams) {
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
    const { id } = await params;

    // Validate UUID format
    if (!UUID_PATTERN.test(id)) {
      return NextResponse.json(
        { error: 'Invalid job ID format. Must be a valid UUID.' },
        { status: 400 }
      );
    }

    // Get job
    const job = await getJob(id);

    if (!job) {
      return NextResponse.json(
        { error: 'Job not found' },
        { status: 404 }
      );
    }

    return NextResponse.json(job);
  } catch (error) {
    console.error('Error getting job:', error);
    return NextResponse.json(
      { error: 'Failed to get job' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest, { params }: RouteParams) {
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
    const { id } = await params;

    // Validate UUID format
    if (!UUID_PATTERN.test(id)) {
      return NextResponse.json(
        { error: 'Invalid job ID format. Must be a valid UUID.' },
        { status: 400 }
      );
    }

    // Parse action from body
    const body = await request.json();
    const action = body.action;

    if (!action || !['cancel', 'retry'].includes(action)) {
      return NextResponse.json(
        { error: 'action must be "cancel" or "retry"' },
        { status: 400 }
      );
    }

    let success: boolean;
    let message: string;

    if (action === 'cancel') {
      success = await cancelJob(id);
      message = success
        ? 'Job cancelled successfully'
        : 'Job could not be cancelled (may not be in cancellable state)';
    } else {
      success = await retryJob(id);
      message = success
        ? 'Job queued for retry'
        : 'Job could not be retried (may not be in failed state)';
    }

    return NextResponse.json({
      success,
      message,
      job_id: id,
      action,
    });
  } catch (error) {
    console.error('Error performing job action:', error);
    return NextResponse.json(
      { error: 'Failed to perform action' },
      { status: 500 }
    );
  }
}
