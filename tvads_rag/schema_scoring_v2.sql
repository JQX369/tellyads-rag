-- =============================================================================
-- TellyAds Scoring V2: AI + User Blended Scoring
-- Version: 2.0.0
-- Date: 2025-12-04
--
-- Changes:
--   1. Split scoring into ai_score (from extraction) and user_score (from engagement)
--   2. Anti-gaming: use distinct session counts instead of raw totals
--   3. Confidence-weighted blending: final_score = ai_score*(1-w) + user_score*w
--   4. Public display threshold for reason_counts
--
-- Formula Constants (documented):
--   AI_SCORE_WEIGHT_MIN = 0.4 (at max engagement, user still gets 60% max)
--   CONFIDENCE_SESSIONS_CAP = 50 (sessions needed for max user_score weight)
--   REASON_DISPLAY_THRESHOLD = 10 (min distinct sessions before public display)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. ADD NEW COLUMNS TO ad_feedback_agg
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    -- AI-derived score from extraction (0-100)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ad_feedback_agg' AND column_name = 'ai_score'
    ) THEN
        ALTER TABLE ad_feedback_agg ADD COLUMN ai_score numeric(5,2) DEFAULT 0;
    END IF;

    -- User-derived score from engagement (0-100)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ad_feedback_agg' AND column_name = 'user_score'
    ) THEN
        ALTER TABLE ad_feedback_agg ADD COLUMN user_score numeric(5,2) DEFAULT 0;
    END IF;

    -- Final blended score (replaces blended_score concept)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ad_feedback_agg' AND column_name = 'final_score'
    ) THEN
        ALTER TABLE ad_feedback_agg ADD COLUMN final_score numeric(5,2) DEFAULT 0;
    END IF;

    -- Distinct sessions that submitted reasons (anti-gaming)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ad_feedback_agg' AND column_name = 'distinct_reason_sessions'
    ) THEN
        ALTER TABLE ad_feedback_agg ADD COLUMN distinct_reason_sessions integer DEFAULT 0;
    END IF;

    -- Confidence weight (computed, 0.0-0.6)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ad_feedback_agg' AND column_name = 'confidence_weight'
    ) THEN
        ALTER TABLE ad_feedback_agg ADD COLUMN confidence_weight numeric(3,2) DEFAULT 0;
    END IF;
END;
$$;

-- -----------------------------------------------------------------------------
-- 2. SCORING CONSTANTS (as a config function for easy tuning)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_scoring_constants()
RETURNS TABLE (
    key text,
    value numeric,
    description text
) AS $$
    SELECT * FROM (VALUES
        ('AI_SCORE_WEIGHT_MIN', 0.4, 'Min weight for AI score (user gets max 60%)'),
        ('CONFIDENCE_SESSIONS_CAP', 50, 'Sessions needed for max user influence'),
        ('REASON_DISPLAY_THRESHOLD', 10, 'Min distinct sessions before public reason display'),
        ('ENGAGEMENT_VIEW_MIN', 10, 'Min views before engagement score calculated'),
        ('LIKE_WEIGHT', 3.0, 'Weight for likes in user_score'),
        ('SAVE_WEIGHT', 5.0, 'Weight for saves in user_score'),
        ('SHARE_WEIGHT', 2.0, 'Weight for shares in user_score'),
        ('REASON_DIVERSITY_BONUS', 2.0, 'Bonus per unique reason type'),
        ('REASON_SESSION_BONUS', 0.5, 'Bonus per distinct session with reasons')
    ) AS t(key, value, description);
$$ LANGUAGE sql IMMUTABLE;

-- -----------------------------------------------------------------------------
-- 3. FUNCTION: Compute AI Score from extraction data
-- -----------------------------------------------------------------------------
-- Aggregates impact_scores JSONB into a single 0-100 score
-- Handles multiple data formats:
--   1. Simple: {"pulse": 85, "echo": 72}
--   2. Nested with score: {"hook_power": {"score": 7.8, ...}}
--   3. Nested under "scores": {"scores": {"pulse": 85}}
CREATE OR REPLACE FUNCTION fn_compute_ai_score(p_ad_id uuid)
RETURNS numeric AS $$
DECLARE
    v_impact jsonb;
    v_scores numeric[] := ARRAY[]::numeric[];
    v_field text;
    v_val numeric;
    v_field_data jsonb;
    v_avg numeric;
    v_fields text[] := ARRAY['pulse', 'echo', 'hook_power', 'brand_integration',
                              'emotional_resonance', 'clarity', 'distinctiveness',
                              'hook_score', 'brand_recall', 'message_clarity'];
