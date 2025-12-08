/**
 * Ingest Enqueue API Route
 *
 * POST /api/ingest/enqueue - Enqueue a new ingestion job
 *
 * Admin-only endpoint that creates jobs in the DB-backed queue.
 * Jobs are processed by the Railway worker.
 */

import { NextRequest, NextResponse } from 'next/server';
import { verifyAdminKey } from '@/lib/admin-auth';
import { enqueueJob, validateJobInput, computeIdempotencyKey } from '@/lib/job-queue';

export const runtime = 'nodejs';

export async function POST(request: NextRequest) {
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
    // Parse request body
    const body = await request.json();

    // Validate input
    const validation = validateJobInput(body);
    if (!validation.valid || !validation.input) {
      return NextResponse.json(
        { error: validation.error },
        { status: 400 }
      );
    }

    const { input } = validation;

    // Extract optional parameters
    const priority = typeof body.priority === 'number' ? body.priority : 0;
    const maxAttempts = typeof body.max_attempts === 'number' ? body.max_attempts : 5;

    // Enqueue job (idempotent)
    const result = await enqueueJob(input, priority, maxAttempts);

    // Return result with appropriate status
    const status = result.already_existed ? 200 : 201;
    return NextResponse.json(
      {
        job_id: result.job_id,
        status: result.status,
        already_existed: result.already_existed,
        idempotency_key: computeIdempotencyKey(input),
      },
      { status }
    );
  } catch (error) {
    console.error('Error enqueueing job:', error);
    return NextResponse.json(
      { error: 'Failed to enqueue job' },
      { status: 500 }
    );
  }
}
