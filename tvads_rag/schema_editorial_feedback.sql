-- =============================================================================
-- TellyAds Editorial + Feedback Schema Migration
-- Version: 1.0.1
-- Date: 2025-12-04
--
-- This migration adds:
--   1. ad_editorial - Human-authored content sidecar (Wix CMS migration target)
--   2. ad_user_reactions - User reaction state (likes, saves, shares)
--   3. ad_user_tags - User-suggested tags with moderation
--   4. ad_feedback_agg - Aggregated metrics for search ranking
--
-- Corrections applied:
--   A) Likes: State table approach (not event log with toggles)
--   B) No duplicate tag storage (tags in ad_user_tags only, counts in agg)
--   C) Proper Postgres partial unique indexes
--   D) Views: Counter increment, not row-per-view
--   E) Ranking boosts: Thresholds defined, applied at query time
--
-- Privacy notes:
--   - session_id = random UUID stored in localStorage (NOT fingerprinting)
--   - No IP addresses stored
--   - No PII collected
-- =============================================================================

-- Ensure required extensions (idempotent)
-- Only pgcrypto needed for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -----------------------------------------------------------------------------
-- 1. EDITORIAL SIDECAR TABLE (Human-owned content from Wix CMS)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ad_editorial (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id uuid NOT NULL REFERENCES ads(id) ON DELETE CASCADE,

    -- SEO URL structure: /advert/{brand_slug}/{slug}
    brand_slug text NOT NULL,           -- e.g., 'specsavers'
    slug text NOT NULL,                 -- e.g., 'clown-surprise-n'

    -- Human-authored content
    headline text,                      -- Editorial headline
    editorial_summary text,             -- Human-written description
    curated_tags text[] DEFAULT '{}',   -- Staff-curated tags

    -- Metadata from Wix CMS
    wix_item_id text,                   -- Original Wix CMS ID
    original_publish_date timestamptz,  -- When first published on Wix

    -- Admin overrides (trumps extractor values)
    override_brand_name text,           -- Override extracted brand_name
    override_year integer,              -- Override extracted year
    override_product_category text,     -- Override extracted category

    -- Publishing workflow
    status text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'archived')),
    publish_date timestamptz,           -- Scheduled publish (NULL = immediate when published)

    -- Content flags
    is_featured boolean DEFAULT false,
    is_hidden boolean DEFAULT false,    -- Soft delete / hide from public
    editor_notes text,                  -- Internal notes

    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- SEO-friendly URL uniqueness: /advert/{brand_slug}/{slug}
CREATE UNIQUE INDEX IF NOT EXISTS idx_ad_editorial_url_unique
    ON ad_editorial(brand_slug, slug);

-- Fast lookup by ad_id (1:1 relationship)
CREATE UNIQUE INDEX IF NOT EXISTS idx_ad_editorial_ad_id_unique
    ON ad_editorial(ad_id);

-- Wix migration dedup
CREATE UNIQUE INDEX IF NOT EXISTS idx_ad_editorial_wix_id_unique
    ON ad_editorial(wix_item_id) WHERE wix_item_id IS NOT NULL;

-- Featured ads query
CREATE INDEX IF NOT EXISTS idx_ad_editorial_featured
    ON ad_editorial(is_featured) WHERE is_featured = true AND status = 'published';

-- Published content (for SEO route gating)
CREATE INDEX IF NOT EXISTS idx_ad_editorial_published
    ON ad_editorial(status, publish_date)
    WHERE status = 'published' AND is_hidden = false;

-- -----------------------------------------------------------------------------
-- 2. USER REACTIONS STATE TABLE (Correction A: State, not event log)
-- -----------------------------------------------------------------------------
-- Stores current state per user/ad pair. Toggle = UPDATE, not INSERT dual events.
-- Uses session_id = random UUID from localStorage (privacy-safe, no fingerprinting)
CREATE TABLE IF NOT EXISTS ad_user_reactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id uuid NOT NULL REFERENCES ads(id) ON DELETE CASCADE,

    -- Anonymous user identification
    session_id text NOT NULL,           -- Browser fingerprint or session token

    -- Reaction states (nullable = not set)
    is_liked boolean,                   -- true/false/null
    is_saved boolean,                   -- true/false/null
    is_shared boolean,                  -- true = shared at least once

    -- Timestamps for analytics
    liked_at timestamptz,
    saved_at timestamptz,
    shared_at timestamptz,

    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- One reaction record per user per ad
CREATE UNIQUE INDEX IF NOT EXISTS idx_ad_user_reactions_unique
    ON ad_user_reactions(ad_id, session_id);

