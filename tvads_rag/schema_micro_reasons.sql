-- =============================================================================
-- TellyAds Micro-Reasons Schema Migration
-- Version: 1.0.0
-- Date: 2025-12-04
--
-- This migration adds:
--   1. ad_like_reasons - User-selected reasons for liking/saving ads
--   2. reason_counts JSONB column on ad_feedback_agg
--   3. Trigger for automatic reason count aggregation
--   4. Blended ranking score formula (engagement + reason quality)
--
-- Predefined reasons:
--   - funny, clever_idea, emotional, great_twist, beautiful_visually
--   - memorable_music, relatable, effective_message, nostalgic, surprising
--
-- Privacy notes:
--   - Same session_id approach (random UUID in localStorage)
--   - No PII, no IP addresses
--   - Lightweight writes (single table insert)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. MICRO-REASONS TABLE (Why did you like/save this?)
-- -----------------------------------------------------------------------------
-- Users can select multiple predefined reasons after liking/saving an ad.
-- Each reason is stored as a separate row for clean aggregation.
CREATE TABLE IF NOT EXISTS ad_like_reasons (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id uuid NOT NULL REFERENCES ads(id) ON DELETE CASCADE,
    session_id text NOT NULL,           -- Same anon ID from localStorage

    -- Reason enum (normalized)
    reason text NOT NULL CHECK (reason IN (
        'funny',
        'clever_idea',
        'emotional',
        'great_twist',
        'beautiful_visually',
        'memorable_music',
        'relatable',
        'effective_message',
        'nostalgic',
        'surprising'
    )),

    -- Optional: was this from a like or save action?
    reaction_type text DEFAULT 'like' CHECK (reaction_type IN ('like', 'save')),

    created_at timestamptz DEFAULT now()
);

-- One reason per user per ad per reason (no duplicates)
CREATE UNIQUE INDEX IF NOT EXISTS idx_ad_like_reasons_unique
    ON ad_like_reasons(ad_id, session_id, reason);

-- Fast lookup by ad for aggregation
CREATE INDEX IF NOT EXISTS idx_ad_like_reasons_ad_id
    ON ad_like_reasons(ad_id);

-- Fast lookup by session for "my reasons" feature
CREATE INDEX IF NOT EXISTS idx_ad_like_reasons_session
    ON ad_like_reasons(session_id);

-- -----------------------------------------------------------------------------
-- 2. ADD reason_counts TO ad_feedback_agg
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ad_feedback_agg' AND column_name = 'reason_counts'
    ) THEN
        ALTER TABLE ad_feedback_agg ADD COLUMN reason_counts jsonb DEFAULT '{}'::jsonb;
    END IF;

    -- Also add reason_total for quick filtering
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ad_feedback_agg' AND column_name = 'reason_total'
    ) THEN
        ALTER TABLE ad_feedback_agg ADD COLUMN reason_total integer DEFAULT 0;
    END IF;

    -- Add blended_score for enhanced ranking
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ad_feedback_agg' AND column_name = 'blended_score'
    ) THEN
        ALTER TABLE ad_feedback_agg ADD COLUMN blended_score numeric(5,2) DEFAULT 0;
    END IF;
END;
$$;

-- -----------------------------------------------------------------------------
-- 3. TRIGGER: Update reason counts on change
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_update_reason_counts()
RETURNS TRIGGER AS $$
DECLARE
    v_ad_id uuid;
    v_reason_counts jsonb;
    v_reason_total integer;
BEGIN
    v_ad_id := COALESCE(NEW.ad_id, OLD.ad_id);

    -- Ensure agg row exists
    INSERT INTO ad_feedback_agg (ad_id)
    VALUES (v_ad_id)
    ON CONFLICT (ad_id) DO NOTHING;

    -- Recalculate reason counts for this ad
    SELECT
        COALESCE(jsonb_object_agg(reason, cnt), '{}'::jsonb),
        COALESCE(SUM(cnt), 0)::integer
    INTO v_reason_counts, v_reason_total
    FROM (
        SELECT reason, COUNT(*) as cnt
        FROM ad_like_reasons
        WHERE ad_id = v_ad_id
        GROUP BY reason
    ) t;

    -- Update aggregate with reason counts and recalculate blended score
    UPDATE ad_feedback_agg
    SET
        reason_counts = v_reason_counts,
        reason_total = v_reason_total,
        -- Blended score formula:
        -- Base: engagement_score (0-100)
        -- Reason bonus: +0.5 per unique reason type (max +5 for 10 reasons)
        -- Reason volume bonus: +0.1 per reason submission (capped at +10)
        -- Final: capped at 100
        blended_score = LEAST(100,
            engagement_score +
            (jsonb_array_length(jsonb_path_query_array(v_reason_counts, '$.keyvalue().key')) * 0.5) +
            LEAST(10, v_reason_total * 0.1)
        ),
        updated_at = now()
    WHERE ad_id = v_ad_id;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Create trigger
