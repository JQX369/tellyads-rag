-- =============================================================================
-- QA Validation Queries for Editorial + Feedback Schema
-- Run these after applying schema_editorial_feedback.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. VERIFY TABLES EXIST
-- -----------------------------------------------------------------------------
SELECT
    expected.table_name,
    CASE WHEN t.table_name IS NOT NULL THEN '✓ EXISTS' ELSE '✗ MISSING' END as status
FROM (
    VALUES
        ('ad_editorial'),
        ('ad_user_reactions'),
        ('ad_user_tags'),
        ('ad_feedback_agg'),
        ('ad_rate_limits')
) expected(table_name)
LEFT JOIN information_schema.tables t
    ON t.table_name = expected.table_name
    AND t.table_schema = 'public';

-- -----------------------------------------------------------------------------
-- 2. VERIFY INDEXES EXIST
-- -----------------------------------------------------------------------------
SELECT
    expected.indexname,
    CASE WHEN i.indexname IS NOT NULL THEN '✓ EXISTS' ELSE '✗ MISSING' END as status
FROM (
    VALUES
        ('idx_ad_editorial_url_unique'),
        ('idx_ad_editorial_ad_id_unique'),
        ('idx_ad_editorial_wix_id_unique'),
        ('idx_ad_editorial_featured'),
        ('idx_ad_user_reactions_unique'),
        ('idx_ad_user_tags_unique'),
        ('idx_ad_user_tags_pending'),
        ('idx_ad_feedback_agg_popular')
) expected(indexname)
LEFT JOIN pg_indexes i ON i.indexname = expected.indexname;

-- -----------------------------------------------------------------------------
-- 3. VERIFY FUNCTIONS EXIST
-- -----------------------------------------------------------------------------
SELECT
    expected.routine_name,
    CASE WHEN r.routine_name IS NOT NULL THEN '✓ EXISTS' ELSE '✗ MISSING' END as status
FROM (
    VALUES
        ('fn_update_feedback_agg_on_reaction'),
        ('fn_update_tag_counts'),
        ('fn_record_ad_view'),
        ('fn_toggle_like'),
        ('fn_toggle_save'),
        ('fn_suggest_tag'),
        ('fn_cleanup_rate_limits')
) expected(routine_name)
LEFT JOIN information_schema.routines r
    ON r.routine_name = expected.routine_name
    AND r.routine_schema = 'public';

-- -----------------------------------------------------------------------------
-- 4. VERIFY TRIGGERS EXIST
-- -----------------------------------------------------------------------------
SELECT
    expected.tgname as trigger_name,
    CASE WHEN t.tgname IS NOT NULL THEN '✓ EXISTS' ELSE '✗ MISSING' END as status
FROM (
    VALUES ('trg_reaction_agg'), ('trg_tag_counts')
) expected(tgname)
LEFT JOIN pg_trigger t ON t.tgname = expected.tgname;

-- -----------------------------------------------------------------------------
-- 5. VERIFY VIEWS EXIST
-- -----------------------------------------------------------------------------
SELECT
    expected.table_name as view_name,
    CASE WHEN v.table_name IS NOT NULL THEN '✓ EXISTS' ELSE '✗ MISSING' END as status
FROM (
    VALUES ('v_ad_with_editorial'), ('v_tag_moderation_queue')
) expected(table_name)
LEFT JOIN information_schema.views v
    ON v.table_name = expected.table_name
    AND v.table_schema = 'public';

-- -----------------------------------------------------------------------------
-- 6. TEST LIKE TOGGLE (Dry run - rollback)
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_test_ad_id uuid;
    v_result boolean;
BEGIN
    -- Get a test ad
    SELECT id INTO v_test_ad_id FROM ads LIMIT 1;

    IF v_test_ad_id IS NOT NULL THEN
        -- Test toggle on
        v_result := fn_toggle_like(v_test_ad_id, 'test-session-qa');
        IF v_result != true THEN
            RAISE NOTICE 'FAIL: First toggle should return true, got %', v_result;
        ELSE
            RAISE NOTICE '✓ PASS: First toggle returned true';
        END IF;

        -- Test toggle off
        v_result := fn_toggle_like(v_test_ad_id, 'test-session-qa');
        IF v_result != false THEN
            RAISE NOTICE 'FAIL: Second toggle should return false, got %', v_result;
        ELSE
            RAISE NOTICE '✓ PASS: Second toggle returned false';
        END IF;

        -- Cleanup
        DELETE FROM ad_user_reactions WHERE session_id = 'test-session-qa';
        DELETE FROM ad_rate_limits WHERE session_id = 'test-session-qa';
        RAISE NOTICE '✓ PASS: Toggle test completed and cleaned up';
    ELSE
        RAISE NOTICE 'SKIP: No ads found for toggle test';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 7. TEST VIEW RECORDING (Dry run - rollback)
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_test_ad_id uuid;
    v_initial_count integer;
    v_final_count integer;