-- Query user's saved/liked ads
CREATE INDEX IF NOT EXISTS idx_ad_user_reactions_session_liked
    ON ad_user_reactions(session_id, is_liked) WHERE is_liked = true;
CREATE INDEX IF NOT EXISTS idx_ad_user_reactions_session_saved
    ON ad_user_reactions(session_id, is_saved) WHERE is_saved = true;

-- -----------------------------------------------------------------------------
-- 3. USER-SUGGESTED TAGS WITH MODERATION
-- -----------------------------------------------------------------------------
-- Correction B: Tags stored here only, counts aggregated in ad_feedback_agg
CREATE TABLE IF NOT EXISTS ad_user_tags (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id uuid NOT NULL REFERENCES ads(id) ON DELETE CASCADE,
    session_id text NOT NULL,           -- Who suggested it

    tag text NOT NULL,                  -- Normalized tag (lowercase, trimmed)

    -- Moderation
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'spam')),
    moderated_by text,                  -- Admin who reviewed
    moderated_at timestamptz,
    rejection_reason text,

    created_at timestamptz DEFAULT now()
);

-- Correction C: Proper partial unique index syntax
-- One suggestion per tag per user per ad
CREATE UNIQUE INDEX IF NOT EXISTS idx_ad_user_tags_unique
    ON ad_user_tags(ad_id, session_id, tag);

-- Moderation queue (pending tags)
CREATE INDEX IF NOT EXISTS idx_ad_user_tags_pending
    ON ad_user_tags(status, created_at) WHERE status = 'pending';

-- Approved tags for an ad
CREATE INDEX IF NOT EXISTS idx_ad_user_tags_approved
    ON ad_user_tags(ad_id, tag) WHERE status = 'approved';

-- -----------------------------------------------------------------------------
-- 4. FEEDBACK AGGREGATES (Derived metrics for search ranking)
-- -----------------------------------------------------------------------------
-- Correction D: Views stored as counter, not row-per-view
-- Correction E: Thresholds for ranking boosts defined in comments
CREATE TABLE IF NOT EXISTS ad_feedback_agg (
    ad_id uuid PRIMARY KEY REFERENCES ads(id) ON DELETE CASCADE,

    -- Counters (Correction D: increment, not rows)
    view_count integer DEFAULT 0,
    like_count integer DEFAULT 0,
    save_count integer DEFAULT 0,
    share_count integer DEFAULT 0,

    -- Tag aggregation (Correction B: counts derived from ad_user_tags)
    -- JSONB: {"nostalgic": 5, "funny": 3, ...}
    tag_counts jsonb DEFAULT '{}'::jsonb,
    approved_tag_count integer DEFAULT 0,

    -- Engagement score (computed, 0-100)
    -- Formula: (likes*3 + saves*5 + shares*2) / views * 100, capped at 100
    engagement_score numeric(5,2) DEFAULT 0,

    -- Timestamps
    first_view_at timestamptz,
    last_interaction_at timestamptz,

    updated_at timestamptz DEFAULT now()
);

-- Ranking boost index (Correction E: only query ads meeting thresholds)
-- Threshold: 5+ likes OR 3+ saves for search ranking boost
CREATE INDEX IF NOT EXISTS idx_ad_feedback_agg_popular
    ON ad_feedback_agg(engagement_score DESC)
    WHERE like_count >= 5 OR save_count >= 3;

-- -----------------------------------------------------------------------------
-- 5. RATE LIMITING TABLE (Anti-gaming)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ad_rate_limits (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id text NOT NULL,
    action_type text NOT NULL,          -- 'like', 'tag_suggest', 'view', etc.
    window_start timestamptz NOT NULL DEFAULT date_trunc('hour', now()),
    action_count integer DEFAULT 1,

    -- Unique per session/action/hour
    UNIQUE(session_id, action_type, window_start)
);

-- Cleanup old rate limit records (run periodically)
CREATE INDEX IF NOT EXISTS idx_ad_rate_limits_cleanup
    ON ad_rate_limits(window_start);

-- -----------------------------------------------------------------------------
-- 6. TRIGGER FUNCTIONS (Update aggregates on reaction changes)
-- -----------------------------------------------------------------------------

-- Function: Update ad_feedback_agg when reactions change
-- Uses delta-based updates for efficiency (handles state transitions correctly)
CREATE OR REPLACE FUNCTION fn_update_feedback_agg_on_reaction()
RETURNS TRIGGER AS $$
DECLARE
    v_ad_id uuid;
    v_like_delta integer := 0;
    v_save_delta integer := 0;
    v_share_delta integer := 0;
