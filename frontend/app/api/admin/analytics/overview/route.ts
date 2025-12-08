/**
 * Admin Analytics Overview API
 *
 * GET /api/admin/analytics/overview
 *
 * Returns high-level analytics metrics for the admin dashboard.
 * Requires admin authentication.
 */

import { NextRequest, NextResponse } from 'next/server';
import { query, queryOne, queryAll } from '@/lib/db';
import { verifyAdminKey } from '@/lib/admin-auth';

export const runtime = 'nodejs';

interface OverviewMetrics {
  // Today
  events_today: number;
  sessions_today: number;
  pageviews_today: number;
  searches_today: number;

  // 7 day totals
  pageviews_7d: number;
  sessions_7d: number;
  searches_7d: number;
  ad_views_7d: number;

  // Trends (percentage change vs previous period)
  pageviews_trend: number | null;
  sessions_trend: number | null;
  searches_trend: number | null;

  // Funnel (7 day averages)
  avg_search_rate: number | null;
  avg_view_rate: number | null;
  avg_engagement_rate: number | null;
}

export async function GET(request: NextRequest) {
  // Verify admin auth
  const authResult = await verifyAdminKey(request);
  if (!authResult.success) {
    return NextResponse.json({ error: authResult.error }, { status: 401 });
  }

  try {
    // Check if analytics tables exist
    const tableExists = await queryOne(
      `SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'analytics_events'
      ) as exists`
    );

    if (!tableExists?.exists) {
      // Return zeros if tables don't exist yet
      return NextResponse.json({
        events_today: 0,
        sessions_today: 0,
        pageviews_today: 0,
        searches_today: 0,
        pageviews_7d: 0,
        sessions_7d: 0,
        searches_7d: 0,
        ad_views_7d: 0,
        pageviews_trend: null,
        sessions_trend: null,
        searches_trend: null,
        avg_search_rate: null,
        avg_view_rate: null,
        avg_engagement_rate: null,
      });
    }

    // Today's metrics from raw events
    const todayMetrics = await queryOne(`
      SELECT
        COUNT(*) as events_today,
        COUNT(DISTINCT session_id) as sessions_today,
        COUNT(*) FILTER (WHERE event = 'page.view') as pageviews_today,
        COUNT(*) FILTER (WHERE event = 'search.performed') as searches_today
      FROM analytics_events
      WHERE event_date = CURRENT_DATE
    `);

    // Check if rollup tables have data
    const rollupExists = await queryOne(
      `SELECT EXISTS (
        SELECT 1 FROM analytics_daily_events LIMIT 1
      ) as exists`
    );

    let metrics7d = {
      pageviews_7d: 0,
      sessions_7d: 0,
      searches_7d: 0,
      ad_views_7d: 0,
    };

    let trends = {
      pageviews_trend: null as number | null,
      sessions_trend: null as number | null,
      searches_trend: null as number | null,
    };

    let funnel = {
      avg_search_rate: null as number | null,
      avg_view_rate: null as number | null,
      avg_engagement_rate: null as number | null,
    };

    if (rollupExists?.exists) {
      // 7 day metrics from rollups
      const weekMetrics = await queryOne(`
        SELECT
          COALESCE(SUM(count) FILTER (WHERE event = 'page.view'), 0) as pageviews_7d,
          COALESCE(SUM(unique_sessions) FILTER (WHERE event = 'page.view'), 0) as sessions_7d,
          COALESCE(SUM(count) FILTER (WHERE event = 'search.performed'), 0) as searches_7d,
          COALESCE(SUM(count) FILTER (WHERE event = 'advert.view'), 0) as ad_views_7d
        FROM analytics_daily_events
        WHERE date >= CURRENT_DATE - 7
      `);

      if (weekMetrics) {
        metrics7d = {
          pageviews_7d: Number(weekMetrics.pageviews_7d) || 0,
          sessions_7d: Number(weekMetrics.sessions_7d) || 0,
          searches_7d: Number(weekMetrics.searches_7d) || 0,
          ad_views_7d: Number(weekMetrics.ad_views_7d) || 0,
        };
      }

      // Previous 7 days for trend calculation
      const prevWeekMetrics = await queryOne(`
        SELECT
          COALESCE(SUM(count) FILTER (WHERE event = 'page.view'), 0) as pageviews_prev,
          COALESCE(SUM(unique_sessions) FILTER (WHERE event = 'page.view'), 0) as sessions_prev,
          COALESCE(SUM(count) FILTER (WHERE event = 'search.performed'), 0) as searches_prev
        FROM analytics_daily_events
        WHERE date >= CURRENT_DATE - 14 AND date < CURRENT_DATE - 7
      `);

      if (prevWeekMetrics) {
        const pvPrev = Number(prevWeekMetrics.pageviews_prev) || 0;
        const sessPrev = Number(prevWeekMetrics.sessions_prev) || 0;
        const searchPrev = Number(prevWeekMetrics.searches_prev) || 0;

        trends = {
          pageviews_trend: pvPrev > 0 ? ((metrics7d.pageviews_7d - pvPrev) / pvPrev) * 100 : null,
          sessions_trend: sessPrev > 0 ? ((metrics7d.sessions_7d - sessPrev) / sessPrev) * 100 : null,
          searches_trend: searchPrev > 0 ? ((metrics7d.searches_7d - searchPrev) / searchPrev) * 100 : null,
        };
      }

      // Check if funnel table exists and has data
      const funnelExists = await queryOne(
        `SELECT EXISTS (
          SELECT 1 FROM analytics_daily_funnel LIMIT 1
        ) as exists`
      );

      if (funnelExists?.exists) {
        const funnelMetrics = await queryOne(`
          SELECT
            AVG(search_rate) as avg_search_rate,
            AVG(view_rate) as avg_view_rate,
            AVG(engagement_rate) as avg_engagement_rate
          FROM analytics_daily_funnel
          WHERE date >= CURRENT_DATE - 7
        `);

        if (funnelMetrics) {
          funnel = {
            avg_search_rate: funnelMetrics.avg_search_rate ? Number(funnelMetrics.avg_search_rate) : null,
            avg_view_rate: funnelMetrics.avg_view_rate ? Number(funnelMetrics.avg_view_rate) : null,
            avg_engagement_rate: funnelMetrics.avg_engagement_rate ? Number(funnelMetrics.avg_engagement_rate) : null,
          };
        }
      }
    }

    const response: OverviewMetrics = {
      events_today: Number(todayMetrics?.events_today) || 0,
      sessions_today: Number(todayMetrics?.sessions_today) || 0,
      pageviews_today: Number(todayMetrics?.pageviews_today) || 0,
      searches_today: Number(todayMetrics?.searches_today) || 0,
      ...metrics7d,
      ...trends,
      ...funnel,
    };

    return NextResponse.json(response);
  } catch (error) {
    console.error('Analytics overview error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch analytics' },
      { status: 500 }
    );
  }
}