BEGIN
    -- Get impact_scores from ads table
    SELECT impact_scores INTO v_impact
    FROM ads WHERE id = p_ad_id;

    IF v_impact IS NULL THEN
        RETURN 50; -- Default neutral score if no AI analysis
    END IF;

    -- Try each field, handling multiple formats
    FOREACH v_field IN ARRAY v_fields LOOP
        -- Skip if field doesn't exist
        IF v_impact->v_field IS NULL THEN
            CONTINUE;
        END IF;

        v_field_data := v_impact->v_field;

        -- Format 1: Simple numeric value {"pulse": 85}
        IF jsonb_typeof(v_field_data) = 'number' THEN
            v_val := (v_impact->>v_field)::numeric;
            -- Scale 0-10 scores to 0-100
            IF v_val <= 10 THEN
                v_val := v_val * 10;
            END IF;
            v_scores := array_append(v_scores, LEAST(100, GREATEST(0, v_val)));

        -- Format 2: Nested object with "score" key {"hook_power": {"score": 7.8}}
        ELSIF jsonb_typeof(v_field_data) = 'object' AND v_field_data->>'score' IS NOT NULL THEN
            v_val := (v_field_data->>'score')::numeric;
            -- Scale 0-10 scores to 0-100
            IF v_val <= 10 THEN
                v_val := v_val * 10;
            END IF;
            v_scores := array_append(v_scores, LEAST(100, GREATEST(0, v_val)));
        END IF;
    END LOOP;

    -- If no valid scores, check for nested "scores" object
    IF array_length(v_scores, 1) IS NULL OR array_length(v_scores, 1) = 0 THEN
        IF v_impact->'scores' IS NOT NULL THEN
            FOREACH v_field IN ARRAY v_fields LOOP
                IF v_impact->'scores'->v_field IS NULL THEN
                    CONTINUE;
                END IF;

                v_field_data := v_impact->'scores'->v_field;

                IF jsonb_typeof(v_field_data) = 'number' THEN
                    v_val := (v_impact->'scores'->>v_field)::numeric;
                    IF v_val <= 10 THEN
                        v_val := v_val * 10;
                    END IF;
                    v_scores := array_append(v_scores, LEAST(100, GREATEST(0, v_val)));
                ELSIF jsonb_typeof(v_field_data) = 'object' AND v_field_data->>'score' IS NOT NULL THEN
                    v_val := (v_field_data->>'score')::numeric;
                    IF v_val <= 10 THEN
                        v_val := v_val * 10;
                    END IF;
                    v_scores := array_append(v_scores, LEAST(100, GREATEST(0, v_val)));
                END IF;
            END LOOP;
        END IF;
    END IF;

    -- Compute average, default to 50 if no scores
    IF array_length(v_scores, 1) IS NULL OR array_length(v_scores, 1) = 0 THEN
        RETURN 50;
    END IF;

    SELECT AVG(s) INTO v_avg FROM unnest(v_scores) AS s;
    RETURN LEAST(100, GREATEST(0, ROUND(v_avg, 2)));
END;
$$ LANGUAGE plpgsql STABLE;

-- -----------------------------------------------------------------------------
-- 4. FUNCTION: Compute User Score from engagement + reasons
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_compute_user_score(
    p_view_count integer,
    p_like_count integer,
    p_save_count integer,
    p_share_count integer,
    p_distinct_reason_sessions integer,
    p_unique_reason_types integer
)
RETURNS numeric AS $$
DECLARE
    v_engagement numeric;
    v_reason_bonus numeric;
    v_total numeric;
BEGIN
    -- Base engagement (same formula as before, but capped at 70)
    IF p_view_count >= 10 THEN
        v_engagement := LEAST(70,
            (p_like_count * 3.0 + p_save_count * 5.0 + p_share_count * 2.0)
            / GREATEST(p_view_count, 1) * 100
        );
    ELSE
        v_engagement := 0;
    END IF;

    -- Reason bonus: diversity + session breadth (max 30)
    -- +2 per unique reason type (max 20 for 10 types)
    -- +0.5 per distinct session with reasons (max 10 for 20 sessions)
    v_reason_bonus := LEAST(30,
        (LEAST(p_unique_reason_types, 10) * 2.0) +
        (LEAST(p_distinct_reason_sessions, 20) * 0.5)
    );

    v_total := v_engagement + v_reason_bonus;
    RETURN LEAST(100, GREATEST(0, ROUND(v_total, 2)));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- -----------------------------------------------------------------------------