BEGIN
    v_ad_id := COALESCE(NEW.ad_id, OLD.ad_id);

    -- Ensure agg row exists
    INSERT INTO ad_feedback_agg (ad_id)
    VALUES (v_ad_id)
    ON CONFLICT (ad_id) DO NOTHING;

    -- Calculate deltas based on state transitions
    IF TG_OP = 'INSERT' THEN
        -- New record: count true values
        v_like_delta := CASE WHEN NEW.is_liked = true THEN 1 ELSE 0 END;
        v_save_delta := CASE WHEN NEW.is_saved = true THEN 1 ELSE 0 END;
        v_share_delta := CASE WHEN NEW.is_shared = true THEN 1 ELSE 0 END;

    ELSIF TG_OP = 'UPDATE' THEN
        -- State transition: +1 for false/null→true, -1 for true→false/null
        v_like_delta := CASE
            WHEN COALESCE(OLD.is_liked, false) = false AND NEW.is_liked = true THEN 1
            WHEN OLD.is_liked = true AND COALESCE(NEW.is_liked, false) = false THEN -1
            ELSE 0
        END;
        v_save_delta := CASE
            WHEN COALESCE(OLD.is_saved, false) = false AND NEW.is_saved = true THEN 1
            WHEN OLD.is_saved = true AND COALESCE(NEW.is_saved, false) = false THEN -1
            ELSE 0
        END;
        v_share_delta := CASE
            WHEN COALESCE(OLD.is_shared, false) = false AND NEW.is_shared = true THEN 1
            WHEN OLD.is_shared = true AND COALESCE(NEW.is_shared, false) = false THEN -1
            ELSE 0
        END;

    ELSIF TG_OP = 'DELETE' THEN
        -- Deleted record: subtract true values
        v_like_delta := CASE WHEN OLD.is_liked = true THEN -1 ELSE 0 END;
        v_save_delta := CASE WHEN OLD.is_saved = true THEN -1 ELSE 0 END;
        v_share_delta := CASE WHEN OLD.is_shared = true THEN -1 ELSE 0 END;
    END IF;

    -- Apply deltas (atomic update)
    UPDATE ad_feedback_agg
    SET
        like_count = GREATEST(0, like_count + v_like_delta),
        save_count = GREATEST(0, save_count + v_save_delta),
        share_count = GREATEST(0, share_count + v_share_delta),
        last_interaction_at = now(),
        updated_at = now(),
        -- Update engagement score inline
        engagement_score = LEAST(100,
            CASE WHEN view_count >= 10 THEN
                (GREATEST(0, like_count + v_like_delta) * 3.0 +
                 GREATEST(0, save_count + v_save_delta) * 5.0 +
                 GREATEST(0, share_count + v_share_delta) * 2.0) / GREATEST(view_count, 1) * 100
            ELSE 0 END
        )
    WHERE ad_id = v_ad_id;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Function: Update tag counts when tags are approved/rejected
CREATE OR REPLACE FUNCTION fn_update_tag_counts()
RETURNS TRIGGER AS $$
BEGIN
    -- Ensure agg row exists
    INSERT INTO ad_feedback_agg (ad_id)
    VALUES (COALESCE(NEW.ad_id, OLD.ad_id))
    ON CONFLICT (ad_id) DO NOTHING;

    -- Recalculate tag counts for this ad (only approved tags)
    UPDATE ad_feedback_agg
    SET
        tag_counts = COALESCE((
            SELECT jsonb_object_agg(tag, cnt)
            FROM (
                SELECT tag, COUNT(*) as cnt
                FROM ad_user_tags
                WHERE ad_id = COALESCE(NEW.ad_id, OLD.ad_id)
                  AND status = 'approved'
                GROUP BY tag
            ) t
        ), '{}'::jsonb),
        approved_tag_count = (
            SELECT COUNT(DISTINCT tag) FROM ad_user_tags
            WHERE ad_id = COALESCE(NEW.ad_id, OLD.ad_id) AND status = 'approved'
        ),
        updated_at = now()
    WHERE ad_id = COALESCE(NEW.ad_id, OLD.ad_id);

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 7. CREATE TRIGGERS
-- -----------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_reaction_agg ON ad_user_reactions;
CREATE TRIGGER trg_reaction_agg
    AFTER INSERT OR UPDATE OR DELETE ON ad_user_reactions
    FOR EACH ROW EXECUTE FUNCTION fn_update_feedback_agg_on_reaction();

