-- =============================================================================
-- TellyAds Import Helper Schema
-- Version: 1.0.0
-- Date: 2025-12-04
--
-- Adds:
--   1. legacy_url column on ad_editorial (for redirects)
--   2. legacy_url_misses table (for 404 monitoring)
--   3. Import review queries
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. ADD LEGACY_URL COLUMN TO ad_editorial
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ad_editorial' AND column_name = 'legacy_url'
    ) THEN
        ALTER TABLE ad_editorial ADD COLUMN legacy_url text;
    END IF;
END;
$$;

-- Index for fast redirect lookups
CREATE INDEX IF NOT EXISTS idx_ad_editorial_legacy_url
    ON ad_editorial(legacy_url)
    WHERE legacy_url IS NOT NULL;

-- -----------------------------------------------------------------------------
-- 2. LEGACY URL MISSES TABLE (404 Monitoring)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS legacy_url_misses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    url text UNIQUE NOT NULL,
    miss_count integer DEFAULT 1,
    first_attempted_at timestamptz DEFAULT now(),
    last_attempted_at timestamptz DEFAULT now(),
    user_agent text,
    referer text,
    resolved boolean DEFAULT false,
    resolution_notes text,
    resolved_to text  -- New canonical URL if resolved
);

-- Index for monitoring
CREATE INDEX IF NOT EXISTS idx_legacy_url_misses_unresolved
    ON legacy_url_misses(miss_count DESC)
    WHERE resolved = false;

-- -----------------------------------------------------------------------------
-- 3. FUNCTION: Log legacy URL miss
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_log_legacy_url_miss(
    p_url text,
    p_user_agent text DEFAULT NULL,
    p_referer text DEFAULT NULL
)
RETURNS void AS $$
BEGIN
    INSERT INTO legacy_url_misses (url, user_agent, referer)
    VALUES (p_url, p_user_agent, p_referer)
    ON CONFLICT (url) DO UPDATE SET
        miss_count = legacy_url_misses.miss_count + 1,
        last_attempted_at = now(),
        user_agent = COALESCE(EXCLUDED.user_agent, legacy_url_misses.user_agent),
        referer = COALESCE(EXCLUDED.referer, legacy_url_misses.referer);
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 4. IMPORT REVIEW VIEWS
-- -----------------------------------------------------------------------------

-- Unmatched editorial rows (imported but not linked to an ad)
CREATE OR REPLACE VIEW v_editorial_orphans AS
SELECT
    e.id,
    e.brand_slug,
    e.slug,
    e.headline,
    e.wix_item_id,
    e.legacy_url,
    e.status,
    e.created_at
FROM ad_editorial e
LEFT JOIN ads a ON a.id = e.ad_id
WHERE a.id IS NULL
ORDER BY e.created_at DESC;

-- Duplicate slugs per brand
CREATE OR REPLACE VIEW v_editorial_dup_slugs AS
SELECT
    brand_slug,
    slug,
    COUNT(*) as duplicate_count,
    array_agg(ad_id) as ad_ids
FROM ad_editorial
GROUP BY brand_slug, slug
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;

-- Published ads missing editorial
CREATE OR REPLACE VIEW v_ads_missing_editorial AS
SELECT
    a.id,
    a.external_id,
    a.brand_name,
    a.one_line_summary,
    a.year,
    a.created_at
FROM ads a
LEFT JOIN ad_editorial e ON e.ad_id = a.id
WHERE e.id IS NULL
ORDER BY a.created_at DESC;

-- Legacy URL coverage
CREATE OR REPLACE VIEW v_legacy_url_coverage AS
SELECT
    e.brand_slug,
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE e.legacy_url IS NOT NULL) as has_legacy_url,
    COUNT(*) FILTER (WHERE e.wix_item_id IS NOT NULL) as has_wix_id,
    COUNT(*) FILTER (WHERE e.status = 'published') as published_count
FROM ad_editorial e
GROUP BY e.brand_slug
ORDER BY total_count DESC;

-- Import statistics summary
CREATE OR REPLACE VIEW v_import_stats AS
SELECT
    (SELECT COUNT(*) FROM ads) as total_ads,
    (SELECT COUNT(*) FROM ad_editorial) as total_editorial,
    (SELECT COUNT(*) FROM ads a JOIN ad_editorial e ON e.ad_id = a.id) as matched,
    (SELECT COUNT(*) FROM ads a LEFT JOIN ad_editorial e ON e.ad_id = a.id WHERE e.id IS NULL) as ads_without_editorial,
    (SELECT COUNT(*) FROM ad_editorial WHERE status = 'published') as published_editorial,
    (SELECT COUNT(*) FROM ad_editorial WHERE status = 'draft') as draft_editorial,
    (SELECT COUNT(*) FROM ad_editorial WHERE legacy_url IS NOT NULL) as has_legacy_url,
    (SELECT COUNT(*) FROM legacy_url_misses WHERE resolved = false) as unresolved_404s;

-- Top 404s needing attention
CREATE OR REPLACE VIEW v_top_404s AS
SELECT
    url,
    miss_count,
    first_attempted_at,
    last_attempted_at,
    user_agent,
    referer
FROM legacy_url_misses
WHERE resolved = false
ORDER BY miss_count DESC
LIMIT 50;

-- -----------------------------------------------------------------------------
-- 5. COMMENTS
-- -----------------------------------------------------------------------------
COMMENT ON TABLE legacy_url_misses IS 'Tracks 404s from legacy Wix URLs for investigation';
COMMENT ON VIEW v_editorial_orphans IS 'Editorial records not linked to any ad (data quality issue)';
COMMENT ON VIEW v_editorial_dup_slugs IS 'Duplicate brand_slug/slug combinations (URL conflict)';
COMMENT ON VIEW v_ads_missing_editorial IS 'Ads without editorial content (need import or manual creation)';
COMMENT ON VIEW v_legacy_url_coverage IS 'Summary of legacy URL and Wix ID coverage by brand';
COMMENT ON VIEW v_import_stats IS 'High-level import statistics dashboard';
COMMENT ON VIEW v_top_404s IS 'Most common 404 URLs needing redirect rules';
