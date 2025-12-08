/**
 * Admin Analytics Content API
 *
 * GET /api/admin/analytics/content?days=7
 *
 * Returns top viewed content and engagement data.
 * Requires admin authentication.
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryAll, queryOne } from '@/lib/db';
import { verifyAdminKey } from '@/lib/admin-auth';

export const runtime = 'nodejs';

interface TopAd {
  ad_id: string;
  external_id: string;
  brand_name: string;
  views: number;
}

interface TopBrand {
  brand: string;
  views: number;
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

    // Check if analytics tables exist
    const tableExists = await queryOne(
      `SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'analytics_events'
      ) as exists`
    );

    if (!tableExists?.exists) {
      return NextResponse.json({
        top_ads: [],
        top_brands: [],
        total_ad_views: 0,
        unique_ads_viewed: 0,
      });
    }

    // Top viewed ads (from raw events if rollups don't exist yet)
    const topAdsQuery = await queryAll(`
      SELECT
        props->>'ad_id' as ad_id,
        props->>'brand' as brand_name,
        COUNT(*) as views
      FROM analytics_events
      WHERE event = 'advert.view'
        AND event_date >= CURRENT_DATE - $1
        AND props->>'ad_id' IS NOT NULL
      GROUP BY props->>'ad_id', props->>'brand'
      ORDER BY views DESC
      LIMIT 10
    `, [days]);

    // Enrich with external_id from ads table
    const topAds: TopAd[] = [];
    for (const row of topAdsQuery) {
      const ad = await queryOne(
        `SELECT external_id, brand_name FROM ads WHERE id = $1`,
        [row.ad_id]
      );
      topAds.push({
        ad_id: row.ad_id,
        external_id: ad?.external_id || row.ad_id,
        brand_name: ad?.brand_name || row.brand_name || 'Unknown',
        views: Number(row.views) || 0,
      });
    }

    // Top brands by views
    const topBrands = await queryAll(`
      SELECT
        props->>'brand' as brand,
        COUNT(*) as views
      FROM analytics_events
      WHERE event = 'advert.view'
        AND event_date >= CURRENT_DATE - $1
        AND props->>'brand' IS NOT NULL
      GROUP BY props->>'brand'
      ORDER BY views DESC
      LIMIT 10
    `, [days]);

    // Summary
    const summary = await queryOne(`
      SELECT
        COUNT(*) as total_views,
        COUNT(DISTINCT props->>'ad_id') as unique_ads
      FROM analytics_events
      WHERE event = 'advert.view'
        AND event_date >= CURRENT_DATE - $1
    `, [days]);

    return NextResponse.json({
      top_ads: topAds,
      top_brands: topBrands.map(row => ({
        brand: row.brand || 'Unknown',
        views: Number(row.views) || 0,
      })) as TopBrand[],
      total_ad_views: Number(summary?.total_views) || 0,
      unique_ads_viewed: Number(summary?.unique_ads) || 0,
    });
  } catch (error) {
    console.error('Analytics content data error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch content data' },
      { status: 500 }
    );
  }
}
