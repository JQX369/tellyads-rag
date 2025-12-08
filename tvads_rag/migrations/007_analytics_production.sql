-- Analytics Production Hardening Migration
-- UTC timezone consistency, performance indexes, content requests, SEO tracking

-- ============================================================================
-- UTC Timezone Fix: Update rollup functions to use UTC explicitly
-- ============================================================================

-- Drop and recreate rollup function with UTC consistency
CREATE OR REPLACE FUNCTION rollup_daily_events(p_date date DEFAULT (NOW() AT TIME ZONE 'UTC')::date - 1)
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
        COUNT(DISTINCT session_id) FILTER (WHERE event IN ('advert.share', 'advert.complete'))
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

-- Update prune function to use 90-day retention (production default)
CREATE OR REPLACE FUNCTION prune_old_events(p_days_to_keep int DEFAULT 90)
RETURNS int AS $$
DECLARE
    v_deleted int;
BEGIN
    DELETE FROM analytics_events
    WHERE event_date < (NOW() AT TIME ZONE 'UTC')::date - p_days_to_keep;

    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Additional Performance Indexes
-- ============================================================================

-- Composite index for rollup queries (event_date + event)
CREATE INDEX IF NOT EXISTS idx_analytics_events_date_event
    ON analytics_events (event_date, event);

-- Index for session lookups
CREATE INDEX IF NOT EXISTS idx_analytics_events_session
    ON analytics_events (session_id, event_date DESC)
    WHERE session_id IS NOT NULL;

-- Index for ua_hash (unique visitor estimation)
CREATE INDEX IF NOT EXISTS idx_analytics_events_ua_hash
    ON analytics_events (ua_hash, event_date DESC)
    WHERE ua_hash IS NOT NULL;

-- ============================================================================
-- Table: content_requests (Content Gap Action Loop)
-- ============================================================================
CREATE TABLE IF NOT EXISTS content_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    -- Source query that triggered the request
    query text NOT NULL,
    source text NOT NULL DEFAULT 'zero_result_search',  -- zero_result_search, manual, admin

    -- Status workflow: new -> queued -> in_progress -> done -> rejected
    status text NOT NULL DEFAULT 'new'
        CHECK (status IN ('new', 'queued', 'in_progress', 'done', 'rejected')),

    -- Admin notes
    notes text,

    -- Resolution
    resolved_at timestamptz,
    resolved_by text,  -- Admin identifier
    result_ad_id uuid REFERENCES ads(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_content_requests_status
    ON content_requests (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_content_requests_query
    ON content_requests (query);

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_content_requests_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_content_requests_updated_at ON content_requests;
CREATE TRIGGER trigger_content_requests_updated_at
    BEFORE UPDATE ON content_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_content_requests_updated_at();

-- ============================================================================
-- Table: analytics_seo_events (SEO hygiene tracking)
-- ============================================================================
CREATE TABLE IF NOT EXISTS analytics_seo_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ts timestamptz NOT NULL DEFAULT now(),
    event_date date GENERATED ALWAYS AS (date(ts AT TIME ZONE 'UTC')) STORED,

    -- Event type
    event_type text NOT NULL,  -- '404', 'legacy_redirect', 'bot_crawl'

    -- URL info
    path text NOT NULL,
    redirect_to text,  -- For legacy redirects

    -- Source
    referrer text,
    user_agent_category text,  -- 'bot', 'browser', 'unknown'

    -- Session (if available)
    session_id text
);

CREATE INDEX IF NOT EXISTS idx_analytics_seo_events_date_type
    ON analytics_seo_events (event_date, event_type);

CREATE INDEX IF NOT EXISTS idx_analytics_seo_events_path
    ON analytics_seo_events (path, event_date DESC);

-- ============================================================================
-- View: analytics_seo_summary (for admin dashboard)
-- ============================================================================
CREATE OR REPLACE VIEW analytics_seo_summary AS
SELECT
    event_date,
    event_type,
    COUNT(*) as count,
    COUNT(DISTINCT path) as unique_paths,
    jsonb_agg(DISTINCT path) FILTER (WHERE path IS NOT NULL) as paths
FROM analytics_seo_events
WHERE event_date >= (NOW() AT TIME ZONE 'UTC')::date - 7
GROUP BY event_date, event_type
ORDER BY event_date DESC, count DESC;

-- ============================================================================
-- View: top_404_paths (for admin dashboard)
-- ============================================================================
CREATE OR REPLACE VIEW top_404_paths AS
SELECT
    path,
    COUNT(*) as count,
    MAX(ts) as last_seen,
    array_agg(DISTINCT referrer) FILTER (WHERE referrer IS NOT NULL AND referrer != '') as referrers
FROM analytics_seo_events
WHERE event_type = '404'
  AND event_date >= (NOW() AT TIME ZONE 'UTC')::date - 7
GROUP BY path
ORDER BY count DESC
LIMIT 50;

-- ============================================================================
-- View: legacy_redirect_hits (for admin dashboard)
-- ============================================================================
CREATE OR REPLACE VIEW legacy_redirect_hits AS
SELECT
    path,
    redirect_to,
    COUNT(*) as count,
    MAX(ts) as last_seen
FROM analytics_seo_events
WHERE event_type = 'legacy_redirect'
  AND event_date >= (NOW() AT TIME ZONE 'UTC')::date - 7
GROUP BY path, redirect_to
ORDER BY count DESC
LIMIT 50;

-- ============================================================================
-- Function: run_all_rollups (convenience wrapper for cron)
-- ============================================================================
CREATE OR REPLACE FUNCTION run_all_rollups(p_date date DEFAULT (NOW() AT TIME ZONE 'UTC')::date - 1)
RETURNS TABLE (
    rollup_name text,
    status text
) AS $$
BEGIN
    -- Run daily events rollup
    BEGIN
        PERFORM rollup_daily_events(p_date);
        rollup_name := 'rollup_daily_events';
        status := 'success';
        RETURN NEXT;
    EXCEPTION WHEN OTHERS THEN
        rollup_name := 'rollup_daily_events';
        status := 'error: ' || SQLERRM;
        RETURN NEXT;
    END;

    RETURN;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Comments
-- ============================================================================
COMMENT ON TABLE content_requests IS
'Content gap action queue. Created from zero-result searches for admin triage.';

COMMENT ON TABLE analytics_seo_events IS
'SEO hygiene events: 404s, legacy redirects, bot crawls. Separate from main analytics for focused queries.';

COMMENT ON FUNCTION run_all_rollups IS
'Convenience function to run all daily rollups. Call from cron: SELECT * FROM run_all_rollups();';