-- 5. FUNCTION: Compute confidence weight based on engagement volume
-- -----------------------------------------------------------------------------
-- Returns 0.0 to 0.6 (user_score weight)
-- At low engagement, AI dominates (weight ~0)
-- At high engagement (50+ distinct sessions), user gets max 60% weight
CREATE OR REPLACE FUNCTION fn_compute_confidence_weight(
    p_distinct_reason_sessions integer,
    p_like_count integer,
    p_save_count integer
)
RETURNS numeric AS $$
DECLARE
    v_engagement_signals integer;
    v_raw_weight numeric;
BEGIN
    -- Total engagement signals
    v_engagement_signals := p_distinct_reason_sessions + p_like_count + p_save_count;

    -- Linear ramp from 0 to 0.6 over 50 signals, capped
    v_raw_weight := LEAST(0.6, (v_engagement_signals::numeric / 50.0) * 0.6);

    RETURN ROUND(v_raw_weight, 2);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- -----------------------------------------------------------------------------
-- 6. UPDATE REASON COUNTS TRIGGER (use distinct sessions)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_update_reason_counts()
RETURNS TRIGGER AS $$
DECLARE
    v_ad_id uuid;
    v_reason_counts jsonb;
    v_distinct_sessions integer;
    v_unique_reason_types integer;
    v_ai_score numeric;
    v_user_score numeric;
    v_confidence_weight numeric;
    v_final_score numeric;
    v_view_count integer;
    v_like_count integer;
    v_save_count integer;
    v_share_count integer;
BEGIN
    v_ad_id := COALESCE(NEW.ad_id, OLD.ad_id);

    -- Ensure agg row exists
    INSERT INTO ad_feedback_agg (ad_id)
    VALUES (v_ad_id)
    ON CONFLICT (ad_id) DO NOTHING;

    -- Count distinct sessions that have submitted reasons (anti-gaming)
    SELECT COUNT(DISTINCT session_id) INTO v_distinct_sessions
    FROM ad_like_reasons
    WHERE ad_id = v_ad_id;

    -- Count unique reason types
    SELECT COUNT(DISTINCT reason) INTO v_unique_reason_types
    FROM ad_like_reasons
    WHERE ad_id = v_ad_id;

    -- Recalculate reason counts (grouped by reason)
    SELECT COALESCE(jsonb_object_agg(reason, cnt), '{}'::jsonb)
    INTO v_reason_counts
    FROM (
        SELECT reason, COUNT(DISTINCT session_id) as cnt
        FROM ad_like_reasons
        WHERE ad_id = v_ad_id
        GROUP BY reason
    ) t;

    -- Get current engagement counts
    SELECT view_count, like_count, save_count, share_count
    INTO v_view_count, v_like_count, v_save_count, v_share_count
    FROM ad_feedback_agg WHERE ad_id = v_ad_id;

    -- Compute scores
    v_ai_score := fn_compute_ai_score(v_ad_id);
    v_user_score := fn_compute_user_score(
        COALESCE(v_view_count, 0),
        COALESCE(v_like_count, 0),
        COALESCE(v_save_count, 0),
        COALESCE(v_share_count, 0),
        v_distinct_sessions,
        v_unique_reason_types
    );
    v_confidence_weight := fn_compute_confidence_weight(
        v_distinct_sessions,
        COALESCE(v_like_count, 0),
        COALESCE(v_save_count, 0)
    );

    -- final_score = ai_score * (1 - w) + user_score * w
    v_final_score := ROUND(
        v_ai_score * (1 - v_confidence_weight) + v_user_score * v_confidence_weight,
        2
    );

    -- Update aggregate
    UPDATE ad_feedback_agg
    SET
        reason_counts = v_reason_counts,
        reason_total = v_distinct_sessions, -- Now stores distinct sessions, not raw count
        distinct_reason_sessions = v_distinct_sessions,
        ai_score = v_ai_score,
        user_score = v_user_score,
        confidence_weight = v_confidence_weight,
        final_score = v_final_score,
        -- Keep blended_score for backwards compat (same as final_score)
        blended_score = v_final_score,
        updated_at = now()
    WHERE ad_id = v_ad_id;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 7. UPDATE REACTION TRIGGER (recalculate scores on engagement change)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_update_feedback_agg_on_reaction()
