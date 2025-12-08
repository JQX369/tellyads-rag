-- Migration 005: Fix Embedding Search
-- Ensures embedding_items is the canonical source for ad-level semantic search
--
-- Background: Search API was querying ads.embedding which doesn't exist.
-- The pipeline writes ad-level embeddings to embedding_items with item_type='ad_summary'.
-- This migration adds constraints and indexes to support efficient ad-level search.

-- ============================================================================
-- 1. Add unique constraint to prevent duplicate ad_summary per ad
-- ============================================================================
-- This ensures at most one ad_summary embedding per ad for consistent search results

DO $$
BEGIN
    -- Create unique index for ad_summary (one per ad)
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_embedding_items_ad_summary_unique'
    ) THEN
        CREATE UNIQUE INDEX idx_embedding_items_ad_summary_unique
            ON embedding_items (ad_id)
            WHERE item_type = 'ad_summary';

        RAISE NOTICE 'Created unique index for ad_summary embeddings';
    END IF;
END;
$$;

-- ============================================================================
-- 2. Add HNSW index on embedding column for fast vector search
-- ============================================================================
-- Use cosine distance operator class (vector_cosine_ops) to match <=> operator

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_embedding_items_embedding_hnsw'
    ) THEN
        CREATE INDEX idx_embedding_items_embedding_hnsw
            ON embedding_items
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);

        RAISE NOTICE 'Created HNSW index on embedding_items.embedding';
    END IF;
END;
$$;

-- ============================================================================
-- 3. Add partial index for ad_summary type (faster ad-level search)
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_embedding_items_ad_summary_embedding'
    ) THEN
        CREATE INDEX idx_embedding_items_ad_summary_embedding
            ON embedding_items
            USING hnsw (embedding vector_cosine_ops)
            WHERE item_type = 'ad_summary';

        RAISE NOTICE 'Created partial HNSW index for ad_summary embeddings';
    END IF;
END;
$$;

-- ============================================================================
-- 4. Create helper function for ad-level semantic search
-- ============================================================================
-- Returns ads ordered by embedding similarity, with proper publish gating

CREATE OR REPLACE FUNCTION search_ads_by_embedding(
    query_embedding vector(1536),
    limit_count integer DEFAULT 20,
    p_brand_name text DEFAULT NULL,
    p_year integer DEFAULT NULL,
    p_product_category text DEFAULT NULL,
    p_has_supers boolean DEFAULT NULL
)
RETURNS TABLE (
    ad_id uuid,
    external_id text,
    brand_name text,
    product_name text,
    product_category text,
    one_line_summary text,
    format_type text,
    year integer,
    duration_seconds numeric,
    s3_key text,
    has_supers boolean,
    has_price_claims boolean,
    impact_scores jsonb,
    similarity double precision
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        a.id as ad_id,
        a.external_id,
        a.brand_name,
        a.product_name,
        a.product_category,
        a.one_line_summary,
        a.format_type,
        a.year,
        a.duration_seconds,
        a.s3_key,
        a.has_supers,
        a.has_price_claims,
        a.impact_scores,
        1 - (ei.embedding <=> query_embedding) as similarity
    FROM embedding_items ei
    JOIN ads a ON a.id = ei.ad_id
    WHERE ei.item_type = 'ad_summary'
      AND (p_brand_name IS NULL OR a.brand_name ILIKE '%' || p_brand_name || '%')
      AND (p_year IS NULL OR a.year = p_year)
      AND (p_product_category IS NULL OR a.product_category ILIKE '%' || p_product_category || '%')
      AND (p_has_supers IS NULL OR a.has_supers = p_has_supers)
    ORDER BY ei.embedding <=> query_embedding
    LIMIT limit_count;
$$;

COMMENT ON FUNCTION search_ads_by_embedding IS
'Search ads by semantic similarity using ad_summary embeddings from embedding_items table';

-- ============================================================================
-- 5. Create helper function for similar ads lookup
-- ============================================================================

CREATE OR REPLACE FUNCTION get_similar_ads(
    source_ad_id uuid,
    limit_count integer DEFAULT 10
)
RETURNS TABLE (
    ad_id uuid,
    external_id text,
    brand_name text,
    product_name text,
    product_category text,
    one_line_summary text,
    format_type text,
    year integer,
    duration_seconds numeric,
    s3_key text,
    impact_scores jsonb,
    similarity double precision
)
LANGUAGE sql
STABLE
AS $$
    WITH source_embedding AS (
        SELECT embedding
        FROM embedding_items
        WHERE ad_id = source_ad_id AND item_type = 'ad_summary'
        LIMIT 1
    )
    SELECT
        a.id as ad_id,
        a.external_id,
        a.brand_name,
        a.product_name,
        a.product_category,
        a.one_line_summary,
        a.format_type,
        a.year,
        a.duration_seconds,
        a.s3_key,
        a.impact_scores,
        1 - (ei.embedding <=> se.embedding) as similarity
    FROM source_embedding se
    CROSS JOIN LATERAL (
        SELECT *
        FROM embedding_items
        WHERE item_type = 'ad_summary'
          AND ad_id != source_ad_id
        ORDER BY embedding <=> se.embedding
        LIMIT limit_count
    ) ei
    JOIN ads a ON a.id = ei.ad_id;
$$;

COMMENT ON FUNCTION get_similar_ads IS
'Find similar ads based on ad_summary embedding similarity';

-- ============================================================================
-- 6. Verification queries (run manually to validate)
-- ============================================================================

-- Check ad_summary count per ad (should be exactly 1 for each):
-- SELECT ad_id, COUNT(*) as cnt
-- FROM embedding_items
-- WHERE item_type = 'ad_summary'
-- GROUP BY ad_id
-- HAVING COUNT(*) > 1;

-- Verify HNSW index is used:
-- EXPLAIN ANALYZE SELECT * FROM search_ads_by_embedding('[0.1,0.2,...]'::vector, 10);

-- Check total ad_summary embeddings vs total ads:
-- SELECT
--     (SELECT COUNT(*) FROM ads) as total_ads,
--     (SELECT COUNT(*) FROM embedding_items WHERE item_type = 'ad_summary') as ads_with_embedding;