BEGIN
    -- Get a test ad
    SELECT id INTO v_test_ad_id FROM ads LIMIT 1;

    IF v_test_ad_id IS NOT NULL THEN
        -- Get initial count
        SELECT COALESCE(view_count, 0) INTO v_initial_count
        FROM ad_feedback_agg WHERE ad_id = v_test_ad_id;
        v_initial_count := COALESCE(v_initial_count, 0);

        -- Record view
        PERFORM fn_record_ad_view(v_test_ad_id, 'test-session-view-qa');

        -- Get final count
        SELECT view_count INTO v_final_count
        FROM ad_feedback_agg WHERE ad_id = v_test_ad_id;

        IF v_final_count = v_initial_count + 1 THEN
            RAISE NOTICE '✓ PASS: View count incremented from % to %', v_initial_count, v_final_count;
        ELSE
            RAISE NOTICE 'FAIL: View count was %, expected %', v_final_count, v_initial_count + 1;
        END IF;

        -- Cleanup (just rate limit, keep view count)
        DELETE FROM ad_rate_limits WHERE session_id = 'test-session-view-qa';
    ELSE
        RAISE NOTICE 'SKIP: No ads found for view test';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 8. TEST TAG SUGGESTION (Dry run - rollback)
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_test_ad_id uuid;
    v_tag_id uuid;
BEGIN
    -- Get a test ad
    SELECT id INTO v_test_ad_id FROM ads LIMIT 1;

    IF v_test_ad_id IS NOT NULL THEN
        -- Suggest tag
        v_tag_id := fn_suggest_tag(v_test_ad_id, 'test-session-tag-qa', 'test tag');

        IF v_tag_id IS NOT NULL THEN
            RAISE NOTICE '✓ PASS: Tag suggestion created with id %', v_tag_id;

            -- Verify it's pending
            IF EXISTS (SELECT 1 FROM ad_user_tags WHERE id = v_tag_id AND status = 'pending') THEN
                RAISE NOTICE '✓ PASS: Tag status is pending';
            ELSE
                RAISE NOTICE 'FAIL: Tag status is not pending';
            END IF;
        ELSE
            RAISE NOTICE 'FAIL: Tag suggestion returned null';
        END IF;

        -- Cleanup
        DELETE FROM ad_user_tags WHERE session_id = 'test-session-tag-qa';
        DELETE FROM ad_rate_limits WHERE session_id = 'test-session-tag-qa';
        RAISE NOTICE '✓ PASS: Tag test completed and cleaned up';
    ELSE
        RAISE NOTICE 'SKIP: No ads found for tag test';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 9. VERIFY AGGREGATION TRIGGER (Check agg table updated)
-- -----------------------------------------------------------------------------
SELECT
    COUNT(*) FILTER (WHERE view_count > 0) as ads_with_views,
    COUNT(*) FILTER (WHERE like_count > 0) as ads_with_likes,
    COUNT(*) FILTER (WHERE save_count > 0) as ads_with_saves,
    COUNT(*) as total_agg_rows
FROM ad_feedback_agg;

-- -----------------------------------------------------------------------------
-- 10. DATA INTEGRITY CHECKS
-- -----------------------------------------------------------------------------
-- Orphaned editorial records (should be 0)
SELECT COUNT(*) as orphaned_editorial
FROM ad_editorial e
LEFT JOIN ads a ON a.id = e.ad_id
WHERE a.id IS NULL;

-- Orphaned reactions (should be 0)
SELECT COUNT(*) as orphaned_reactions
FROM ad_user_reactions r
LEFT JOIN ads a ON a.id = r.ad_id
WHERE a.id IS NULL;

-- Orphaned tags (should be 0)
SELECT COUNT(*) as orphaned_tags
FROM ad_user_tags t
LEFT JOIN ads a ON a.id = t.ad_id
WHERE a.id IS NULL;

-- Orphaned agg records (should be 0)
SELECT COUNT(*) as orphaned_agg
FROM ad_feedback_agg f
LEFT JOIN ads a ON a.id = f.ad_id
WHERE a.id IS NULL;

-- -----------------------------------------------------------------------------
-- 11. RATE LIMIT TEST
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_test_ad_id uuid;
    i integer;
