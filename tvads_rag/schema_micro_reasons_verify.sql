-- =============================================================================
-- QA Validation Queries for Micro-Reasons Schema
-- Run these after applying schema_micro_reasons.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. VERIFY TABLE EXISTS
-- -----------------------------------------------------------------------------
SELECT
    expected.table_name,
    CASE WHEN t.table_name IS NOT NULL THEN '✓ EXISTS' ELSE '✗ MISSING' END as status
FROM (
    VALUES ('ad_like_reasons')
) expected(table_name)
LEFT JOIN information_schema.tables t
    ON t.table_name = expected.table_name
    AND t.table_schema = 'public';

-- -----------------------------------------------------------------------------
-- 2. VERIFY NEW COLUMNS ON ad_feedback_agg
-- -----------------------------------------------------------------------------
SELECT
    expected.column_name,
    CASE WHEN c.column_name IS NOT NULL THEN '✓ EXISTS' ELSE '✗ MISSING' END as status
FROM (
    VALUES ('reason_counts'), ('reason_total'), ('blended_score')
) expected(column_name)
LEFT JOIN information_schema.columns c
    ON c.column_name = expected.column_name
    AND c.table_name = 'ad_feedback_agg'
    AND c.table_schema = 'public';

-- -----------------------------------------------------------------------------
-- 3. VERIFY INDEXES
-- -----------------------------------------------------------------------------
SELECT
    expected.indexname,
    CASE WHEN i.indexname IS NOT NULL THEN '✓ EXISTS' ELSE '✗ MISSING' END as status
FROM (
    VALUES
        ('idx_ad_like_reasons_unique'),
        ('idx_ad_like_reasons_ad_id'),
        ('idx_ad_like_reasons_session'),
        ('idx_ad_feedback_agg_blended')
) expected(indexname)
LEFT JOIN pg_indexes i ON i.indexname = expected.indexname;

-- -----------------------------------------------------------------------------
-- 4. VERIFY FUNCTIONS
-- -----------------------------------------------------------------------------
SELECT
    expected.routine_name,
    CASE WHEN r.routine_name IS NOT NULL THEN '✓ EXISTS' ELSE '✗ MISSING' END as status
FROM (
    VALUES
        ('fn_add_reasons'),
        ('fn_update_reason_counts'),
        ('fn_get_reason_labels')
) expected(routine_name)
LEFT JOIN information_schema.routines r
    ON r.routine_name = expected.routine_name
    AND r.routine_schema = 'public';

-- -----------------------------------------------------------------------------
-- 5. VERIFY TRIGGER
-- -----------------------------------------------------------------------------
SELECT
    expected.tgname as trigger_name,
    CASE WHEN t.tgname IS NOT NULL THEN '✓ EXISTS' ELSE '✗ MISSING' END as status
FROM (
    VALUES ('trg_reason_counts')
) expected(tgname)
LEFT JOIN pg_trigger t ON t.tgname = expected.tgname;

-- -----------------------------------------------------------------------------
-- 6. TEST REASON SUBMISSION (Dry run)
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_test_ad_id uuid;
    v_inserted integer;
BEGIN
    -- Get a test ad
    SELECT id INTO v_test_ad_id FROM ads LIMIT 1;

    IF v_test_ad_id IS NOT NULL THEN
        -- Test adding reasons
        v_inserted := fn_add_reasons(
            v_test_ad_id,
            'test-session-reason-qa',
            ARRAY['funny', 'clever_idea', 'emotional'],
            'like'
        );

        IF v_inserted = 3 THEN
            RAISE NOTICE 'PASS: Inserted % reasons', v_inserted;
        ELSE
            RAISE NOTICE 'WARN: Expected 3 insertions, got %', v_inserted;
        END IF;

        -- Verify they exist
        IF EXISTS (
            SELECT 1 FROM ad_like_reasons
            WHERE ad_id = v_test_ad_id AND session_id = 'test-session-reason-qa'
            HAVING COUNT(*) = 3
        ) THEN
            RAISE NOTICE 'PASS: Reasons stored correctly';
        ELSE
            RAISE NOTICE 'FAIL: Reasons not stored correctly';
        END IF;

        -- Test duplicate rejection (should not insert again)
        v_inserted := fn_add_reasons(
            v_test_ad_id,
            'test-session-reason-qa',
            ARRAY['funny'],  -- Already exists
            'like'
        );

        IF v_inserted = 0 THEN
            RAISE NOTICE 'PASS: Duplicate reason correctly rejected';
        ELSE
            RAISE NOTICE 'FAIL: Duplicate reason was inserted';
        END IF;

        -- Cleanup
        DELETE FROM ad_like_reasons WHERE session_id = 'test-session-reason-qa';
        DELETE FROM ad_rate_limits WHERE session_id = 'test-session-reason-qa';
        RAISE NOTICE 'PASS: Reason test completed and cleaned up';
    ELSE
        RAISE NOTICE 'SKIP: No ads found for reason test';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 7. TEST REASON AGGREGATION TRIGGER
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_test_ad_id uuid;
    v_reason_counts jsonb;
    v_reason_total integer;
