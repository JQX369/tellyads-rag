/**
 * Admin Analytics Daily Data API
 *
 * GET /api/admin/analytics/daily?days=30
 *
 * Returns daily time-series data for charts.
 * Requires admin authentication.
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryAll, queryOne } from '@/lib/db';
import { verifyAdminKey } from '@/lib/admin-auth';

export const runtime = 'nodejs';

interface DailyDataPoint {
  date: string;
  pageviews: number;
  sessions: number;
  searches: number;
  ad_views: number;
}

export async function GET(request: NextRequest) {
  // Verify admin auth
  const authResult = await verifyAdminKey(request);
  if (!authResult.success) {
    return NextResponse.json({ error: authResult.error }, { status: 401 });
  }

  try {
    const { searchParams } = new URL(request.url);
    const days = Math.min(parseInt(searchParams.get('days') || '30', 10), 90);

    // Check if rollup tables exist
    const tableExists = await queryOne(
      `SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'analytics_daily_events'
      ) as exists`
    );

    if (!tableExists?.exists) {
      return NextResponse.json({ data: [] });
    }

    // Get daily data from rollups
    const rows = await queryAll(`
      SELECT
        date,
        COALESCE(SUM(count) FILTER (WHERE event = 'page.view'), 0) as pageviews,
        COALESCE(MAX(unique_sessions) FILTER (WHERE event = 'page.view'), 0) as sessions,
        COALESCE(SUM(count) FILTER (WHERE event = 'search.performed'), 0) as searches,
        COALESCE(SUM(count) FILTER (WHERE event = 'advert.view'), 0) as ad_views
      FROM analytics_daily_events
      WHERE date >= CURRENT_DATE - $1
      GROUP BY date
      ORDER BY date ASC
    `, [days]);

    const data: DailyDataPoint[] = rows.map(row => ({
      date: row.date instanceof Date ? row.date.toISOString().split('T')[0] : String(row.date),
      pageviews: Number(row.pageviews) || 0,
      sessions: Number(row.sessions) || 0,
      searches: Number(row.searches) || 0,
      ad_views: Number(row.ad_views) || 0,
    }));

    return NextResponse.json({ data });
  } catch (error) {
    console.error('Analytics daily data error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch daily data' },
      { status: 500 }
    );
  }
}