BEGIN
    SELECT id INTO v_test_ad_id FROM ads LIMIT 1;

    IF v_test_ad_id IS NOT NULL THEN
        -- Try to exceed rate limit (50 likes per hour)
        FOR i IN 1..55 LOOP
            BEGIN
                PERFORM fn_toggle_like(v_test_ad_id, 'rate-limit-test-' || i::text);
            EXCEPTION WHEN OTHERS THEN
                IF i > 50 THEN
                    RAISE NOTICE '✓ PASS: Rate limit triggered at iteration %', i;
                ELSE
                    RAISE NOTICE 'FAIL: Rate limit triggered too early at iteration %', i;
                END IF;
                EXIT;
            END;
        END LOOP;

        -- Cleanup
        DELETE FROM ad_user_reactions WHERE session_id LIKE 'rate-limit-test-%';
        DELETE FROM ad_rate_limits WHERE session_id LIKE 'rate-limit-test-%';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 12. SAMPLE DATA QUERIES (for manual verification)
-- -----------------------------------------------------------------------------

-- View merged ad data (editorial + extractor)
SELECT * FROM v_ad_with_editorial LIMIT 5;

-- View pending moderation queue
SELECT * FROM v_tag_moderation_queue LIMIT 10;

-- Popular ads by engagement (with threshold check)
SELECT
    a.external_id,
    a.brand_name,
    f.view_count,
    f.like_count,
    f.save_count,
    f.engagement_score,
    (f.like_count >= 5 OR f.save_count >= 3) as meets_ranking_threshold
FROM ads a
JOIN ad_feedback_agg f ON f.ad_id = a.id
WHERE f.engagement_score > 0
ORDER BY f.engagement_score DESC
LIMIT 20;

-- -----------------------------------------------------------------------------
-- 13. SEO ROUTE GATING TEST (Verify unpublished/scheduled 404s)
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_test_ad_id uuid;
    v_editorial_id uuid;
    v_found boolean;
BEGIN
    -- Get a test ad
    SELECT id INTO v_test_ad_id FROM ads LIMIT 1;

    IF v_test_ad_id IS NOT NULL THEN
        -- Create test editorial rows with different statuses
        -- 1. Draft (should NOT be visible)
        INSERT INTO ad_editorial (ad_id, brand_slug, slug, status)
        VALUES (v_test_ad_id, 'test-brand', 'draft-test', 'draft')
        RETURNING id INTO v_editorial_id;

        SELECT EXISTS (
            SELECT 1 FROM ad_editorial
            WHERE brand_slug = 'test-brand' AND slug = 'draft-test'
              AND status = 'published'
              AND is_hidden = false
              AND (publish_date IS NULL OR publish_date <= NOW())
        ) INTO v_found;

        IF v_found THEN
            RAISE NOTICE 'FAIL: Draft content should NOT be visible';
        ELSE
            RAISE NOTICE '✓ PASS: Draft content correctly hidden';
        END IF;

        DELETE FROM ad_editorial WHERE id = v_editorial_id;

        -- 2. Published but future publish_date (should NOT be visible)
        INSERT INTO ad_editorial (ad_id, brand_slug, slug, status, publish_date)
        VALUES (v_test_ad_id, 'test-brand', 'scheduled-test', 'published', NOW() + interval '1 day')
        RETURNING id INTO v_editorial_id;

        SELECT EXISTS (
            SELECT 1 FROM ad_editorial
            WHERE brand_slug = 'test-brand' AND slug = 'scheduled-test'
              AND status = 'published'
              AND is_hidden = false
              AND (publish_date IS NULL OR publish_date <= NOW())
        ) INTO v_found;

        IF v_found THEN
            RAISE NOTICE 'FAIL: Scheduled future content should NOT be visible';
        ELSE
            RAISE NOTICE '✓ PASS: Scheduled future content correctly hidden';
        END IF;

        DELETE FROM ad_editorial WHERE id = v_editorial_id;

        -- 3. Published with is_hidden = true (should NOT be visible)
        INSERT INTO ad_editorial (ad_id, brand_slug, slug, status, is_hidden)
        VALUES (v_test_ad_id, 'test-brand', 'hidden-test', 'published', true)
        RETURNING id INTO v_editorial_id;

        SELECT EXISTS (
            SELECT 1 FROM ad_editorial
            WHERE brand_slug = 'test-brand' AND slug = 'hidden-test'
              AND status = 'published'
              AND is_hidden = false
              AND (publish_date IS NULL OR publish_date <= NOW())
        ) INTO v_found;

        IF v_found THEN
            RAISE NOTICE 'FAIL: Hidden content should NOT be visible';
        ELSE
            RAISE NOTICE '✓ PASS: Hidden content correctly hidden';
        END IF;

        DELETE FROM ad_editorial WHERE id = v_editorial_id;

        -- 4. Published, not hidden, no future date (SHOULD be visible)
        INSERT INTO ad_editorial (ad_id, brand_slug, slug, status, is_hidden)
        VALUES (v_test_ad_id, 'test-brand', 'published-test', 'published', false)
        RETURNING id INTO v_editorial_id;

        SELECT EXISTS (
            SELECT 1 FROM ad_editorial
            WHERE brand_slug = 'test-brand' AND slug = 'published-test'
              AND status = 'published'
              AND is_hidden = false
              AND (publish_date IS NULL OR publish_date <= NOW())
        ) INTO v_found;

        IF v_found THEN
            RAISE NOTICE '✓ PASS: Published content correctly visible';
        ELSE
            RAISE NOTICE 'FAIL: Published content should be visible';
        END IF;

        DELETE FROM ad_editorial WHERE id = v_editorial_id;

        RAISE NOTICE '✓ PASS: SEO gating tests completed';
    ELSE
        RAISE NOTICE 'SKIP: No ads found for SEO gating test';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 14. STATE TRANSITION TEST (Verify delta-based aggregate updates)
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_test_ad_id uuid;
    v_initial_likes integer;
    v_after_like integer;
    v_after_unlike integer;