BEGIN
    SELECT id INTO v_test_ad_id FROM ads LIMIT 1;

    IF v_test_ad_id IS NOT NULL THEN
        -- Ensure agg row exists
        INSERT INTO ad_feedback_agg (ad_id)
        VALUES (v_test_ad_id)
        ON CONFLICT (ad_id) DO NOTHING;

        -- Add test reasons (triggers aggregation)
        INSERT INTO ad_like_reasons (ad_id, session_id, reason)
        VALUES
            (v_test_ad_id, 'agg-test-1', 'funny'),
            (v_test_ad_id, 'agg-test-2', 'funny'),
            (v_test_ad_id, 'agg-test-1', 'emotional');

        -- Check aggregation
        SELECT reason_counts, reason_total
        INTO v_reason_counts, v_reason_total
        FROM ad_feedback_agg WHERE ad_id = v_test_ad_id;

        IF v_reason_counts->>'funny' = '2' AND v_reason_counts->>'emotional' = '1' THEN
            RAISE NOTICE 'PASS: Reason counts aggregated correctly: %', v_reason_counts;
        ELSE
            RAISE NOTICE 'FAIL: Expected {"funny":2,"emotional":1}, got %', v_reason_counts;
        END IF;

        IF v_reason_total = 3 THEN
            RAISE NOTICE 'PASS: Reason total is correct: %', v_reason_total;
        ELSE
            RAISE NOTICE 'FAIL: Expected reason_total=3, got %', v_reason_total;
        END IF;

        -- Cleanup
        DELETE FROM ad_like_reasons WHERE session_id IN ('agg-test-1', 'agg-test-2');
        RAISE NOTICE 'PASS: Aggregation test completed';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 8. TEST BLENDED SCORE CALCULATION
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_test_ad_id uuid;
    v_initial_score numeric;
    v_final_score numeric;
BEGIN
    SELECT id INTO v_test_ad_id FROM ads LIMIT 1;

    IF v_test_ad_id IS NOT NULL THEN
        -- Ensure agg row with some engagement
        INSERT INTO ad_feedback_agg (ad_id, view_count, like_count, engagement_score)
        VALUES (v_test_ad_id, 100, 10, 30)
        ON CONFLICT (ad_id) DO UPDATE SET
            view_count = 100,
            like_count = 10,
            engagement_score = 30;

        SELECT blended_score INTO v_initial_score
        FROM ad_feedback_agg WHERE ad_id = v_test_ad_id;

        -- Add reasons (should boost blended score)
        INSERT INTO ad_like_reasons (ad_id, session_id, reason)
        VALUES
            (v_test_ad_id, 'blend-test-1', 'funny'),
            (v_test_ad_id, 'blend-test-1', 'emotional'),
            (v_test_ad_id, 'blend-test-1', 'clever_idea'),
            (v_test_ad_id, 'blend-test-2', 'funny'),
            (v_test_ad_id, 'blend-test-2', 'nostalgic');

        SELECT blended_score INTO v_final_score
        FROM ad_feedback_agg WHERE ad_id = v_test_ad_id;

        IF v_final_score > v_initial_score THEN
            RAISE NOTICE 'PASS: Blended score increased from % to %', v_initial_score, v_final_score;
        ELSE
            RAISE NOTICE 'FAIL: Blended score did not increase (% -> %)', v_initial_score, v_final_score;
        END IF;

        -- Cleanup
        DELETE FROM ad_like_reasons WHERE session_id IN ('blend-test-1', 'blend-test-2');
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 9. TEST RATE LIMITING
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_test_ad_id uuid;
    i integer;