DROP TRIGGER IF EXISTS trg_tag_counts ON ad_user_tags;
CREATE TRIGGER trg_tag_counts
    AFTER INSERT OR UPDATE OF status OR DELETE ON ad_user_tags
    FOR EACH ROW EXECUTE FUNCTION fn_update_tag_counts();

-- -----------------------------------------------------------------------------
-- 8. HELPER FUNCTIONS
-- -----------------------------------------------------------------------------

-- Increment view count (Correction D: single update, not row insert)
CREATE OR REPLACE FUNCTION fn_record_ad_view(p_ad_id uuid, p_session_id text)
RETURNS void AS $$
BEGIN
    -- Check rate limit (max 10 views per ad per hour per session)
    INSERT INTO ad_rate_limits (session_id, action_type, window_start, action_count)
    VALUES (p_session_id, 'view:' || p_ad_id::text, date_trunc('hour', now()), 1)
    ON CONFLICT (session_id, action_type, window_start)
    DO UPDATE SET action_count = ad_rate_limits.action_count + 1
    WHERE ad_rate_limits.action_count < 10;

    -- Only increment if not rate limited
    IF FOUND THEN
        INSERT INTO ad_feedback_agg (ad_id, view_count, first_view_at)
        VALUES (p_ad_id, 1, now())
        ON CONFLICT (ad_id) DO UPDATE SET
            view_count = ad_feedback_agg.view_count + 1,
            first_view_at = COALESCE(ad_feedback_agg.first_view_at, now()),
            updated_at = now();
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Toggle like state (Correction A: update state, not insert events)
CREATE OR REPLACE FUNCTION fn_toggle_like(p_ad_id uuid, p_session_id text)
RETURNS boolean AS $$
DECLARE
    v_new_state boolean;
BEGIN
    -- Check rate limit (max 50 likes per hour)
    PERFORM 1 FROM ad_rate_limits
    WHERE session_id = p_session_id
      AND action_type = 'like'
      AND window_start = date_trunc('hour', now())
      AND action_count >= 50;

    IF FOUND THEN
        RAISE EXCEPTION 'Rate limit exceeded';
    END IF;

    -- Record rate limit
    INSERT INTO ad_rate_limits (session_id, action_type, window_start, action_count)
    VALUES (p_session_id, 'like', date_trunc('hour', now()), 1)
    ON CONFLICT (session_id, action_type, window_start)
    DO UPDATE SET action_count = ad_rate_limits.action_count + 1;

    -- Toggle like state
    INSERT INTO ad_user_reactions (ad_id, session_id, is_liked, liked_at)
    VALUES (p_ad_id, p_session_id, true, now())
    ON CONFLICT (ad_id, session_id) DO UPDATE SET
        is_liked = NOT COALESCE(ad_user_reactions.is_liked, false),
        liked_at = CASE
            WHEN NOT COALESCE(ad_user_reactions.is_liked, false) THEN now()
            ELSE ad_user_reactions.liked_at
        END,
        updated_at = now()
    RETURNING is_liked INTO v_new_state;

    RETURN v_new_state;
END;
$$ LANGUAGE plpgsql;

-- Toggle save state
CREATE OR REPLACE FUNCTION fn_toggle_save(p_ad_id uuid, p_session_id text)
RETURNS boolean AS $$
DECLARE
    v_new_state boolean;
BEGIN
    INSERT INTO ad_user_reactions (ad_id, session_id, is_saved, saved_at)
    VALUES (p_ad_id, p_session_id, true, now())
    ON CONFLICT (ad_id, session_id) DO UPDATE SET
        is_saved = NOT COALESCE(ad_user_reactions.is_saved, false),
        saved_at = CASE
            WHEN NOT COALESCE(ad_user_reactions.is_saved, false) THEN now()
            ELSE ad_user_reactions.saved_at
        END,
        updated_at = now()
    RETURNING is_saved INTO v_new_state;

    RETURN v_new_state;
END;
$$ LANGUAGE plpgsql;

-- Suggest a tag (with rate limiting)
CREATE OR REPLACE FUNCTION fn_suggest_tag(
    p_ad_id uuid,
    p_session_id text,
    p_tag text
)
RETURNS uuid AS $$
DECLARE
    v_tag_id uuid;
    v_normalized_tag text;
