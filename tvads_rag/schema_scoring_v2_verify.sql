-- =============================================================================
-- QA Validation Queries for Scoring V2 Schema
-- Run these after applying schema_scoring_v2.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. VERIFY NEW COLUMNS EXIST
-- -----------------------------------------------------------------------------
SELECT
    expected.column_name,
    CASE WHEN c.column_name IS NOT NULL THEN '✓ EXISTS' ELSE '✗ MISSING' END as status
FROM (
    VALUES
        ('ai_score'),
        ('user_score'),
        ('final_score'),
        ('distinct_reason_sessions'),
        ('confidence_weight')
) expected(column_name)
LEFT JOIN information_schema.columns c
    ON c.column_name = expected.column_name
    AND c.table_name = 'ad_feedback_agg'
    AND c.table_schema = 'public';

-- -----------------------------------------------------------------------------
-- 2. VERIFY FUNCTIONS EXIST
-- -----------------------------------------------------------------------------
SELECT
    expected.routine_name,
    CASE WHEN r.routine_name IS NOT NULL THEN '✓ EXISTS' ELSE '✗ MISSING' END as status
FROM (
    VALUES
        ('fn_scoring_constants'),
        ('fn_compute_ai_score'),
        ('fn_compute_user_score'),
        ('fn_compute_confidence_weight')
) expected(routine_name)
LEFT JOIN information_schema.routines r
    ON r.routine_name = expected.routine_name
    AND r.routine_schema = 'public';

-- -----------------------------------------------------------------------------
-- 3. VERIFY SCORING CONSTANTS
-- -----------------------------------------------------------------------------
SELECT * FROM fn_scoring_constants();

-- -----------------------------------------------------------------------------
-- 4. TEST: AI SCORE COMPUTATION
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_test_ad_id uuid;
    v_ai_score numeric;
BEGIN
    -- Get an ad with impact_scores
    SELECT id INTO v_test_ad_id
    FROM ads
    WHERE impact_scores IS NOT NULL
    LIMIT 1;

    IF v_test_ad_id IS NOT NULL THEN
        v_ai_score := fn_compute_ai_score(v_test_ad_id);

        IF v_ai_score >= 0 AND v_ai_score <= 100 THEN
            RAISE NOTICE 'PASS: AI score computed: % (in range 0-100)', v_ai_score;
        ELSE
            RAISE NOTICE 'FAIL: AI score out of range: %', v_ai_score;
        END IF;
    ELSE
        -- Test default for ad without impact_scores
        SELECT id INTO v_test_ad_id FROM ads LIMIT 1;
        v_ai_score := fn_compute_ai_score(v_test_ad_id);

        IF v_ai_score = 50 THEN
            RAISE NOTICE 'PASS: AI score defaults to 50 for ad without impact_scores';
        ELSE
            RAISE NOTICE 'WARN: AI score for ad without impact_scores: %', v_ai_score;
        END IF;
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 5. TEST: USER SCORE COMPUTATION
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_user_score numeric;
BEGIN
    -- Test with realistic values
    v_user_score := fn_compute_user_score(
        100,   -- views
        10,    -- likes
        5,     -- saves
        2,     -- shares
        5,     -- distinct_reason_sessions
        3      -- unique_reason_types
    );

    IF v_user_score >= 0 AND v_user_score <= 100 THEN
        RAISE NOTICE 'PASS: User score computed: % (in range 0-100)', v_user_score;
    ELSE
        RAISE NOTICE 'FAIL: User score out of range: %', v_user_score;
    END IF;

    -- Test with low views (should be 0 engagement)
    v_user_score := fn_compute_user_score(5, 10, 5, 2, 5, 3);
    IF v_user_score < 30 THEN  -- Only reason bonus, no engagement
        RAISE NOTICE 'PASS: User score with low views (reason bonus only): %', v_user_score;
    ELSE
        RAISE NOTICE 'FAIL: User score should be low with insufficient views: %', v_user_score;
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 6. TEST: CONFIDENCE WEIGHT COMPUTATION
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_weight numeric;
BEGIN
    -- Low engagement: should be near 0
    v_weight := fn_compute_confidence_weight(0, 0, 0);
    IF v_weight = 0 THEN
        RAISE NOTICE 'PASS: Confidence weight is 0 with no engagement';
    ELSE
        RAISE NOTICE 'FAIL: Expected 0, got %', v_weight;
    END IF;

    -- High engagement: should be capped at 0.6
    v_weight := fn_compute_confidence_weight(50, 50, 50);
    IF v_weight = 0.6 THEN
        RAISE NOTICE 'PASS: Confidence weight caps at 0.6 with high engagement';
    ELSE
        RAISE NOTICE 'FAIL: Expected 0.6, got %', v_weight;
    END IF;

    -- Mid engagement: should be between 0 and 0.6
    v_weight := fn_compute_confidence_weight(10, 5, 5);
    IF v_weight > 0 AND v_weight < 0.6 THEN
        RAISE NOTICE 'PASS: Confidence weight scales with engagement: %', v_weight;
    ELSE
        RAISE NOTICE 'FAIL: Unexpected weight: %', v_weight;
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 7. TEST: ANTI-GAMING - Repeated submits from same session
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_test_ad_id uuid;
    v_initial_sessions integer;
    v_after_sessions integer;