BEGIN
    SELECT id INTO v_test_ad_id FROM ads LIMIT 1;

    IF v_test_ad_id IS NOT NULL THEN
        -- Try to exceed rate limit (20 reason submissions per hour)
        FOR i IN 1..25 LOOP
            BEGIN
                PERFORM fn_add_reasons(
                    v_test_ad_id,
                    'rate-test-reasons',
                    ARRAY['funny'],
                    'like'
                );
            EXCEPTION WHEN OTHERS THEN
                IF i > 20 THEN
                    RAISE NOTICE 'PASS: Rate limit triggered at iteration %', i;
                ELSE
                    RAISE NOTICE 'FAIL: Rate limit triggered too early at iteration %', i;
                END IF;
                EXIT;
            END;
        END LOOP;

        -- Cleanup
        DELETE FROM ad_like_reasons WHERE session_id = 'rate-test-reasons';
        DELETE FROM ad_rate_limits WHERE session_id = 'rate-test-reasons';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 10. TEST INVALID REASON REJECTION
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_test_ad_id uuid;
    v_inserted integer;
BEGIN
    SELECT id INTO v_test_ad_id FROM ads LIMIT 1;

    IF v_test_ad_id IS NOT NULL THEN
        -- Try to add an invalid reason (should be skipped, not error)
        v_inserted := fn_add_reasons(
            v_test_ad_id,
            'invalid-test',
            ARRAY['invalid_reason', 'funny', 'also_invalid'],
            'like'
        );

        IF v_inserted = 1 THEN
            RAISE NOTICE 'PASS: Only valid reason was inserted (1 of 3)';
        ELSE
            RAISE NOTICE 'FAIL: Expected 1 insertion, got %', v_inserted;
        END IF;

        -- Cleanup
        DELETE FROM ad_like_reasons WHERE session_id = 'invalid-test';
        DELETE FROM ad_rate_limits WHERE session_id = 'invalid-test';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 11. VERIFY REASON LABELS FUNCTION
-- -----------------------------------------------------------------------------
SELECT * FROM fn_get_reason_labels();

-- -----------------------------------------------------------------------------
-- 12. DATA INTEGRITY CHECK
-- -----------------------------------------------------------------------------
-- Orphaned reasons (should be 0)
SELECT COUNT(*) as orphaned_reasons
FROM ad_like_reasons r
LEFT JOIN ads a ON a.id = r.ad_id
WHERE a.id IS NULL;

-- Reason count consistency
SELECT
    f.ad_id,
    f.reason_total as agg_total,
    (SELECT COUNT(*) FROM ad_like_reasons WHERE ad_id = f.ad_id) as actual_total,
    CASE
        WHEN f.reason_total = (SELECT COUNT(*) FROM ad_like_reasons WHERE ad_id = f.ad_id)
        THEN 'CONSISTENT'
        ELSE 'DRIFT DETECTED'
    END as consistency_status
FROM ad_feedback_agg f
WHERE f.reason_total > 0
LIMIT 20;

-- -----------------------------------------------------------------------------
-- 13. SAMPLE QUERIES FOR PRODUCTION USE
-- -----------------------------------------------------------------------------

-- Top reasons across all ads
SELECT
    reason,
    COUNT(*) as total_submissions,
    COUNT(DISTINCT ad_id) as unique_ads
FROM ad_like_reasons
GROUP BY reason
ORDER BY total_submissions DESC;

-- Ads with most reason diversity (good for "highly resonant" ranking)
SELECT
    a.external_id,
    a.brand_name,
    f.reason_total,
    jsonb_array_length(jsonb_path_query_array(f.reason_counts, '$.keyvalue().key')) as unique_reasons,
    f.blended_score
FROM ad_feedback_agg f
JOIN ads a ON a.id = f.ad_id
WHERE f.reason_total > 0
ORDER BY unique_reasons DESC, f.blended_score DESC
LIMIT 20;

-- Ads ranked by blended score (for enhanced search ranking)
SELECT
    a.external_id,
    a.brand_name,
    f.engagement_score,
    f.blended_score,
    f.reason_counts
FROM ad_feedback_agg f
JOIN ads a ON a.id = f.ad_id
WHERE f.blended_score > 0
ORDER BY f.blended_score DESC
LIMIT 20;
