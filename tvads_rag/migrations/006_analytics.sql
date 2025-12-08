-- Analytics Schema Migration
-- Internal decision dashboard with actionable metrics
-- GDPR-conscious: no raw IP storage, minimal PII

-- ============================================================================
-- Table: analytics_events (raw event log, pruned after rollup)
-- ============================================================================
CREATE TABLE IF NOT EXISTS analytics_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ts timestamptz NOT NULL DEFAULT now(),

    -- Event classification
    event text NOT NULL,  -- e.g., 'page.view', 'search.performed', 'advert.view'

    -- Context
    path text,            -- URL path (e.g., '/advert/coca-cola/christmas-2024')
    referrer text,        -- Referring URL (truncated to domain+path)

    -- Session tracking (anonymous, rotates daily)
    session_id text,      -- Random ID, client-generated, rotates daily

    -- Optional user link (for logged-in admin users only)
    user_id uuid,         -- NULL for anonymous visitors

    -- Event-specific properties
    props jsonb DEFAULT '{}'::jsonb,  -- { query, results_count, ad_id, brand, etc. }

    -- Privacy-safe device fingerprint (hashed UA + screen size bucket)
    ua_hash text,         -- SHA256(user_agent + screen_bucket), for unique visitor estimation

    -- Partition key for efficient pruning
    event_date date GENERATED ALWAYS AS (date(ts)) STORED
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_analytics_events_ts
    ON analytics_events (ts DESC);

CREATE INDEX IF NOT EXISTS idx_analytics_events_event_ts
    ON analytics_events (event, ts DESC);

CREATE INDEX IF NOT EXISTS idx_analytics_events_path_ts
    ON analytics_events (path, ts DESC)
    WHERE path IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_analytics_events_date
    ON analytics_events (event_date);

-- GIN index for JSONB property queries
CREATE INDEX IF NOT EXISTS idx_analytics_events_props
    ON analytics_events USING GIN (props);

-- ============================================================================
-- Table: analytics_daily_events (rollup by event type and path)
-- ============================================================================
CREATE TABLE IF NOT EXISTS analytics_daily_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    date date NOT NULL,

    -- Dimensions
    event text NOT NULL,
    path text,  -- NULL = all paths for this event

    -- Metrics
    count int NOT NULL DEFAULT 0,
    unique_sessions int NOT NULL DEFAULT 0,
    unique_visitors int NOT NULL DEFAULT 0,  -- Based on ua_hash

    -- Extra aggregates stored in JSONB for flexibility
    meta jsonb DEFAULT '{}'::jsonb,

    UNIQUE (date, event, path)
);

CREATE INDEX IF NOT EXISTS idx_analytics_daily_events_date
    ON analytics_daily_events (date DESC);

CREATE INDEX IF NOT EXISTS idx_analytics_daily_events_event_date
    ON analytics_daily_events (event, date DESC);

-- ============================================================================
-- Table: analytics_daily_search (search intelligence rollup)
-- ============================================================================
CREATE TABLE IF NOT EXISTS analytics_daily_search (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    date date NOT NULL,

    -- Dimensions
    query_normalized text NOT NULL,  -- Lowercased, trimmed search query

    -- Metrics
    search_count int NOT NULL DEFAULT 0,
    unique_sessions int NOT NULL DEFAULT 0,

    -- Result metrics
    avg_results_count numeric(10,2),
    zero_result_count int NOT NULL DEFAULT 0,

    -- Click-through (if we track search result clicks)
    click_count int NOT NULL DEFAULT 0,
    avg_click_position numeric(10,2),

    UNIQUE (date, query_normalized)
);

CREATE INDEX IF NOT EXISTS idx_analytics_daily_search_date
    ON analytics_daily_search (date DESC);

CREATE INDEX IF NOT EXISTS idx_analytics_daily_search_count
    ON analytics_daily_search (date DESC, search_count DESC);

