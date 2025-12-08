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

### 1. Run Migrations
```bash
# Initial schema
psql "$SUPABASE_DB_URL" -f tvads_rag/migrations/006_analytics.sql

# Production hardening (UTC fixes, indexes, SEO tracking, content requests)
psql "$SUPABASE_DB_URL" -f tvads_rag/migrations/007_analytics_production.sql
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

### Vercel Cron (Recommended)

Rollups are automatically scheduled via `vercel.json`:
```json
{
  "crons": [
    {
      "path": "/api/admin/analytics/rollup",
      "schedule": "0 3 * * *"
    }
  ]
}
```

### Manual Execution

Run rollups manually:
```bash
# Via API (requires ADMIN_API_KEY or Vercel cron headers)
curl -X POST https://tellyads.com/api/admin/analytics/rollup \
  -H "x-admin-key: $ADMIN_API_KEY"

# Via SQL
psql "$SUPABASE_DB_URL" -c "SELECT run_all_rollups();"
```

### Rollup Status Check
```bash
curl https://tellyads.com/api/admin/analytics/rollup \
  -H "x-admin-key: $ADMIN_API_KEY"
```

## Event Pruning

Raw events are pruned after **90 days**. Rollups are preserved indefinitely:

```sql
SELECT prune_old_events(90);  -- Keep 90 days of raw events
```

Pruning runs automatically on Sundays via the rollup cron job.

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
| `GET /api/admin/analytics/overview` | Summary metrics + capture health |
| `GET /api/admin/analytics/daily?days=30` | Time series data |
| `GET /api/admin/analytics/search?days=7` | Search intelligence |
| `GET /api/admin/analytics/content?days=7` | Content engagement |
| `GET /api/admin/analytics/pipeline` | Pipeline health |
| `GET /api/admin/analytics/seo?days=7` | SEO hygiene (404s, redirects) |
| `GET /api/admin/analytics/content-requests` | Content gap requests |
| `POST /api/admin/analytics/content-requests` | Create/update content request |
| `GET /api/admin/analytics/rollup` | Rollup status |
| `POST /api/admin/analytics/rollup` | Trigger rollup (Vercel cron) |

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
| `tvads_rag/migrations/006_analytics.sql` | Initial database schema |
| `tvads_rag/migrations/007_analytics_production.sql` | Production hardening |
| `frontend/lib/analytics.ts` | Client tracking helper |
| `frontend/lib/analytics-metrics.ts` | Capture observability metrics |
| `frontend/app/api/analytics/capture/route.ts` | Capture endpoint |
| `frontend/app/api/admin/analytics/*/route.ts` | Admin API endpoints |
| `frontend/app/admin/analytics/page.tsx` | Admin dashboard UI |
| `frontend/tests/analytics/*.test.ts` | Automated test suite |
| `frontend/tests/analytics/helpers/` | Test utilities and seed data |
| `scripts/analytics/truth_test.py` | Live environment verification |

## Security

The capture endpoint includes several production hardening measures:

- **Origin validation**: Only accepts requests from allowed origins
- **Dual rate limiting**: Session-based (100/min) + UA-hash fallback (500/min)
- **Props sanitization**: Sensitive keys automatically filtered
- **Silent failures**: Errors don't expose internal state

## Testing

### Running Analytics Tests Locally

The analytics system includes automated tests for CI and local development:

```bash
cd frontend

# Run all tests (unit + analytics)
npm test

# Run only analytics tests
npm run test:analytics

# Run only unit tests
npm run test:unit

# Watch mode for development
npm run test:watch
```

### Test Coverage

The analytics test suite (`frontend/tests/analytics/`) covers:

1. **Capture Endpoint** (`capture.test.ts`)
   - Valid event acceptance (204 response)
   - Invalid event rejection (400 response)
   - Payload validation and sanitization
   - Props filtering (sensitive keys removed)

2. **Security** (`security.test.ts`)
   - Origin validation
   - Rate limiting (session and ua_hash)
   - Admin auth requirements

3. **Admin API Schemas** (`admin-apis.test.ts`)
   - Overview endpoint returns correct shape
   - Search endpoint returns arrays
   - SEO endpoint returns 404 and redirect data
   - Content requests endpoint returns correct shape

4. **Rollup Endpoint** (`rollup.test.ts`)
   - Security (requires auth or cron secret)
   - Status reporting
   - Rollup execution

### Seeded Test Data

The test suite includes a seed helper (`tests/analytics/helpers/seed.ts`) that generates:
- 5 page.view events
- 3 search.performed events (1 zero-results)
- 1 search.zero_results event
- 2 search.result_click events
- 5 advert.view events
- 2 advert.share events

Use this for validating rollup correctness.

### CI Integration

Analytics tests run automatically on PRs via GitHub Actions (`.github/workflows/ci.yml`).
Tests are fast (<30s) and don't require a database connection (mocked).

## Truth Test

Verify analytics correctness against a live environment:

```bash
# Local testing
python scripts/analytics/truth_test.py --base-url http://localhost:3000

# Production testing (requires DB access or admin key)
python scripts/analytics/truth_test.py \
  --base-url https://tellyads.com \
  --admin-key $ADMIN_API_KEY
```

## Production Readiness Checklist

### Pre-Deployment

| Check | Status | Notes |
|-------|--------|-------|
| Run 006_analytics.sql migration | | Initial schema |
| Run 007_analytics_production.sql migration | | UTC fixes, indexes, SEO |
| Verify `runtime = 'nodejs'` on all endpoints | PASS | Required for Postgres |
| Set `ADMIN_API_KEY` environment variable | | Required for admin APIs |
| Set `VERCEL_CRON_SECRET` (optional) | | Extra cron security |

### Post-Deployment

| Check | Status | Notes |
|-------|--------|-------|
| Verify `/api/analytics/capture` returns 204 | | Capture working |
| Verify `/api/admin/analytics/overview` returns data | | Admin API working |
| Run truth test | | Event correctness |
| Check rollup job status | | Cron configured |
| Verify no errors in capture metrics | | `capture_error_count = 0` |

### Verification Commands

```bash
# Check capture endpoint
curl -X POST https://tellyads.com/api/analytics/capture \
  -H "Content-Type: application/json" \
  -H "Origin: https://tellyads.com" \
  -d '{"event":"page.view","path":"/test"}'
# Expected: 204 No Content

# Check admin overview
curl https://tellyads.com/api/admin/analytics/overview \
  -H "x-admin-key: $ADMIN_API_KEY"
# Expected: JSON with capture_error_count, capture_events_24h

# Check rollup status
curl https://tellyads.com/api/admin/analytics/rollup \
  -H "x-admin-key: $ADMIN_API_KEY"
# Expected: JSON with last_rollup_date

# Run truth test
python scripts/analytics/truth_test.py --base-url https://tellyads.com
```

### Monitoring

Key metrics to watch in the admin dashboard:

- **capture_error_rate_pct**: Should be < 1%
- **capture_events_24h**: Should increase with traffic
- **last_rollup_date**: Should be yesterday or today (3 AM UTC)

### Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| 401 on admin APIs | Missing/invalid admin key | Check `ADMIN_API_KEY` env var |
| Events not appearing | Capture errors | Check `capture_error_count` in overview |
| Rollups not running | Cron misconfigured | Check Vercel cron logs |
| Zero metrics | Tables don't exist | Run migrations |
| Origin rejection | Cross-site request | Update `ALLOWED_ORIGINS` in capture route |
