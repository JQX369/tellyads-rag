/**
 * Job Queue utilities for Next.js Route Handlers.
 *
 * Provides TypeScript wrappers for the DB-backed ingestion job queue.
 * Uses PostgreSQL functions defined in migrations/003_ingestion_jobs.sql.
 */

import { query, queryOne, queryAll } from './db';
import { createHash } from 'crypto';

// Job status enum matching SQL constraint
export type JobStatus = 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED' | 'RETRY';

// Job input payload
export interface JobInput {
  source_type: 's3' | 'url' | 'local';
  s3_key?: string;
  url?: string;
  external_id?: string;
  metadata?: Record<string, unknown>;
}

// Job output payload
export interface JobOutput {
  ad_id?: string;
  warnings?: string[];
  extraction_version?: string;
  already_existed?: boolean;
  elapsed_seconds?: number;
  stage_reached?: string;
}

// Full job record
export interface IngestionJob {
  id: string;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  status: JobStatus;
  priority: number;
  attempts: number;
  max_attempts: number;
  locked_at: string | null;
  locked_by: string | null;
  run_after: string;
  last_error: string | null;
  error_code: string | null;
  input: JobInput;
  output: JobOutput | null;
  idempotency_key: string;
  ad_id: string | null;
}

// Enqueue result
export interface EnqueueResult {
  job_id: string;
  status: JobStatus;
  already_existed: boolean;
}

// Queue stats
export interface QueueStats {
  status: JobStatus;
  count: number;
  avg_attempts: number;
  oldest: string | null;
  newest: string | null;
}

/**
 * Compute idempotency key for job input.
 * Uses SHA-256 hash of canonical input string.
 */
export function computeIdempotencyKey(input: JobInput): string {
  let canonical: string;

  if (input.s3_key) {
    canonical = `s3:${input.s3_key}`;
  } else if (input.url) {
    canonical = `url:${input.url}`;
  } else if (input.external_id) {
    canonical = `id:${input.external_id}`;
  } else {
    throw new Error('JobInput must have s3_key, url, or external_id');
  }

  return createHash('sha256').update(canonical).digest('hex').slice(0, 32);
}

/**
 * Enqueue a new ingestion job (idempotent).
 *
 * @param input - Job input payload
 * @param priority - Higher = more urgent (default 0)
 * @param maxAttempts - Max retry attempts before permanent failure
 * @returns EnqueueResult with job_id, status, and whether it already existed
 */
export async function enqueueJob(
  input: JobInput,
  priority: number = 0,
  maxAttempts: number = 5
): Promise<EnqueueResult> {
  const idempotencyKey = computeIdempotencyKey(input);

  const result = await queryOne<{
    job_id: string;
    status: JobStatus;
    already_existed: boolean;
  }>(
    'SELECT * FROM enqueue_job($1::jsonb, $2, $3, $4)',
    [JSON.stringify(input), idempotencyKey, priority, maxAttempts]
  );

  if (!result) {
    throw new Error('Failed to enqueue job');
  }

  return {
    job_id: result.job_id,
    status: result.status,
    already_existed: result.already_existed,
  };
}

/**
 * Get job by ID.
 */
export async function getJob(jobId: string): Promise<IngestionJob | null> {
  return queryOne<IngestionJob>(
    'SELECT * FROM ingestion_jobs WHERE id = $1',
    [jobId]
  );
}

/**
 * List jobs with optional filters.
 */