RETURNS TRIGGER AS $$
DECLARE
    v_ad_id uuid;
    v_like_delta integer := 0;
    v_save_delta integer := 0;
    v_share_delta integer := 0;
    v_new_like_count integer;
    v_new_save_count integer;
    v_new_share_count integer;
    v_view_count integer;
    v_distinct_sessions integer;
    v_unique_reason_types integer;
    v_ai_score numeric;
    v_user_score numeric;
    v_confidence_weight numeric;
    v_final_score numeric;
BEGIN
    v_ad_id := COALESCE(NEW.ad_id, OLD.ad_id);

    -- Ensure agg row exists
    INSERT INTO ad_feedback_agg (ad_id)
    VALUES (v_ad_id)
    ON CONFLICT (ad_id) DO NOTHING;

    -- Calculate deltas based on state transitions
    IF TG_OP = 'INSERT' THEN
        v_like_delta := CASE WHEN NEW.is_liked = true THEN 1 ELSE 0 END;
        v_save_delta := CASE WHEN NEW.is_saved = true THEN 1 ELSE 0 END;
        v_share_delta := CASE WHEN NEW.is_shared = true THEN 1 ELSE 0 END;
    ELSIF TG_OP = 'UPDATE' THEN
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
        v_like_delta := CASE WHEN OLD.is_liked = true THEN -1 ELSE 0 END;
        v_save_delta := CASE WHEN OLD.is_saved = true THEN -1 ELSE 0 END;
        v_share_delta := CASE WHEN OLD.is_shared = true THEN -1 ELSE 0 END;
    END IF;

    -- Get current values and apply deltas
    SELECT
        view_count,
        GREATEST(0, like_count + v_like_delta),
        GREATEST(0, save_count + v_save_delta),
        GREATEST(0, share_count + v_share_delta),
        COALESCE(distinct_reason_sessions, 0)
    INTO v_view_count, v_new_like_count, v_new_save_count, v_new_share_count, v_distinct_sessions
    FROM ad_feedback_agg WHERE ad_id = v_ad_id;

    -- Get reason diversity
    SELECT COUNT(DISTINCT reason) INTO v_unique_reason_types
    FROM ad_like_reasons WHERE ad_id = v_ad_id;

    -- Compute scores
    v_ai_score := fn_compute_ai_score(v_ad_id);
    v_user_score := fn_compute_user_score(
        COALESCE(v_view_count, 0),
        v_new_like_count,
        v_new_save_count,
        v_new_share_count,
        v_distinct_sessions,
        COALESCE(v_unique_reason_types, 0)
    );
    v_confidence_weight := fn_compute_confidence_weight(
        v_distinct_sessions,
        v_new_like_count,
        v_new_save_count
    );
    v_final_score := ROUND(
        v_ai_score * (1 - v_confidence_weight) + v_user_score * v_confidence_weight,
        2
    );

    -- Apply updates
    UPDATE ad_feedback_agg
    SET
        like_count = v_new_like_count,
        save_count = v_new_save_count,
        share_count = v_new_share_count,
        last_interaction_at = now(),
        updated_at = now(),
        engagement_score = LEAST(100,
            CASE WHEN COALESCE(v_view_count, 0) >= 10 THEN
                (v_new_like_count * 3.0 + v_new_save_count * 5.0 + v_new_share_count * 2.0)
                / GREATEST(v_view_count, 1) * 100
            ELSE 0 END
        ),
        ai_score = v_ai_score,
        user_score = v_user_score,
        confidence_weight = v_confidence_weight,
        final_score = v_final_score,
        blended_score = v_final_score
    WHERE ad_id = v_ad_id;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 8. INDEX FOR FINAL SCORE RANKING
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_ad_feedback_agg_final_score
    ON ad_feedback_agg(final_score DESC)
    WHERE final_score > 0;