-- ============================================================================
-- Table: analytics_daily_funnel (engagement funnel rollup)
-- ============================================================================
CREATE TABLE IF NOT EXISTS analytics_daily_funnel (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    date date NOT NULL UNIQUE,

    -- Funnel stages (count of unique sessions)
    visits int NOT NULL DEFAULT 0,           -- Any page.view
    searches int NOT NULL DEFAULT 0,         -- search.performed
    ad_views int NOT NULL DEFAULT 0,         -- advert.view
    engagements int NOT NULL DEFAULT 0,      -- advert.play, advert.like, advert.save
    deep_engagements int NOT NULL DEFAULT 0, -- advert.share, advert.full_watch

    -- Conversion rates (pre-computed for fast dashboard queries)
    search_rate numeric(5,4),      -- searches / visits
    view_rate numeric(5,4),        -- ad_views / visits
    engagement_rate numeric(5,4),  -- engagements / ad_views

    -- Source breakdown (top referrers)
    referrer_breakdown jsonb DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_analytics_daily_funnel_date
    ON analytics_daily_funnel (date DESC);

-- ============================================================================
-- Table: analytics_daily_content (content & SEO hygiene rollup)
-- ============================================================================
CREATE TABLE IF NOT EXISTS analytics_daily_content (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    date date NOT NULL UNIQUE,

    -- Content health
    total_ads int NOT NULL DEFAULT 0,
    published_ads int NOT NULL DEFAULT 0,
    draft_ads int NOT NULL DEFAULT 0,
    hidden_ads int NOT NULL DEFAULT 0,

    -- Engagement distribution
    ads_with_views int NOT NULL DEFAULT 0,
    ads_with_engagement int NOT NULL DEFAULT 0,

    -- Top content (arrays of ad_ids)
    top_viewed_ads jsonb DEFAULT '[]'::jsonb,      -- [{id, views, brand}]
    top_searched_brands jsonb DEFAULT '[]'::jsonb, -- [{brand, count}]

    -- SEO health
    pages_indexed int NOT NULL DEFAULT 0,
    pages_crawled int NOT NULL DEFAULT 0  -- If we track bot visits
);

CREATE INDEX IF NOT EXISTS idx_analytics_daily_content_date
    ON analytics_daily_content (date DESC);

-- ============================================================================
-- Table: analytics_pipeline_health (RAG pipeline metrics)
-- ============================================================================
CREATE TABLE IF NOT EXISTS analytics_pipeline_health (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    date date NOT NULL UNIQUE,

    -- Job queue metrics (from ingestion_jobs)
    jobs_completed int NOT NULL DEFAULT 0,
    jobs_failed int NOT NULL DEFAULT 0,
    jobs_pending int NOT NULL DEFAULT 0,

    -- Processing metrics
    avg_processing_time_seconds numeric(10,2),

    -- Error breakdown
    error_breakdown jsonb DEFAULT '{}'::jsonb,  -- { error_code: count }

    -- Quality metrics
    ads_missing_embeddings int NOT NULL DEFAULT 0,
    ads_missing_transcripts int NOT NULL DEFAULT 0,
    ads_with_warnings int NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_analytics_pipeline_health_date
    ON analytics_pipeline_health (date DESC);

-- ============================================================================
-- Function: rollup_daily_events (aggregate raw events into daily rollup)
-- Run daily via cron or on-demand
-- ============================================================================
CREATE OR REPLACE FUNCTION rollup_daily_events(p_date date DEFAULT CURRENT_DATE - 1)
RETURNS void AS $$
BEGIN
    -- Daily events rollup
    INSERT INTO analytics_daily_events (date, event, path, count, unique_sessions, unique_visitors)
    SELECT
        p_date,
        event,
        path,
        COUNT(*),
        COUNT(DISTINCT session_id),
        COUNT(DISTINCT ua_hash)
    FROM analytics_events
    WHERE event_date = p_date
    GROUP BY event, path
    ON CONFLICT (date, event, path)
    DO UPDATE SET
        count = EXCLUDED.count,
        unique_sessions = EXCLUDED.unique_sessions,
        unique_visitors = EXCLUDED.unique_visitors;

    -- Search intelligence rollup
    INSERT INTO analytics_daily_search (date, query_normalized, search_count, unique_sessions, avg_results_count, zero_result_count, click_count)
    SELECT
        p_date,
        LOWER(TRIM(props->>'query')) as query_normalized,
        COUNT(*),
        COUNT(DISTINCT session_id),
        AVG((props->>'results_count')::numeric),
        COUNT(*) FILTER (WHERE (props->>'results_count')::int = 0),
        COUNT(*) FILTER (WHERE props->>'clicked_ad_id' IS NOT NULL)
    FROM analytics_events
    WHERE event_date = p_date
      AND event = 'search.performed'
      AND props->>'query' IS NOT NULL
    GROUP BY LOWER(TRIM(props->>'query'))
    ON CONFLICT (date, query_normalized)
    DO UPDATE SET
        search_count = EXCLUDED.search_count,
        unique_sessions = EXCLUDED.unique_sessions,
        avg_results_count = EXCLUDED.avg_results_count,
        zero_result_count = EXCLUDED.zero_result_count,
        click_count = EXCLUDED.click_count;

    -- Funnel rollup
    INSERT INTO analytics_daily_funnel (date, visits, searches, ad_views, engagements, deep_engagements)
    SELECT
        p_date,
        COUNT(DISTINCT session_id) FILTER (WHERE event = 'page.view'),
        COUNT(DISTINCT session_id) FILTER (WHERE event = 'search.performed'),
        COUNT(DISTINCT session_id) FILTER (WHERE event = 'advert.view'),
        COUNT(DISTINCT session_id) FILTER (WHERE event IN ('advert.play', 'advert.like', 'advert.save')),
        COUNT(DISTINCT session_id) FILTER (WHERE event IN ('advert.share', 'advert.full_watch'))
    FROM analytics_events
    WHERE event_date = p_date
    ON CONFLICT (date)
    DO UPDATE SET
        visits = EXCLUDED.visits,
        searches = EXCLUDED.searches,
        ad_views = EXCLUDED.ad_views,
        engagements = EXCLUDED.engagements,
        deep_engagements = EXCLUDED.deep_engagements;

    -- Update funnel conversion rates
    UPDATE analytics_daily_funnel
    SET
        search_rate = CASE WHEN visits > 0 THEN searches::numeric / visits ELSE 0 END,
        view_rate = CASE WHEN visits > 0 THEN ad_views::numeric / visits ELSE 0 END,
        engagement_rate = CASE WHEN ad_views > 0 THEN engagements::numeric / ad_views ELSE 0 END
    WHERE date = p_date;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Function: prune_old_events (delete raw events after N days, keep rollups)
-- Run weekly via cron
-- ============================================================================
CREATE OR REPLACE FUNCTION prune_old_events(p_days_to_keep int DEFAULT 30)
RETURNS int AS $$
DECLARE
    v_deleted int;
BEGIN
    DELETE FROM analytics_events
    WHERE event_date < CURRENT_DATE - p_days_to_keep;

    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- View: analytics_overview (quick dashboard stats)
-- ============================================================================
CREATE OR REPLACE VIEW analytics_overview AS
SELECT
    -- Today's snapshot
    (SELECT COUNT(*) FROM analytics_events WHERE event_date = CURRENT_DATE) as events_today,
    (SELECT COUNT(DISTINCT session_id) FROM analytics_events WHERE event_date = CURRENT_DATE) as sessions_today,

    -- This week's aggregates
    (SELECT COALESCE(SUM(count), 0) FROM analytics_daily_events
     WHERE date >= CURRENT_DATE - 7 AND event = 'page.view') as pageviews_7d,
    (SELECT COALESCE(SUM(unique_sessions), 0) FROM analytics_daily_events
     WHERE date >= CURRENT_DATE - 7 AND event = 'page.view') as sessions_7d,
    (SELECT COALESCE(SUM(search_count), 0) FROM analytics_daily_search
     WHERE date >= CURRENT_DATE - 7) as searches_7d,

    -- Funnel averages (last 7 days)
    (SELECT AVG(search_rate) FROM analytics_daily_funnel
     WHERE date >= CURRENT_DATE - 7) as avg_search_rate_7d,
    (SELECT AVG(engagement_rate) FROM analytics_daily_funnel
     WHERE date >= CURRENT_DATE - 7) as avg_engagement_rate_7d;

-- ============================================================================
-- Comments
-- ============================================================================
COMMENT ON TABLE analytics_events IS
'Raw event log for TellyAds analytics. Pruned after 30 days; rollups preserved indefinitely.';

COMMENT ON TABLE analytics_daily_events IS
'Daily rollup of events by type and path. Primary source for admin dashboard charts.';

COMMENT ON TABLE analytics_daily_search IS
'Daily rollup of search queries for search intelligence dashboard.';

COMMENT ON TABLE analytics_daily_funnel IS
'Daily rollup of engagement funnel metrics. Pre-computed conversion rates for fast queries.';

COMMENT ON FUNCTION rollup_daily_events IS
'Aggregate raw events into daily rollups. Run daily at midnight UTC via cron.';

COMMENT ON FUNCTION prune_old_events IS
'Delete raw events older than N days. Rollups are preserved. Run weekly.';
