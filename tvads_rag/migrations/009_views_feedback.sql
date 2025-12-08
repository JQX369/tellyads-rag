-- Views and Feedback Tracking Migration
-- Enhanced view tracking with deduplication, ratings, and weighted scoring
--
-- Tables:
--   - ad_view_events: Deduplicated view tracking per ad/session
--   - ad_ratings: Star ratings and written reviews
--   - feedback_weight_configs: Admin-configurable scoring weights
--   - ad_feedback_agg: Pre-computed aggregate feedback metrics
--
-- Views:
--   - ad_feedback_summary: Comprehensive feedback stats per ad
--   - feedback_leaderboard: Top-rated ads with composite scores

-- ============================================================================
-- Table: ad_view_events (deduplicated view tracking)
-- ============================================================================
CREATE TABLE IF NOT EXISTS ad_view_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id uuid NOT NULL REFERENCES ads(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),

    -- Session tracking for deduplication
    session_id text NOT NULL,

    -- Fingerprint for unique visitor estimation (hashed)
    visitor_hash text,

    -- Context
    referrer text,
    source text,  -- 'search', 'direct', 'similar', 'brand_page', etc.

    -- Watch duration (if available)
    watch_duration_seconds int,
    completed boolean DEFAULT false,  -- Watched to completion

    -- Derived date for efficient partitioning
    view_date date GENERATED ALWAYS AS (date(created_at AT TIME ZONE 'UTC')) STORED
);

-- Unique constraint for deduplication: one view per session per ad per day
CREATE UNIQUE INDEX IF NOT EXISTS idx_ad_view_events_dedup
    ON ad_view_events (ad_id, session_id, view_date);

