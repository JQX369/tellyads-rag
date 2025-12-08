/**
 * Admin Analytics Search Intelligence API
 *
 * GET /api/admin/analytics/search?days=7
 *
 * Returns top search queries and zero-result queries.
 * Requires admin authentication.
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryAll, queryOne } from '@/lib/db';
import { verifyAdminKey } from '@/lib/admin-auth';

export const runtime = 'nodejs';

interface SearchQuery {
  query: string;
  count: number;
  unique_sessions: number;
  avg_results: number | null;
  zero_result_count: number;
}

export async function GET(request: NextRequest) {
  // Verify admin auth
  const authResult = await verifyAdminKey(request);
  if (!authResult.success) {
    return NextResponse.json({ error: authResult.error }, { status: 401 });
  }

  try {
    const { searchParams } = new URL(request.url);
    const days = Math.min(parseInt(searchParams.get('days') || '7', 10), 30);

    // Check if search rollup table exists
    const tableExists = await queryOne(
      `SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'analytics_daily_search'
      ) as exists`
    );

    if (!tableExists?.exists) {
      return NextResponse.json({
        top_queries: [],
        zero_result_queries: [],
        total_searches: 0,
        unique_queries: 0,
        zero_result_rate: 0,
      });
    }

    // Top queries
    const topQueries = await queryAll(`
      SELECT
        query_normalized as query,
        SUM(search_count) as count,
        SUM(unique_sessions) as unique_sessions,
        AVG(avg_results_count) as avg_results,
        SUM(zero_result_count) as zero_result_count
      FROM analytics_daily_search
      WHERE date >= CURRENT_DATE - $1
      GROUP BY query_normalized
      ORDER BY count DESC
      LIMIT 20
    `, [days]);

    // Zero result queries
    const zeroResultQueries = await queryAll(`
      SELECT
        query_normalized as query,
        SUM(search_count) as count,
        SUM(zero_result_count) as zero_count
      FROM analytics_daily_search
      WHERE date >= CURRENT_DATE - $1
      GROUP BY query_normalized
      HAVING SUM(zero_result_count) > 0
      ORDER BY zero_count DESC
      LIMIT 15
    `, [days]);

    // Summary stats
    const summary = await queryOne(`
      SELECT
        COALESCE(SUM(search_count), 0) as total_searches,
        COUNT(DISTINCT query_normalized) as unique_queries,
        COALESCE(SUM(zero_result_count), 0) as total_zero_results
      FROM analytics_daily_search
      WHERE date >= CURRENT_DATE - $1
    `, [days]);

    const totalSearches = Number(summary?.total_searches) || 0;
    const totalZeroResults = Number(summary?.total_zero_results) || 0;

    return NextResponse.json({
      top_queries: topQueries.map(row => ({
        query: row.query,
        count: Number(row.count) || 0,
        unique_sessions: Number(row.unique_sessions) || 0,
        avg_results: row.avg_results ? Number(row.avg_results) : null,
        zero_result_count: Number(row.zero_result_count) || 0,
      })),
      zero_result_queries: zeroResultQueries.map(row => ({
        query: row.query,
        count: Number(row.zero_count) || 0,
      })),
      total_searches: totalSearches,
      unique_queries: Number(summary?.unique_queries) || 0,
      zero_result_rate: totalSearches > 0 ? (totalZeroResults / totalSearches) * 100 : 0,
    });
  } catch (error) {
    console.error('Analytics search data error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch search data' },
      { status: 500 }
    );
  }
}
