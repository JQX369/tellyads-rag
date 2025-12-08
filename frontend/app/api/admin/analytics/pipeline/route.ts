/**
 * Admin Analytics Pipeline Health API
 *
 * GET /api/admin/analytics/pipeline
 *
 * Returns ingestion pipeline health metrics.
 * Requires admin authentication.
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryAll, queryOne } from '@/lib/db';
import { verifyAdminKey } from '@/lib/admin-auth';

export const runtime = 'nodejs';

interface PipelineHealth {
  // Job queue status
  jobs_queued: number;
  jobs_running: number;
  jobs_completed_24h: number;
  jobs_failed_24h: number;

  // Data quality
  total_ads: number;
  ads_with_embeddings: number;
  ads_with_transcripts: number;
  ads_missing_embeddings: number;

  // Recent errors
  recent_errors: Array<{
    error_code: string;
    count: number;
    last_seen: string;
  }>;
}

export async function GET(request: NextRequest) {
  // Verify admin auth
  const authResult = await verifyAdminKey(request);
  if (!authResult.success) {
    return NextResponse.json({ error: authResult.error }, { status: 401 });
  }

  try {
    // Check if ingestion_jobs table exists
    const jobsTableExists = await queryOne(
      `SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'ingestion_jobs'
      ) as exists`
    );

    let jobStats = {
      jobs_queued: 0,
      jobs_running: 0,
      jobs_completed_24h: 0,
      jobs_failed_24h: 0,
    };

    let recentErrors: Array<{ error_code: string; count: number; last_seen: string }> = [];

    if (jobsTableExists?.exists) {
      // Job queue status
      const queueStats = await queryOne(`
        SELECT
          COUNT(*) FILTER (WHERE status IN ('QUEUED', 'RETRY')) as queued,
          COUNT(*) FILTER (WHERE status = 'RUNNING') as running,
          COUNT(*) FILTER (WHERE status = 'SUCCEEDED' AND completed_at >= NOW() - INTERVAL '24 hours') as completed_24h,
          COUNT(*) FILTER (WHERE status = 'FAILED' AND completed_at >= NOW() - INTERVAL '24 hours') as failed_24h
        FROM ingestion_jobs
      `);

      if (queueStats) {
        jobStats = {
          jobs_queued: Number(queueStats.queued) || 0,
          jobs_running: Number(queueStats.running) || 0,
          jobs_completed_24h: Number(queueStats.completed_24h) || 0,
          jobs_failed_24h: Number(queueStats.failed_24h) || 0,
        };
      }

      // Recent errors
      const errors = await queryAll(`
        SELECT
          COALESCE(error_code, 'UNKNOWN') as error_code,
          COUNT(*) as count,
          MAX(completed_at) as last_seen
        FROM ingestion_jobs
        WHERE status = 'FAILED'
          AND completed_at >= NOW() - INTERVAL '7 days'
        GROUP BY error_code
        ORDER BY count DESC
        LIMIT 10
      `);

      recentErrors = errors.map(row => ({
        error_code: row.error_code,
        count: Number(row.count) || 0,
        last_seen: row.last_seen instanceof Date ? row.last_seen.toISOString() : String(row.last_seen),
      }));
    }

    // Data quality from ads table
    const adStats = await queryOne(`
      SELECT
        COUNT(*) as total_ads,
        COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_embeddings,
        COUNT(*) FILTER (WHERE raw_transcript IS NOT NULL) as with_transcripts
      FROM ads
    `);

    const totalAds = Number(adStats?.total_ads) || 0;
    const withEmbeddings = Number(adStats?.with_embeddings) || 0;
    const withTranscripts = Number(adStats?.with_transcripts) || 0;

    const response: PipelineHealth = {
      ...jobStats,
      total_ads: totalAds,
      ads_with_embeddings: withEmbeddings,
      ads_with_transcripts: withTranscripts,
      ads_missing_embeddings: totalAds - withEmbeddings,
      recent_errors: recentErrors,
    };

    return NextResponse.json(response);
  } catch (error) {
    console.error('Pipeline health data error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch pipeline data' },
      { status: 500 }
    );
  }
}
