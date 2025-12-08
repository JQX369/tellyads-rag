# TellyAds Analytics System

Internal decision dashboard with actionable metrics for the TellyAds admin.

## Overview

The analytics system provides:
- **Event Tracking**: Client-side tracking of user interactions
- **Rollup Tables**: Pre-aggregated daily metrics for fast dashboard queries
- **Admin Dashboard**: Visual metrics UI at `/admin/analytics`
- **GDPR Compliance**: No raw IP storage, minimal PII, session rotation

## Architecture

```
[Browser] ---> [/api/analytics/capture] ---> [analytics_events table]
                                                    |
                                              [Daily Rollup Job]
                                                    |
                                        [analytics_daily_* tables]
                                                    |
                                           [Admin Dashboard]
```

## Event Taxonomy

Events follow the `{domain}.{action}` naming convention:

### Page Events
- `page.view` - Page loaded
- `page.scroll_depth` - User scrolled to 25/50/75/100%
- `page.exit` - User left page

### Search Events
- `search.performed` - User searched (`{ query, results_count, latency_ms }`)
- `search.result_click` - Clicked a search result (`{ query, ad_id, position }`)
- `search.zero_results` - Search returned no results
- `search.filter_applied` - Filter applied

### Advert Events
- `advert.view` - Ad page viewed (`{ ad_id, brand, source }`)
- `advert.play` - Video play started
- `advert.complete` - Video watched to completion
- `advert.like` / `advert.save` - Engagement actions
- `advert.share` - Ad shared

### Browse Events
- `browse.era_click` - Clicked decade filter
- `browse.brand_click` - Clicked brand
- `browse.random_click` - Used random ad feature

## Database Schema

### Raw Events Table
```sql
analytics_events (
  id uuid PRIMARY KEY,
  ts timestamptz,
  event text,
  path text,
  referrer text,
  session_id text,
  props jsonb,
  ua_hash text,
  event_date date GENERATED
)
```

### Rollup Tables
- `analytics_daily_events` - Daily event counts by type/path
- `analytics_daily_search` - Search query aggregates
- `analytics_daily_funnel` - Conversion funnel metrics
- `analytics_daily_content` - Content engagement rollup
- `analytics_pipeline_health` - Ingestion pipeline metrics

## Setup

### 1. Run Migration
```bash
psql "$SUPABASE_DB_URL" -f tvads_rag/migrations/006_analytics.sql
```

### 2. Initialize Tracking
Add to your layout or app provider:

```tsx
import { initAnalytics } from '@/lib/analytics';

useEffect(() => {
  return initAnalytics();
}, []);
```

### 3. Track Custom Events
```tsx
import { track, trackSearch, trackAdView } from '@/lib/analytics';

// Track search
trackSearch(query, results.length, latencyMs);

// Track ad view
trackAdView(adId, brandName, 'search');

// Custom event
track('browse.era_click', { decade: '1990s' });
```

## Daily Rollup

Run the rollup function daily (e.g., via cron):

```sql
SELECT rollup_daily_events(CURRENT_DATE - 1);
```

## Event Pruning

Raw events are pruned after 30 days. Rollups are preserved indefinitely:

```sql
SELECT prune_old_events(30);  -- Keep 30 days of raw events
```

## Admin Dashboard

Access at `/admin/analytics` (requires admin auth).

### Tabs
1. **Overview** - High-level metrics, trends, funnel rates
2. **Search** - Top queries, zero-result queries, search volume
3. **Content** - Top viewed ads, popular brands
4. **Pipeline** - Job queue status, data quality metrics

## API Endpoints

All require `x-admin-key` header.

| Endpoint | Description |
|----------|-------------|
| `GET /api/admin/analytics/overview` | Summary metrics |
| `GET /api/admin/analytics/daily?days=30` | Time series data |
| `GET /api/admin/analytics/search?days=7` | Search intelligence |
| `GET /api/admin/analytics/content?days=7` | Content engagement |
| `GET /api/admin/analytics/pipeline` | Pipeline health |

## Privacy

- **No raw IP storage**: IPs are not captured
- **UA hashing**: User agent is hashed for unique visitor estimation
- **Session rotation**: Sessions rotate daily
- **Minimal PII**: Only essential data captured
- **Query truncation**: Long queries are truncated to 200 chars
- **Props sanitization**: Sensitive keys filtered automatically

## Files

| File | Purpose |
|------|---------|
| `tvads_rag/migrations/006_analytics.sql` | Database schema |
| `frontend/lib/analytics.ts` | Client tracking helper |
| `frontend/app/api/analytics/capture/route.ts` | Capture endpoint |
| `frontend/app/api/admin/analytics/*/route.ts` | Admin API endpoints |
| `frontend/app/admin/analytics/page.tsx` | Admin dashboard UI |