-- -----------------------------------------------------------------------------
-- 9. UPDATE VIEW: Include new score components
-- -----------------------------------------------------------------------------
-- Drop first to allow column changes (CREATE OR REPLACE can't rename columns)
DROP VIEW IF EXISTS v_ad_with_editorial;

CREATE OR REPLACE VIEW v_ad_with_editorial AS
SELECT
    a.id,
    a.external_id,
    e.brand_slug,
    e.slug,
    COALESCE(e.override_brand_name, a.brand_name) as brand_name,
    COALESCE(e.override_year, a.year) as year,
    COALESCE(e.override_product_category, a.product_category) as product_category,
    e.headline,
    COALESCE(e.editorial_summary, a.one_line_summary) as summary,
    e.curated_tags,
    e.is_featured,
    a.product_name,
    a.one_line_summary as extracted_summary,
    a.story_summary,
    a.duration_seconds,
    a.format_type,
    a.hero_analysis,
    a.impact_scores,
    -- Feedback counts
    COALESCE(f.view_count, 0) as view_count,
    COALESCE(f.like_count, 0) as like_count,
    COALESCE(f.save_count, 0) as save_count,
    -- Score components (v2)
    COALESCE(f.ai_score, 50) as ai_score,
    COALESCE(f.user_score, 0) as user_score,
    COALESCE(f.confidence_weight, 0) as confidence_weight,
    COALESCE(f.final_score, 50) as final_score,
    -- Anti-gaming: distinct sessions
    COALESCE(f.distinct_reason_sessions, 0) as distinct_reason_sessions,
    -- Reason counts (only if threshold met)
    CASE
        WHEN COALESCE(f.distinct_reason_sessions, 0) >= 10
        THEN f.reason_counts
        ELSE '{}'::jsonb
    END as reason_counts,
    f.tag_counts as user_tag_counts,
    -- Ranking boost flag
    (COALESCE(f.like_count, 0) >= 5 OR COALESCE(f.save_count, 0) >= 3) as has_ranking_boost,
    (COALESCE(f.distinct_reason_sessions, 0) >= 10) as has_reason_boost,
    -- Legacy compat
    COALESCE(f.engagement_score, 0) as engagement_score,
    COALESCE(f.blended_score, 50) as blended_score,
    -- Timestamps
    a.created_at,
    a.updated_at,
    e.original_publish_date
FROM ads a
LEFT JOIN ad_editorial e ON e.ad_id = a.id AND e.is_hidden = false
LEFT JOIN ad_feedback_agg f ON f.ad_id = a.id;

-- -----------------------------------------------------------------------------
-- 10. BACKFILL EXISTING RECORDS WITH AI SCORES
-- -----------------------------------------------------------------------------
-- Run this once after migration to populate ai_score for existing ads
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN SELECT ad_id FROM ad_feedback_agg LOOP
        UPDATE ad_feedback_agg
        SET ai_score = fn_compute_ai_score(r.ad_id)
        WHERE ad_id = r.ad_id AND (ai_score IS NULL OR ai_score = 0);
    END LOOP;
    RAISE NOTICE 'Backfilled AI scores for existing feedback records';
END $$;

-- -----------------------------------------------------------------------------
-- COMMENTS: Scoring Formula Documentation
-- -----------------------------------------------------------------------------
--
-- FINAL SCORE FORMULA:
--   final_score = ai_score * (1 - confidence_weight) + user_score * confidence_weight
--
-- WHERE:
--   ai_score (0-100): Average of impact_scores fields from AI extraction
--     - Fields: pulse, echo, hook_power, brand_integration, emotional_resonance, clarity, distinctiveness
--     - Default: 50 if no AI analysis available
--
--   user_score (0-100): Engagement metrics + reason signals
--     - Base engagement: (likes*3 + saves*5 + shares*2) / views * 100 (max 70)
--     - Reason bonus: unique_types * 2 + distinct_sessions * 0.5 (max 30)
--
--   confidence_weight (0.0-0.6): Linear ramp based on engagement volume
--     - Formula: min(0.6, total_signals / 50 * 0.6)
--     - total_signals = distinct_reason_sessions + like_count + save_count
--     - At 0 engagement: weight = 0 (AI score 100%)
--     - At 50+ signals: weight = 0.6 (AI score 40%, user score 60%)
--
-- ANTI-GAMING:
--   - reason_counts uses COUNT(DISTINCT session_id) per reason
--   - distinct_reason_sessions counts unique sessions, not submissions
--   - Public display threshold: 10 distinct sessions before reason_counts shown
--
-- -----------------------------------------------------------------------------