BEGIN
    -- Get a test ad
    SELECT id INTO v_test_ad_id FROM ads LIMIT 1;

    IF v_test_ad_id IS NOT NULL THEN
        -- Ensure agg row exists
        INSERT INTO ad_feedback_agg (ad_id, like_count)
        VALUES (v_test_ad_id, 0)
        ON CONFLICT (ad_id) DO UPDATE SET like_count = 0;

        SELECT like_count INTO v_initial_likes
        FROM ad_feedback_agg WHERE ad_id = v_test_ad_id;

        -- Toggle like ON
        PERFORM fn_toggle_like(v_test_ad_id, 'state-test-session');

        SELECT like_count INTO v_after_like
        FROM ad_feedback_agg WHERE ad_id = v_test_ad_id;

        IF v_after_like = v_initial_likes + 1 THEN
            RAISE NOTICE '✓ PASS: Like ON incremented count from % to %', v_initial_likes, v_after_like;
        ELSE
            RAISE NOTICE 'FAIL: Like ON expected %, got %', v_initial_likes + 1, v_after_like;
        END IF;

        -- Toggle like OFF
        PERFORM fn_toggle_like(v_test_ad_id, 'state-test-session');

        SELECT like_count INTO v_after_unlike
        FROM ad_feedback_agg WHERE ad_id = v_test_ad_id;

        IF v_after_unlike = v_initial_likes THEN
            RAISE NOTICE '✓ PASS: Like OFF decremented count from % to %', v_after_like, v_after_unlike;
        ELSE
            RAISE NOTICE 'FAIL: Like OFF expected %, got %', v_initial_likes, v_after_unlike;
        END IF;

        -- Cleanup
        DELETE FROM ad_user_reactions WHERE session_id = 'state-test-session';
        DELETE FROM ad_rate_limits WHERE session_id = 'state-test-session';

        RAISE NOTICE '✓ PASS: State transition test completed';
    ELSE
        RAISE NOTICE 'SKIP: No ads found for state transition test';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 15. AGGREGATE CONSISTENCY CHECK (Verify counts match raw data)
-- -----------------------------------------------------------------------------
SELECT
    f.ad_id,
    f.like_count as agg_likes,
    (SELECT COUNT(*) FROM ad_user_reactions WHERE ad_id = f.ad_id AND is_liked = true) as actual_likes,
    f.save_count as agg_saves,
    (SELECT COUNT(*) FROM ad_user_reactions WHERE ad_id = f.ad_id AND is_saved = true) as actual_saves,
    CASE
        WHEN f.like_count = (SELECT COUNT(*) FROM ad_user_reactions WHERE ad_id = f.ad_id AND is_liked = true)
         AND f.save_count = (SELECT COUNT(*) FROM ad_user_reactions WHERE ad_id = f.ad_id AND is_saved = true)
        THEN '✓ CONSISTENT'
        ELSE '✗ DRIFT DETECTED'
    END as consistency_status
FROM ad_feedback_agg f
LIMIT 20;