export async function listJobs(options: {
  status?: JobStatus;
  limit?: number;
  offset?: number;
}): Promise<IngestionJob[]> {
  const { status, limit = 50, offset = 0 } = options;

  if (status) {
    return queryAll<IngestionJob>(
      `SELECT id, created_at, updated_at, status, priority,
              attempts, max_attempts, last_error, error_code,
              input, output, ad_id, started_at, completed_at,
              locked_at, locked_by, run_after, idempotency_key
       FROM ingestion_jobs
       WHERE status = $1
       ORDER BY created_at DESC
       LIMIT $2 OFFSET $3`,
      [status, Math.min(limit, 200), offset]
    );
  }

  return queryAll<IngestionJob>(
    `SELECT id, created_at, updated_at, status, priority,
            attempts, max_attempts, last_error, error_code,
            input, output, ad_id, started_at, completed_at,
            locked_at, locked_by, run_after, idempotency_key
     FROM ingestion_jobs
     ORDER BY created_at DESC
     LIMIT $1 OFFSET $2`,
    [Math.min(limit, 200), offset]
  );
}

/**
 * Get queue statistics.
 */
export async function getQueueStats(): Promise<{
  by_status: Record<JobStatus, number>;
  total: number;
}> {
  const rows = await queryAll<QueueStats>('SELECT * FROM job_queue_stats');

  const byStatus: Record<string, number> = {};
  let total = 0;

  for (const row of rows) {
    byStatus[row.status] = Number(row.count);
    total += Number(row.count);
  }

  return {
    by_status: byStatus as Record<JobStatus, number>,
    total,
  };
}

/**
 * Cancel a queued job.
 */
export async function cancelJob(jobId: string): Promise<boolean> {
  const result = await queryOne<{ cancel_job: boolean }>(
    'SELECT cancel_job($1)',
    [jobId]
  );
  return result?.cancel_job ?? false;
}

/**
 * Get dead letter jobs (failed with max attempts reached).
 */
export async function getDeadLetterJobs(limit: number = 50): Promise<IngestionJob[]> {
  return queryAll<IngestionJob>(
    'SELECT * FROM dead_letter_jobs LIMIT $1',
    [Math.min(limit, 200)]
  );
}

/**
 * Retry a failed job (reset to QUEUED).
 */
export async function retryJob(jobId: string): Promise<boolean> {
  const result = await query(
    `UPDATE ingestion_jobs
     SET status = 'QUEUED',
         attempts = 0,
         last_error = NULL,
         error_code = NULL,
         run_after = NOW(),
         locked_at = NULL,
         locked_by = NULL,
         completed_at = NULL
     WHERE id = $1 AND status IN ('FAILED', 'CANCELLED')
     RETURNING id`,
    [jobId]
  );
  return result.rowCount !== null && result.rowCount > 0;
}

/**
 * Validate job input.
 */
export function validateJobInput(input: unknown): { valid: boolean; error?: string; input?: JobInput } {
  if (!input || typeof input !== 'object') {
    return { valid: false, error: 'Input must be an object' };
  }

  const obj = input as Record<string, unknown>;

  // Validate source_type
  const validSourceTypes = ['s3', 'url', 'local'];
  if (!obj.source_type || !validSourceTypes.includes(obj.source_type as string)) {
    return { valid: false, error: `source_type must be one of: ${validSourceTypes.join(', ')}` };
  }

  // Require at least one identifier
  if (!obj.s3_key && !obj.url && !obj.external_id) {
    return { valid: false, error: 'Must provide s3_key, url, or external_id' };
  }

  // Validate s3_key format
  if (obj.s3_key && typeof obj.s3_key !== 'string') {
    return { valid: false, error: 's3_key must be a string' };
  }

  // Validate url format
  if (obj.url) {
    if (typeof obj.url !== 'string') {
      return { valid: false, error: 'url must be a string' };
    }
    try {
      new URL(obj.url as string);
    } catch {
      return { valid: false, error: 'url must be a valid URL' };
    }
  }

  return {
    valid: true,
    input: {
      source_type: obj.source_type as 's3' | 'url' | 'local',
      s3_key: obj.s3_key as string | undefined,
      url: obj.url as string | undefined,
      external_id: obj.external_id as string | undefined,
      metadata: obj.metadata as Record<string, unknown> | undefined,
    },
  };
}
