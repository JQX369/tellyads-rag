/**
 * Admin Analytics Rollup API
 *
 * POST /api/admin/analytics/rollup
 *
 * Runs daily rollup aggregations. Call from Vercel cron or manually.
 * Also handles weekly pruning of old events.
 *
 * Vercel Cron configuration (in vercel.json):
 * {
 *   "crons": [{
 *     "path": "/api/admin/analytics/rollup",
 *     "schedule": "0 1 * * *"  // 1 AM UTC daily
 *   }]
 * }
 */

import { NextRequest, NextResponse } from 'next/server';
import { query, queryOne } from '@/lib/db';
import { verifyAdmin } from '@/lib/admin-auth';

export const runtime = 'nodejs';

// Vercel cron sends a specific header
const VERCEL_CRON_SECRET = process.env.CRON_SECRET;

function isVercelCron(request: NextRequest): boolean {
  // Vercel cron jobs include this header
  const authHeader = request.headers.get('authorization');
  if (VERCEL_CRON_SECRET && authHeader === `Bearer ${VERCEL_CRON_SECRET}`) {
    return true;
  }

  // Also check for Vercel's internal cron header
  const cronHeader = request.headers.get('x-vercel-cron');
  return cronHeader === '1';
}

export async function POST(request: NextRequest) {
  // Allow either admin auth or Vercel cron
  const isCron = isVercelCron(request);
  if (!isCron) {
    const authResult = await verifyAdmin(request);
    if (!authResult.success) {
      return NextResponse.json({ error: authResult.error }, { status: 401 });
    }
  }

  try {
    const results: Array<{ task: string; status: string; details?: string }> = [];

    // Parse optional date parameter (defaults to yesterday UTC)
    const { searchParams } = new URL(request.url);
    const dateParam = searchParams.get('date');
    const targetDate = dateParam || null; // null = use SQL default (yesterday UTC)

    // Run rollup function
    try {
      if (targetDate) {
        await query(`SELECT rollup_daily_events($1::date)`, [targetDate]);
      } else {
        await query(`SELECT rollup_daily_events()`);
      }
      results.push({ task: 'rollup_daily_events', status: 'success' });
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Unknown error';
      results.push({ task: 'rollup_daily_events', status: 'error', details: msg });
    }

    // Check if it's time for weekly pruning (Sunday)
    const today = new Date();
    const isWeeklyPruneDay = today.getUTCDay() === 0; // Sunday

    if (isWeeklyPruneDay || searchParams.get('force_prune') === 'true') {
      try {
        const pruneResult = await queryOne(`SELECT prune_old_events(90) as deleted_count`);
        const deletedCount = pruneResult?.deleted_count || 0;
        results.push({
          task: 'prune_old_events',
          status: 'success',
          details: `Deleted ${deletedCount} events older than 90 days`,
        });
      } catch (error) {
        const msg = error instanceof Error ? error.message : 'Unknown error';
        results.push({ task: 'prune_old_events', status: 'error', details: msg });
      }
    }

    // Log completion for monitoring
    const successCount = results.filter(r => r.status === 'success').length;
    const errorCount = results.filter(r => r.status === 'error').length;
    console.log(`[Analytics Rollup] Completed: ${successCount} success, ${errorCount} errors`);

    return NextResponse.json({
      success: errorCount === 0,
      timestamp: new Date().toISOString(),
      target_date: targetDate || 'yesterday (UTC)',
      results,
    });
  } catch (error) {
    console.error('Analytics rollup error:', error);
    return NextResponse.json(
      { error: 'Rollup failed', details: error instanceof Error ? error.message : 'Unknown' },
      { status: 500 }
    );
  }
}

// GET for status check
export async function GET(request: NextRequest) {
  // Allow either admin auth or Vercel cron
  const isCron = isVercelCron(request);
  if (!isCron) {
    const authResult = await verifyAdmin(request);
    if (!authResult.success) {
      return NextResponse.json({ error: authResult.error }, { status: 401 });
    }
  }

  try {
    // Get last rollup dates from each table
    const lastRollups = await queryOne(`
      SELECT
        (SELECT MAX(date) FROM analytics_daily_events) as last_daily_events,
        (SELECT MAX(date) FROM analytics_daily_search) as last_daily_search,
        (SELECT MAX(date) FROM analytics_daily_funnel) as last_daily_funnel,
        (SELECT MIN(event_date) FROM analytics_events) as oldest_raw_event,
        (SELECT MAX(event_date) FROM analytics_events) as newest_raw_event,
        (SELECT COUNT(*) FROM analytics_events) as raw_event_count
    `);

    return NextResponse.json({
      status: 'ok',
      last_rollups: {
        daily_events: lastRollups?.last_daily_events,
        daily_search: lastRollups?.last_daily_search,
        daily_funnel: lastRollups?.last_daily_funnel,
      },
      raw_events: {
        oldest: lastRollups?.oldest_raw_event,
        newest: lastRollups?.newest_raw_event,
        count: Number(lastRollups?.raw_event_count) || 0,
      },
      retention_days: 90,
    });
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to check rollup status' },
      { status: 500 }
    );
  }
}