BEGIN
    SELECT id INTO v_test_ad_id FROM ads LIMIT 1;

    IF v_test_ad_id IS NOT NULL THEN
        -- Ensure agg row exists
        INSERT INTO ad_feedback_agg (ad_id)
        VALUES (v_test_ad_id)
        ON CONFLICT (ad_id) DO NOTHING;

        -- Get initial count
        SELECT COALESCE(distinct_reason_sessions, 0) INTO v_initial_sessions
        FROM ad_feedback_agg WHERE ad_id = v_test_ad_id;

        -- Add reasons from one session
        INSERT INTO ad_like_reasons (ad_id, session_id, reason)
        VALUES
            (v_test_ad_id, 'anti-gaming-test-session', 'funny'),
            (v_test_ad_id, 'anti-gaming-test-session', 'emotional'),
            (v_test_ad_id, 'anti-gaming-test-session', 'clever_idea');

        -- Check distinct sessions (should be +1, not +3)
        SELECT distinct_reason_sessions INTO v_after_sessions
        FROM ad_feedback_agg WHERE ad_id = v_test_ad_id;

        IF v_after_sessions = v_initial_sessions + 1 THEN
            RAISE NOTICE 'PASS: Distinct sessions incremented by 1 (not 3 rows)';
        ELSE
            RAISE NOTICE 'FAIL: Expected %, got %', v_initial_sessions + 1, v_after_sessions;
        END IF;

        -- Try duplicate reason (should not insert due to UNIQUE)
        BEGIN
            INSERT INTO ad_like_reasons (ad_id, session_id, reason)
            VALUES (v_test_ad_id, 'anti-gaming-test-session', 'funny');
            RAISE NOTICE 'FAIL: Duplicate reason was inserted';
        EXCEPTION WHEN unique_violation THEN
            RAISE NOTICE 'PASS: Duplicate reason correctly rejected';
        END;

        -- Cleanup
        DELETE FROM ad_like_reasons WHERE session_id = 'anti-gaming-test-session';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 8. TEST: Reason counts use distinct sessions
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_test_ad_id uuid;
    v_reason_counts jsonb;
BEGIN
    SELECT id INTO v_test_ad_id FROM ads LIMIT 1;

    IF v_test_ad_id IS NOT NULL THEN
        -- Add reasons from multiple sessions
        INSERT INTO ad_like_reasons (ad_id, session_id, reason)
        VALUES
            (v_test_ad_id, 'distinct-test-1', 'funny'),
            (v_test_ad_id, 'distinct-test-2', 'funny'),
            (v_test_ad_id, 'distinct-test-3', 'funny'),
            (v_test_ad_id, 'distinct-test-1', 'emotional');

        -- Check reason_counts uses distinct sessions
        SELECT reason_counts INTO v_reason_counts
        FROM ad_feedback_agg WHERE ad_id = v_test_ad_id;

        IF (v_reason_counts->>'funny')::int = 3 THEN
            RAISE NOTICE 'PASS: reason_counts shows distinct sessions (funny=3)';
        ELSE
            RAISE NOTICE 'FAIL: Expected funny=3, got %', v_reason_counts->>'funny';
        END IF;

        IF (v_reason_counts->>'emotional')::int = 1 THEN
            RAISE NOTICE 'PASS: reason_counts shows distinct sessions (emotional=1)';
        ELSE
            RAISE NOTICE 'FAIL: Expected emotional=1, got %', v_reason_counts->>'emotional';
        END IF;

        -- Cleanup
        DELETE FROM ad_like_reasons WHERE session_id LIKE 'distinct-test-%';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 9. TEST: Display threshold for reason_counts
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_test_ad_id uuid;
    v_distinct_sessions integer;
BEGIN
    SELECT id INTO v_test_ad_id FROM ads LIMIT 1;

    IF v_test_ad_id IS NOT NULL THEN
        -- Add reasons from only 5 sessions (below threshold of 10)
        FOR i IN 1..5 LOOP
            INSERT INTO ad_like_reasons (ad_id, session_id, reason)
            VALUES (v_test_ad_id, 'threshold-test-' || i, 'funny');
        END LOOP;

        SELECT distinct_reason_sessions INTO v_distinct_sessions
        FROM ad_feedback_agg WHERE ad_id = v_test_ad_id;

        IF v_distinct_sessions < 10 THEN
            RAISE NOTICE 'PASS: With % sessions, threshold not met (should hide reason_counts)', v_distinct_sessions;
        ELSE
            RAISE NOTICE 'WARN: More sessions than expected: %', v_distinct_sessions;
        END IF;

        -- Cleanup
        DELETE FROM ad_like_reasons WHERE session_id LIKE 'threshold-test-%';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 10. TEST: Final score behavior at different engagement levels
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_test_ad_id uuid;
    v_ai_score numeric;
    v_final_score_low numeric;
    v_final_score_high numeric;