BEGIN
    -- Normalize tag
    v_normalized_tag := lower(trim(p_tag));

    -- Validate tag (2-30 chars, alphanumeric + spaces)
    IF v_normalized_tag !~ '^[a-z0-9 ]{2,30}$' THEN
        RAISE EXCEPTION 'Invalid tag format';
    END IF;

    -- Check rate limit (max 10 tag suggestions per hour)
    PERFORM 1 FROM ad_rate_limits
    WHERE session_id = p_session_id
      AND action_type = 'tag_suggest'
      AND window_start = date_trunc('hour', now())
      AND action_count >= 10;

    IF FOUND THEN
        RAISE EXCEPTION 'Rate limit exceeded';
    END IF;

    -- Record rate limit
    INSERT INTO ad_rate_limits (session_id, action_type, window_start, action_count)
    VALUES (p_session_id, 'tag_suggest', date_trunc('hour', now()), 1)
    ON CONFLICT (session_id, action_type, window_start)
    DO UPDATE SET action_count = ad_rate_limits.action_count + 1;

    -- Insert tag suggestion
    INSERT INTO ad_user_tags (ad_id, session_id, tag)
    VALUES (p_ad_id, p_session_id, v_normalized_tag)
    ON CONFLICT (ad_id, session_id, tag) DO NOTHING
    RETURNING id INTO v_tag_id;

    RETURN v_tag_id;
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 9. VIEWS FOR EASY QUERYING
-- -----------------------------------------------------------------------------

-- Drop views first to allow column changes (CREATE OR REPLACE can't change columns)
DROP VIEW IF EXISTS v_ad_with_editorial;
DROP VIEW IF EXISTS v_tag_moderation_queue;

-- Ad with editorial overlay (merges extractor + human content)
CREATE OR REPLACE VIEW v_ad_with_editorial AS
SELECT
    a.id,
    a.external_id,
    -- Editorial URL components
    e.brand_slug,
    e.slug,
    -- Use editorial override if set, else extractor value
    COALESCE(e.override_brand_name, a.brand_name) as brand_name,
    COALESCE(e.override_year, a.year) as year,
    COALESCE(e.override_product_category, a.product_category) as product_category,
    -- Editorial content
    e.headline,
    COALESCE(e.editorial_summary, a.one_line_summary) as summary,
    e.curated_tags,
    e.is_featured,
    -- Extractor content
    a.product_name,
    a.one_line_summary as extracted_summary,
    a.story_summary,
    a.duration_seconds,
    a.format_type,
    a.hero_analysis,
    a.impact_scores,
    -- Feedback (with threshold for ranking - Correction E)
    COALESCE(f.view_count, 0) as view_count,
    COALESCE(f.like_count, 0) as like_count,
    COALESCE(f.save_count, 0) as save_count,
    COALESCE(f.engagement_score, 0) as engagement_score,
    f.tag_counts as user_tag_counts,
    -- Ranking boost flag (Correction E: threshold-based)
    (COALESCE(f.like_count, 0) >= 5 OR COALESCE(f.save_count, 0) >= 3) as has_ranking_boost,
    -- Timestamps
    a.created_at,
    a.updated_at,
    e.original_publish_date
FROM ads a
LEFT JOIN ad_editorial e ON e.ad_id = a.id AND e.is_hidden = false
LEFT JOIN ad_feedback_agg f ON f.ad_id = a.id;

-- Moderation queue view
CREATE OR REPLACE VIEW v_tag_moderation_queue AS
SELECT
    t.id as tag_id,
    t.ad_id,
    t.tag,
    t.session_id,
    t.created_at,
    a.brand_name,
    a.product_name,
    COUNT(*) OVER (PARTITION BY t.ad_id, t.tag) as suggestion_count
FROM ad_user_tags t
JOIN ads a ON a.id = t.ad_id
WHERE t.status = 'pending'
ORDER BY t.created_at ASC;

-- -----------------------------------------------------------------------------
-- 10. CLEANUP FUNCTION (Run periodically)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_cleanup_rate_limits()
RETURNS integer AS $$
DECLARE
    v_deleted integer;
BEGIN
    DELETE FROM ad_rate_limits
    WHERE window_start < now() - interval '24 hours';

    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted;
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- COMMENTS: Ranking Boost Thresholds (Correction E)
-- -----------------------------------------------------------------------------
-- The following thresholds are used for search ranking boosts:
--   - Minimum 5 likes OR 3 saves to get engagement boost
--   - Minimum 10 views before engagement_score is calculated
--   - engagement_score = (likes*3 + saves*5 + shares*2) / views * 100
--
-- These thresholds prevent gaming by requiring genuine engagement
-- before boosting search visibility.
-- -----------------------------------------------------------------------------
