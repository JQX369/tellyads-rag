/**
 * Admin Analytics SEO Hygiene API
 *
 * GET /api/admin/analytics/seo?days=7
 *
 * Returns SEO hygiene metrics: 404s, legacy redirects.
 * Requires admin authentication.
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryAll, queryOne } from '@/lib/db';
import { verifyAdmin } from '@/lib/admin-auth';

export const runtime = 'nodejs';

export async function GET(request: NextRequest) {
  // Verify admin auth
  const authResult = await verifyAdmin(request);
  if (!authResult.success) {
    return NextResponse.json({ error: authResult.error }, { status: 401 });
  }

  try {
    const { searchParams } = new URL(request.url);
    const days = Math.min(parseInt(searchParams.get('days') || '7', 10), 30);

    // Check if SEO events table exists
    const tableExists = await queryOne(
      `SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'analytics_seo_events'
      ) as exists`
    );

    if (!tableExists?.exists) {
      // Fall back to main analytics_events for seo.* events
      const fallback404s = await queryAll(`
        SELECT
          path,
          COUNT(*) as count,
          MAX(ts) as last_seen
        FROM analytics_events
        WHERE event = 'seo.404'
          AND event_date >= CURRENT_DATE - $1
        GROUP BY path
        ORDER BY count DESC
        LIMIT 20
      `, [days]);

      const fallbackRedirects = await queryAll(`
        SELECT
          path,
          props->>'redirect_to' as redirect_to,
          COUNT(*) as count,
          MAX(ts) as last_seen
        FROM analytics_events
        WHERE event = 'seo.legacy_redirect'
          AND event_date >= CURRENT_DATE - $1
        GROUP BY path, props->>'redirect_to'
        ORDER BY count DESC
        LIMIT 20
      `, [days]);

      return NextResponse.json({
        top_404s: fallback404s.map(row => ({
          path: row.path,
          count: Number(row.count) || 0,
          last_seen: row.last_seen,
        })),
        legacy_redirects: fallbackRedirects.map(row => ({
          path: row.path,
          redirect_to: row.redirect_to,
          count: Number(row.count) || 0,
          last_seen: row.last_seen,
        })),
        total_404s_7d: fallback404s.reduce((sum, r) => sum + (Number(r.count) || 0), 0),
        total_redirects_7d: fallbackRedirects.reduce((sum, r) => sum + (Number(r.count) || 0), 0),
      });
    }

    // Use dedicated SEO events table
    const top404s = await queryAll(`
      SELECT * FROM top_404_paths
    `);

    const legacyRedirects = await queryAll(`
      SELECT * FROM legacy_redirect_hits
    `);

    // Summary stats
    const summary = await queryOne(`
      SELECT
        COUNT(*) FILTER (WHERE event_type = '404') as total_404s,
        COUNT(*) FILTER (WHERE event_type = 'legacy_redirect') as total_redirects,
        COUNT(DISTINCT path) FILTER (WHERE event_type = '404') as unique_404_paths
      FROM analytics_seo_events
      WHERE event_date >= CURRENT_DATE - $1
    `, [days]);

    return NextResponse.json({
      top_404s: top404s.map(row => ({
        path: row.path,
        count: Number(row.count) || 0,
        last_seen: row.last_seen,
        referrers: row.referrers || [],
      })),
      legacy_redirects: legacyRedirects.map(row => ({
        path: row.path,
        redirect_to: row.redirect_to,
        count: Number(row.count) || 0,
        last_seen: row.last_seen,
      })),
      total_404s_7d: Number(summary?.total_404s) || 0,
      total_redirects_7d: Number(summary?.total_redirects) || 0,
      unique_404_paths: Number(summary?.unique_404_paths) || 0,
    });
  } catch (error) {
    console.error('SEO analytics error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch SEO data' },
      { status: 500 }
    );
  }
}