CREATE INDEX IF NOT EXISTS idx_ad_view_events_ad_date
    ON ad_view_events (ad_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ad_view_events_date
    ON ad_view_events (view_date DESC);

CREATE INDEX IF NOT EXISTS idx_ad_view_events_visitor
    ON ad_view_events (visitor_hash, view_date DESC)
    WHERE visitor_hash IS NOT NULL;

-- ============================================================================
-- Table: ad_ratings (star ratings and reviews)
-- ============================================================================
CREATE TABLE IF NOT EXISTS ad_ratings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id uuid NOT NULL REFERENCES ads(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    -- Rater identity (anonymous by session or user_id)
    session_id text,
    user_id uuid,  -- NULL for anonymous

    -- Rating data
    rating smallint NOT NULL CHECK (rating >= 1 AND rating <= 5),

    -- Optional written review
    review_text text,

    -- Review moderation status
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'flagged')),

    -- Metadata
    helpful_count int NOT NULL DEFAULT 0,
    reported_count int NOT NULL DEFAULT 0,

    -- One rating per session or user per ad
    UNIQUE NULLS NOT DISTINCT (ad_id, session_id),
    UNIQUE NULLS NOT DISTINCT (ad_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_ad_ratings_ad_status
    ON ad_ratings (ad_id, status);

CREATE INDEX IF NOT EXISTS idx_ad_ratings_created
    ON ad_ratings (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ad_ratings_pending
    ON ad_ratings (status, created_at DESC)
    WHERE status = 'pending';

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_ad_ratings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_ad_ratings_updated_at ON ad_ratings;
CREATE TRIGGER trigger_ad_ratings_updated_at
    BEFORE UPDATE ON ad_ratings
    FOR EACH ROW
    EXECUTE FUNCTION update_ad_ratings_updated_at();

-- ============================================================================
-- Table: feedback_weight_configs (admin-configurable weights)
-- ============================================================================
CREATE TABLE IF NOT EXISTS feedback_weight_configs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    -- Config identifier (use 'default' for global config)
    config_key text NOT NULL UNIQUE DEFAULT 'default',

    -- Display name
    name text NOT NULL DEFAULT 'Default Weights',
    description text,

    -- Is this config active?
    is_active boolean NOT NULL DEFAULT true,

    -- Weights (0.0 to 10.0 scale, normalized when computing)
    weight_views numeric(4,2) NOT NULL DEFAULT 1.0,
    weight_unique_views numeric(4,2) NOT NULL DEFAULT 1.5,
    weight_completions numeric(4,2) NOT NULL DEFAULT 2.0,
    weight_likes numeric(4,2) NOT NULL DEFAULT 3.0,
    weight_saves numeric(4,2) NOT NULL DEFAULT 4.0,
    weight_shares numeric(4,2) NOT NULL DEFAULT 5.0,
    weight_rating numeric(4,2) NOT NULL DEFAULT 4.0,
    weight_review numeric(4,2) NOT NULL DEFAULT 3.0,

    -- Time decay settings
    decay_half_life_days int NOT NULL DEFAULT 30,  -- Score halves every N days
    recency_boost_days int NOT NULL DEFAULT 7,    -- Boost for content in last N days
    recency_boost_multiplier numeric(3,2) NOT NULL DEFAULT 1.5,

    -- Constraints
    CHECK (weight_views >= 0 AND weight_views <= 10),
    CHECK (weight_unique_views >= 0 AND weight_unique_views <= 10),
    CHECK (weight_completions >= 0 AND weight_completions <= 10),
    CHECK (weight_likes >= 0 AND weight_likes <= 10),
    CHECK (weight_saves >= 0 AND weight_saves <= 10),
    CHECK (weight_shares >= 0 AND weight_shares <= 10),
    CHECK (weight_rating >= 0 AND weight_rating <= 10),
    CHECK (weight_review >= 0 AND weight_review <= 10),
    CHECK (decay_half_life_days > 0),
    CHECK (recency_boost_days >= 0),
    CHECK (recency_boost_multiplier >= 1)
);

-- Insert default config
INSERT INTO feedback_weight_configs (config_key, name, description)
VALUES ('default', 'Default Weights', 'Default scoring weights for ad ranking')
ON CONFLICT (config_key) DO NOTHING;

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_feedback_weight_configs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_feedback_weight_configs_updated_at ON feedback_weight_configs;
CREATE TRIGGER trigger_feedback_weight_configs_updated_at
    BEFORE UPDATE ON feedback_weight_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_feedback_weight_configs_updated_at();

-- ============================================================================
-- Table: ad_feedback_agg (pre-computed aggregate metrics)
-- ============================================================================
CREATE TABLE IF NOT EXISTS ad_feedback_agg (
    ad_id uuid PRIMARY KEY REFERENCES ads(id) ON DELETE CASCADE,
    updated_at timestamptz NOT NULL DEFAULT now(),

    -- View metrics
    total_views int NOT NULL DEFAULT 0,
    unique_views int NOT NULL DEFAULT 0,
    views_7d int NOT NULL DEFAULT 0,
    views_30d int NOT NULL DEFAULT 0,

    -- Completion metrics
    total_completions int NOT NULL DEFAULT 0,
    completion_rate numeric(5,4),  -- 0.0 to 1.0
    avg_watch_seconds numeric(10,2),

    -- Engagement metrics (from existing likes/saves)
    total_likes int NOT NULL DEFAULT 0,
    total_saves int NOT NULL DEFAULT 0,
    total_shares int NOT NULL DEFAULT 0,

    -- Rating metrics
    rating_count int NOT NULL DEFAULT 0,
    rating_sum int NOT NULL DEFAULT 0,
    rating_avg numeric(3,2),  -- 1.00 to 5.00
    review_count int NOT NULL DEFAULT 0,

    -- Computed scores (using active weight config)
    raw_score numeric(12,4) NOT NULL DEFAULT 0,
    weighted_score numeric(12,4) NOT NULL DEFAULT 0,
    time_decayed_score numeric(12,4) NOT NULL DEFAULT 0,

    -- Ranking (updated periodically)
    rank_by_score int,
    rank_by_views int,
    rank_by_rating int,

    -- Percentiles
    score_percentile numeric(5,2),  -- 0-100

    -- First and last engagement timestamps
    first_view_at timestamptz,
    last_view_at timestamptz,
    last_engagement_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_ad_feedback_agg_score
    ON ad_feedback_agg (weighted_score DESC);

CREATE INDEX IF NOT EXISTS idx_ad_feedback_agg_views
    ON ad_feedback_agg (total_views DESC);

CREATE INDEX IF NOT EXISTS idx_ad_feedback_agg_rating
    ON ad_feedback_agg (rating_avg DESC NULLS LAST)
    WHERE rating_count >= 3;  -- Only rank ads with minimum ratings

-- ============================================================================
-- Function: record_ad_view (upsert view with deduplication)
-- ============================================================================
CREATE OR REPLACE FUNCTION record_ad_view(
    p_ad_id uuid,
    p_session_id text,
    p_visitor_hash text DEFAULT NULL,
    p_referrer text DEFAULT NULL,
    p_source text DEFAULT NULL,
    p_watch_duration int DEFAULT NULL,
    p_completed boolean DEFAULT false
) RETURNS uuid AS $$
DECLARE
    v_view_id uuid;
BEGIN
    -- Upsert view event (deduplicated by ad/session/date)
    INSERT INTO ad_view_events (
        ad_id, session_id, visitor_hash, referrer, source,
        watch_duration_seconds, completed
    ) VALUES (
        p_ad_id, p_session_id, p_visitor_hash, p_referrer, p_source,
        p_watch_duration, p_completed
    )
    ON CONFLICT (ad_id, session_id, view_date) DO UPDATE SET
        watch_duration_seconds = GREATEST(
            COALESCE(ad_view_events.watch_duration_seconds, 0),
            COALESCE(EXCLUDED.watch_duration_seconds, 0)
        ),
        completed = ad_view_events.completed OR EXCLUDED.completed
    RETURNING id INTO v_view_id;

    -- Update aggregate (lightweight increment)
    INSERT INTO ad_feedback_agg (ad_id, total_views, unique_views, first_view_at, last_view_at)
    VALUES (p_ad_id, 1, 1, now(), now())
    ON CONFLICT (ad_id) DO UPDATE SET
        total_views = ad_feedback_agg.total_views + 1,
        last_view_at = now(),
        updated_at = now();

    -- Note: unique_views, views_7d, views_30d are recomputed by refresh_ad_feedback_agg()

    RETURN v_view_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Function: record_ad_rating (upsert rating)
-- ============================================================================
CREATE OR REPLACE FUNCTION record_ad_rating(
    p_ad_id uuid,
    p_session_id text,
    p_user_id uuid DEFAULT NULL,
    p_rating smallint DEFAULT NULL,
    p_review_text text DEFAULT NULL
) RETURNS uuid AS $$
DECLARE
    v_rating_id uuid;
    v_old_rating smallint;
BEGIN
    -- Get existing rating if any (for delta calculation)
    IF p_user_id IS NOT NULL THEN
        SELECT rating INTO v_old_rating FROM ad_ratings
        WHERE ad_id = p_ad_id AND user_id = p_user_id;
    ELSE
        SELECT rating INTO v_old_rating FROM ad_ratings
        WHERE ad_id = p_ad_id AND session_id = p_session_id;
    END IF;

    -- Upsert rating
    IF p_user_id IS NOT NULL THEN
        INSERT INTO ad_ratings (ad_id, session_id, user_id, rating, review_text)
        VALUES (p_ad_id, p_session_id, p_user_id, p_rating, p_review_text)
        ON CONFLICT (ad_id, user_id) DO UPDATE SET
            rating = COALESCE(EXCLUDED.rating, ad_ratings.rating),
            review_text = COALESCE(EXCLUDED.review_text, ad_ratings.review_text),
            status = CASE
                WHEN EXCLUDED.review_text IS NOT NULL AND EXCLUDED.review_text != ad_ratings.review_text
                THEN 'pending'
                ELSE ad_ratings.status
            END
        RETURNING id INTO v_rating_id;
    ELSE
        INSERT INTO ad_ratings (ad_id, session_id, rating, review_text)
        VALUES (p_ad_id, p_session_id, p_rating, p_review_text)
        ON CONFLICT (ad_id, session_id) DO UPDATE SET
            rating = COALESCE(EXCLUDED.rating, ad_ratings.rating),
            review_text = COALESCE(EXCLUDED.review_text, ad_ratings.review_text),
            status = CASE
                WHEN EXCLUDED.review_text IS NOT NULL AND EXCLUDED.review_text != ad_ratings.review_text
                THEN 'pending'
                ELSE ad_ratings.status
            END
        RETURNING id INTO v_rating_id;
    END IF;

    -- Update aggregate with delta
    IF v_old_rating IS NULL THEN
        -- New rating
        INSERT INTO ad_feedback_agg (ad_id, rating_count, rating_sum, review_count)
        VALUES (
            p_ad_id,
            1,
            p_rating,
            CASE WHEN p_review_text IS NOT NULL THEN 1 ELSE 0 END
        )
        ON CONFLICT (ad_id) DO UPDATE SET
            rating_count = ad_feedback_agg.rating_count + 1,
            rating_sum = ad_feedback_agg.rating_sum + p_rating,
            rating_avg = (ad_feedback_agg.rating_sum + p_rating)::numeric / (ad_feedback_agg.rating_count + 1),
            review_count = ad_feedback_agg.review_count + CASE WHEN p_review_text IS NOT NULL THEN 1 ELSE 0 END,
            updated_at = now();
    ELSE
        -- Updated rating (adjust delta)
        UPDATE ad_feedback_agg SET
            rating_sum = rating_sum - v_old_rating + p_rating,
            rating_avg = (rating_sum - v_old_rating + p_rating)::numeric / rating_count,
            updated_at = now()
        WHERE ad_id = p_ad_id;
    END IF;

    RETURN v_rating_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Function: refresh_ad_feedback_agg (full recompute for an ad or all ads)
-- ============================================================================
CREATE OR REPLACE FUNCTION refresh_ad_feedback_agg(p_ad_id uuid DEFAULT NULL)
RETURNS int AS $$
DECLARE
    v_updated int;
    v_config feedback_weight_configs%ROWTYPE;
BEGIN
    -- Get active weight config
    SELECT * INTO v_config FROM feedback_weight_configs
    WHERE is_active = true
    ORDER BY created_at DESC
    LIMIT 1;

    IF v_config IS NULL THEN
        -- Use defaults if no config
        SELECT * INTO v_config FROM feedback_weight_configs
        WHERE config_key = 'default';
    END IF;

    -- Full recompute
    WITH view_stats AS (
        SELECT
            ad_id,
            COUNT(*) as total_views,
            COUNT(DISTINCT visitor_hash) as unique_views,
            COUNT(*) FILTER (WHERE view_date >= CURRENT_DATE - 7) as views_7d,
            COUNT(*) FILTER (WHERE view_date >= CURRENT_DATE - 30) as views_30d,
            COUNT(*) FILTER (WHERE completed) as total_completions,
            AVG(watch_duration_seconds) as avg_watch_seconds,
            MIN(created_at) as first_view_at,
            MAX(created_at) as last_view_at
        FROM ad_view_events
        WHERE p_ad_id IS NULL OR ad_id = p_ad_id
        GROUP BY ad_id
    ),
    rating_stats AS (
        SELECT
            ad_id,
            COUNT(*) as rating_count,
            SUM(rating) as rating_sum,
            AVG(rating) as rating_avg,
            COUNT(*) FILTER (WHERE review_text IS NOT NULL AND status = 'approved') as review_count
        FROM ad_ratings
        WHERE p_ad_id IS NULL OR ad_id = p_ad_id
        GROUP BY ad_id
    ),
    engagement_stats AS (
        SELECT
            id as ad_id,
            COALESCE(likes, 0) as total_likes,
            COALESCE(saves, 0) as total_saves,
            0 as total_shares  -- shares not tracked in ads table currently
        FROM ads
        WHERE p_ad_id IS NULL OR id = p_ad_id
    ),
    combined AS (
        SELECT
            e.ad_id,
            COALESCE(v.total_views, 0) as total_views,
            COALESCE(v.unique_views, 0) as unique_views,
            COALESCE(v.views_7d, 0) as views_7d,
            COALESCE(v.views_30d, 0) as views_30d,
            COALESCE(v.total_completions, 0) as total_completions,
            CASE WHEN COALESCE(v.total_views, 0) > 0
                THEN v.total_completions::numeric / v.total_views
                ELSE NULL
            END as completion_rate,
            v.avg_watch_seconds,
            e.total_likes,
            e.total_saves,
            e.total_shares,
            COALESCE(r.rating_count, 0) as rating_count,
            COALESCE(r.rating_sum, 0) as rating_sum,
            r.rating_avg,
            COALESCE(r.review_count, 0) as review_count,
            v.first_view_at,
            v.last_view_at,
            GREATEST(v.last_view_at, a.updated_at) as last_engagement_at,
            -- Raw score (sum of metrics)
            (
                COALESCE(v.total_views, 0) * v_config.weight_views +
                COALESCE(v.unique_views, 0) * v_config.weight_unique_views +
                COALESCE(v.total_completions, 0) * v_config.weight_completions +
                e.total_likes * v_config.weight_likes +
                e.total_saves * v_config.weight_saves +
                e.total_shares * v_config.weight_shares +
                COALESCE(r.rating_avg, 0) * COALESCE(r.rating_count, 0) * v_config.weight_rating +
                COALESCE(r.review_count, 0) * v_config.weight_review
            ) as raw_score,
            a.created_at as ad_created_at
        FROM engagement_stats e
        LEFT JOIN view_stats v ON e.ad_id = v.ad_id
        LEFT JOIN rating_stats r ON e.ad_id = r.ad_id
        JOIN ads a ON e.ad_id = a.id
    )
    INSERT INTO ad_feedback_agg (
        ad_id, updated_at,
        total_views, unique_views, views_7d, views_30d,
        total_completions, completion_rate, avg_watch_seconds,
        total_likes, total_saves, total_shares,
        rating_count, rating_sum, rating_avg, review_count,
        raw_score, weighted_score, time_decayed_score,
        first_view_at, last_view_at, last_engagement_at
    )
    SELECT
        ad_id, now(),
        total_views, unique_views, views_7d, views_30d,
        total_completions, completion_rate, avg_watch_seconds,
        total_likes, total_saves, total_shares,
        rating_count, rating_sum, rating_avg, review_count,
        raw_score,
        -- Weighted score (with recency boost)
        raw_score * CASE
            WHEN ad_created_at >= CURRENT_DATE - v_config.recency_boost_days
            THEN v_config.recency_boost_multiplier
            ELSE 1.0
        END,
        -- Time decayed score
        raw_score * POWER(0.5,
            EXTRACT(EPOCH FROM (now() - COALESCE(last_engagement_at, ad_created_at)))
            / (v_config.decay_half_life_days * 86400)
        ),
        first_view_at, last_view_at, last_engagement_at
    FROM combined
    ON CONFLICT (ad_id) DO UPDATE SET
        updated_at = now(),
        total_views = EXCLUDED.total_views,
        unique_views = EXCLUDED.unique_views,
        views_7d = EXCLUDED.views_7d,
        views_30d = EXCLUDED.views_30d,
        total_completions = EXCLUDED.total_completions,
        completion_rate = EXCLUDED.completion_rate,
        avg_watch_seconds = EXCLUDED.avg_watch_seconds,
        total_likes = EXCLUDED.total_likes,
        total_saves = EXCLUDED.total_saves,
        total_shares = EXCLUDED.total_shares,
        rating_count = EXCLUDED.rating_count,
        rating_sum = EXCLUDED.rating_sum,
        rating_avg = EXCLUDED.rating_avg,
        review_count = EXCLUDED.review_count,
        raw_score = EXCLUDED.raw_score,
        weighted_score = EXCLUDED.weighted_score,
        time_decayed_score = EXCLUDED.time_decayed_score,
        first_view_at = EXCLUDED.first_view_at,
        last_view_at = EXCLUDED.last_view_at,
        last_engagement_at = EXCLUDED.last_engagement_at;

    GET DIAGNOSTICS v_updated = ROW_COUNT;

    -- Update rankings (if refreshing all)
    IF p_ad_id IS NULL THEN
        WITH ranked AS (
            SELECT
                ad_id,
                ROW_NUMBER() OVER (ORDER BY weighted_score DESC) as rank_by_score,
                ROW_NUMBER() OVER (ORDER BY total_views DESC) as rank_by_views,
                ROW_NUMBER() OVER (ORDER BY rating_avg DESC NULLS LAST) as rank_by_rating,
                PERCENT_RANK() OVER (ORDER BY weighted_score) * 100 as score_percentile
            FROM ad_feedback_agg
        )
        UPDATE ad_feedback_agg a SET
            rank_by_score = r.rank_by_score,
            rank_by_views = r.rank_by_views,
            rank_by_rating = r.rank_by_rating,
            score_percentile = r.score_percentile
        FROM ranked r
        WHERE a.ad_id = r.ad_id;
    END IF;

    RETURN v_updated;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- View: ad_feedback_summary (comprehensive feedback stats per ad)
-- ============================================================================
CREATE OR REPLACE VIEW ad_feedback_summary AS
SELECT
    a.id as ad_id,
    a.external_id,
    a.brand,
    a.title,
    a.created_at as ad_created_at,

    -- View metrics
    COALESCE(f.total_views, 0) as total_views,
    COALESCE(f.unique_views, 0) as unique_views,
    COALESCE(f.views_7d, 0) as views_7d,
    COALESCE(f.views_30d, 0) as views_30d,

    -- Completion metrics
    COALESCE(f.total_completions, 0) as total_completions,
    f.completion_rate,
    f.avg_watch_seconds,

    -- Engagement
    COALESCE(a.likes, 0) as likes,
    COALESCE(a.saves, 0) as saves,
    COALESCE(f.total_shares, 0) as shares,

    -- Ratings
    COALESCE(f.rating_count, 0) as rating_count,
    f.rating_avg,
    COALESCE(f.review_count, 0) as review_count,

    -- Scores
    COALESCE(f.raw_score, 0) as raw_score,
    COALESCE(f.weighted_score, 0) as weighted_score,
    COALESCE(f.time_decayed_score, 0) as time_decayed_score,

    -- Rankings
    f.rank_by_score,
    f.rank_by_views,
    f.rank_by_rating,
    f.score_percentile,

    -- Timestamps
    f.first_view_at,
    f.last_view_at,
    f.last_engagement_at,
    f.updated_at as metrics_updated_at
FROM ads a
LEFT JOIN ad_feedback_agg f ON a.id = f.ad_id;

-- ============================================================================
-- View: feedback_leaderboard (top-rated ads with composite scores)
-- ============================================================================
CREATE OR REPLACE VIEW feedback_leaderboard AS
SELECT
    ad_id,
    external_id,
    brand,
    title,
    weighted_score,
    time_decayed_score,
    total_views,
    rating_avg,
    rating_count,
    likes,
    rank_by_score,
    score_percentile
FROM ad_feedback_summary
WHERE total_views > 0 OR rating_count > 0
ORDER BY weighted_score DESC;

-- ============================================================================
-- View: pending_reviews (for admin moderation)
-- ============================================================================
CREATE OR REPLACE VIEW pending_reviews AS
SELECT
    r.id,
    r.ad_id,
    a.external_id,
    a.brand,
    a.title,
    r.rating,
    r.review_text,
    r.created_at,
    r.session_id,
    r.reported_count
FROM ad_ratings r
JOIN ads a ON r.ad_id = a.id
WHERE r.status = 'pending'
  AND r.review_text IS NOT NULL
ORDER BY r.created_at DESC;

-- ============================================================================
-- Comments
-- ============================================================================
COMMENT ON TABLE ad_view_events IS
'Deduplicated view tracking. One entry per ad/session/day. Aggregated into ad_feedback_agg.';

COMMENT ON TABLE ad_ratings IS
'User ratings and reviews for ads. One rating per user/session per ad.';

COMMENT ON TABLE feedback_weight_configs IS
'Admin-configurable weights for computing ad scores. Default config always exists.';

COMMENT ON TABLE ad_feedback_agg IS
'Pre-computed aggregate metrics per ad. Refreshed by refresh_ad_feedback_agg().';

COMMENT ON FUNCTION record_ad_view IS
'Record a deduplicated view event. Automatically updates aggregates.';

COMMENT ON FUNCTION record_ad_rating IS
'Record or update a rating. Automatically updates aggregates.';

COMMENT ON FUNCTION refresh_ad_feedback_agg IS
'Recompute all aggregate metrics. Run daily via cron or after weight config changes.';