BEGIN
    SELECT id INTO v_test_ad_id FROM ads LIMIT 1;

    IF v_test_ad_id IS NOT NULL THEN
        v_ai_score := fn_compute_ai_score(v_test_ad_id);

        -- Set up low engagement scenario
        UPDATE ad_feedback_agg
        SET view_count = 5, like_count = 0, save_count = 0, distinct_reason_sessions = 0
        WHERE ad_id = v_test_ad_id;

        -- Trigger score recalculation
        INSERT INTO ad_like_reasons (ad_id, session_id, reason)
        VALUES (v_test_ad_id, 'score-test-low', 'funny');
        DELETE FROM ad_like_reasons WHERE session_id = 'score-test-low';

        SELECT final_score INTO v_final_score_low
        FROM ad_feedback_agg WHERE ad_id = v_test_ad_id;

        -- At low engagement, final_score should be close to ai_score
        IF ABS(v_final_score_low - v_ai_score) < 10 THEN
            RAISE NOTICE 'PASS: Low engagement: final_score (%) near ai_score (%)', v_final_score_low, v_ai_score;
        ELSE
            RAISE NOTICE 'WARN: Low engagement: final_score (%) differs from ai_score (%)', v_final_score_low, v_ai_score;
        END IF;

        -- Set up high engagement scenario
        UPDATE ad_feedback_agg
        SET view_count = 100, like_count = 30, save_count = 20
        WHERE ad_id = v_test_ad_id;

        -- Add reasons from many sessions
        FOR i IN 1..30 LOOP
            INSERT INTO ad_like_reasons (ad_id, session_id, reason)
            VALUES (v_test_ad_id, 'score-test-high-' || i, 'funny');
        END LOOP;

        SELECT final_score INTO v_final_score_high
        FROM ad_feedback_agg WHERE ad_id = v_test_ad_id;

        -- At high engagement, user_score should have meaningful influence
        RAISE NOTICE 'High engagement: final_score = %, ai_score = %', v_final_score_high, v_ai_score;

        IF v_final_score_high != v_final_score_low THEN
            RAISE NOTICE 'PASS: Engagement changes final_score (low: %, high: %)', v_final_score_low, v_final_score_high;
        ELSE
            RAISE NOTICE 'WARN: Final scores same despite engagement difference';
        END IF;

        -- Cleanup
        DELETE FROM ad_like_reasons WHERE session_id LIKE 'score-test-%';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 11. DATA CONSISTENCY CHECK
-- -----------------------------------------------------------------------------
-- Verify distinct_reason_sessions matches actual distinct sessions
SELECT
    f.ad_id,
    f.distinct_reason_sessions as stored_value,
    (SELECT COUNT(DISTINCT session_id) FROM ad_like_reasons WHERE ad_id = f.ad_id) as actual_value,
    CASE
        WHEN f.distinct_reason_sessions = (SELECT COUNT(DISTINCT session_id) FROM ad_like_reasons WHERE ad_id = f.ad_id)
        THEN 'CONSISTENT'
        ELSE 'DRIFT'
    END as status
FROM ad_feedback_agg f
WHERE f.distinct_reason_sessions > 0
LIMIT 20;

-- -----------------------------------------------------------------------------
-- 12. SAMPLE QUERIES FOR PRODUCTION
-- -----------------------------------------------------------------------------

-- Ads ranked by final_score (AI + User blended)
SELECT
    a.external_id,
    a.brand_name,
    f.ai_score,
    f.user_score,
    f.confidence_weight,
    f.final_score,
    f.distinct_reason_sessions,
    CASE WHEN f.distinct_reason_sessions >= 10 THEN f.reason_counts ELSE '{}'::jsonb END as public_reasons
FROM ad_feedback_agg f
JOIN ads a ON a.id = f.ad_id
WHERE f.final_score > 0
ORDER BY f.final_score DESC
LIMIT 20;

-- Score composition breakdown
SELECT
    a.external_id,
    f.ai_score,
    f.user_score,
    f.confidence_weight,
    f.final_score,
    -- Formula verification
    ROUND(f.ai_score * (1 - f.confidence_weight) + f.user_score * f.confidence_weight, 2) as calculated_score,
    CASE
        WHEN ABS(f.final_score - (f.ai_score * (1 - f.confidence_weight) + f.user_score * f.confidence_weight)) < 0.01
        THEN 'CORRECT'
        ELSE 'MISMATCH'
    END as formula_check
FROM ad_feedback_agg f
JOIN ads a ON a.id = f.ad_id
WHERE f.final_score > 0
LIMIT 10;