DROP TRIGGER IF EXISTS trg_reason_counts ON ad_like_reasons;
CREATE TRIGGER trg_reason_counts
    AFTER INSERT OR DELETE ON ad_like_reasons
    FOR EACH ROW EXECUTE FUNCTION fn_update_reason_counts();

-- -----------------------------------------------------------------------------
-- 4. HELPER FUNCTION: Add reasons for an ad
-- -----------------------------------------------------------------------------
-- Accepts array of reasons, validates, rate-limits, inserts
CREATE OR REPLACE FUNCTION fn_add_reasons(
    p_ad_id uuid,
    p_session_id text,
    p_reasons text[],
    p_reaction_type text DEFAULT 'like'
)
RETURNS integer AS $$
DECLARE
    v_inserted integer := 0;
    v_reason text;
BEGIN
    -- Validate reaction_type
    IF p_reaction_type NOT IN ('like', 'save') THEN
        RAISE EXCEPTION 'Invalid reaction_type';
    END IF;

    -- Rate limit: max 20 reason submissions per hour
    PERFORM 1 FROM ad_rate_limits
    WHERE session_id = p_session_id
      AND action_type = 'reason'
      AND window_start = date_trunc('hour', now())
      AND action_count >= 20;

    IF FOUND THEN
        RAISE EXCEPTION 'Rate limit exceeded';
    END IF;

    -- Record rate limit
    INSERT INTO ad_rate_limits (session_id, action_type, window_start, action_count)
    VALUES (p_session_id, 'reason', date_trunc('hour', now()), array_length(p_reasons, 1))
    ON CONFLICT (session_id, action_type, window_start)
    DO UPDATE SET action_count = ad_rate_limits.action_count + array_length(p_reasons, 1);

    -- Insert each valid reason
    FOREACH v_reason IN ARRAY p_reasons LOOP
        -- Skip invalid reasons (constraint will catch, but let's be explicit)
        IF v_reason NOT IN (
            'funny', 'clever_idea', 'emotional', 'great_twist', 'beautiful_visually',
            'memorable_music', 'relatable', 'effective_message', 'nostalgic', 'surprising'
        ) THEN
            CONTINUE;
        END IF;

        INSERT INTO ad_like_reasons (ad_id, session_id, reason, reaction_type)
        VALUES (p_ad_id, p_session_id, v_reason, p_reaction_type)
        ON CONFLICT (ad_id, session_id, reason) DO NOTHING;

        IF FOUND THEN
            v_inserted := v_inserted + 1;
        END IF;
    END LOOP;

    RETURN v_inserted;
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 5. UPDATE BLENDED SCORE ON ENGAGEMENT CHANGES
-- -----------------------------------------------------------------------------
-- Modify the existing reaction trigger to also update blended_score
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

    -- Apply deltas and update engagement + blended scores
    UPDATE ad_feedback_agg
    SET
        like_count = GREATEST(0, like_count + v_like_delta),
        save_count = GREATEST(0, save_count + v_save_delta),
        share_count = GREATEST(0, share_count + v_share_delta),
        last_interaction_at = now(),
        updated_at = now(),
        -- Update engagement score
        engagement_score = LEAST(100,
            CASE WHEN view_count >= 10 THEN
                (GREATEST(0, like_count + v_like_delta) * 3.0 +
                 GREATEST(0, save_count + v_save_delta) * 5.0 +
                 GREATEST(0, share_count + v_share_delta) * 2.0) / GREATEST(view_count, 1) * 100
            ELSE 0 END
        ),
        -- Update blended score (engagement + reason bonuses)
        blended_score = LEAST(100,
            CASE WHEN view_count >= 10 THEN
                (GREATEST(0, like_count + v_like_delta) * 3.0 +
                 GREATEST(0, save_count + v_save_delta) * 5.0 +
                 GREATEST(0, share_count + v_share_delta) * 2.0) / GREATEST(view_count, 1) * 100
            ELSE 0 END
            + (jsonb_array_length(COALESCE(jsonb_path_query_array(reason_counts, '$.keyvalue().key'), '[]'::jsonb)) * 0.5)
            + LEAST(10, COALESCE(reason_total, 0) * 0.1)
        )
    WHERE ad_id = v_ad_id;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 6. INDEX FOR BLENDED SCORE RANKING
-- -----------------------------------------------------------------------------
-- Query ads by blended_score for enhanced ranking
CREATE INDEX IF NOT EXISTS idx_ad_feedback_agg_blended
    ON ad_feedback_agg(blended_score DESC)
    WHERE blended_score > 0;

-- -----------------------------------------------------------------------------
-- 7. UPDATE VIEW: Include reason_counts
-- -----------------------------------------------------------------------------
-- Drop first to allow column changes (CREATE OR REPLACE can't rename columns)
DROP VIEW IF EXISTS v_ad_with_editorial;

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
    -- Feedback (with threshold for ranking)
    COALESCE(f.view_count, 0) as view_count,
    COALESCE(f.like_count, 0) as like_count,
    COALESCE(f.save_count, 0) as save_count,
    COALESCE(f.engagement_score, 0) as engagement_score,
    COALESCE(f.blended_score, 0) as blended_score,
    f.tag_counts as user_tag_counts,
    -- NEW: reason counts for UI
    COALESCE(f.reason_counts, '{}'::jsonb) as reason_counts,
    COALESCE(f.reason_total, 0) as reason_total,
    -- Ranking boost flag (threshold-based)
    (COALESCE(f.like_count, 0) >= 5 OR COALESCE(f.save_count, 0) >= 3) as has_ranking_boost,
    -- Enhanced boost with reasons
    (COALESCE(f.reason_total, 0) >= 3) as has_reason_boost,
    -- Timestamps
    a.created_at,
    a.updated_at,
    e.original_publish_date
FROM ads a
LEFT JOIN ad_editorial e ON e.ad_id = a.id AND e.is_hidden = false
LEFT JOIN ad_feedback_agg f ON f.ad_id = a.id;

-- -----------------------------------------------------------------------------
-- 8. CONSTANTS: Reason Labels for UI
-- -----------------------------------------------------------------------------
-- Exposed as a simple function for frontend reference
CREATE OR REPLACE FUNCTION fn_get_reason_labels()
RETURNS TABLE (reason text, label text, emoji text) AS $$
    SELECT * FROM (VALUES
        ('funny', 'Funny', '😂'),
        ('clever_idea', 'Clever idea', '💡'),
        ('emotional', 'Emotional', '❤️'),
        ('great_twist', 'Great twist/ending', '🎬'),
        ('beautiful_visually', 'Beautiful visually', '✨'),
        ('memorable_music', 'Memorable music', '🎵'),
        ('relatable', 'Relatable', '🤝'),
        ('effective_message', 'Effective message', '📣'),
        ('nostalgic', 'Nostalgic', '📼'),
        ('surprising', 'Surprising', '😮')
    ) AS t(reason, label, emoji);
$$ LANGUAGE sql STABLE;

-- -----------------------------------------------------------------------------
-- COMMENTS: Blended Score Formula
-- -----------------------------------------------------------------------------
-- blended_score = engagement_score + reason_diversity_bonus + reason_volume_bonus
--
-- Where:
--   - engagement_score: (likes*3 + saves*5 + shares*2) / views * 100 (capped at 100)
--   - reason_diversity_bonus: unique_reason_types * 0.5 (max +5 for all 10 types)
--   - reason_volume_bonus: min(reason_total * 0.1, 10) (max +10)
--   - Final blended_score capped at 100
--
-- This rewards ads that:
--   1. Have genuine engagement (not just views)
--   2. Resonate across multiple dimensions (diversity)
--   3. Have consistent reason-giving behavior (volume)
-- -----------------------------------------------------------------------------
