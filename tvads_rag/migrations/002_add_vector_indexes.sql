-- Migration 002: Add vector indexes for semantic search performance
--
-- This migration:
-- 1. Adds embedding column to ads table if not exists
-- 2. Creates HNSW indexes on both ads.embedding and embedding_items.embedding
--
-- HNSW is chosen over IVFFlat because:
-- - Better recall at similar latency
-- - No training phase required
-- - Smaller index size for our dataset (<100k records)
--
-- Operator class: vector_cosine_ops matches the <=> operator used in search queries
--
-- Run with:
--   psql "$SUPABASE_DB_URL" -f migrations/002_add_vector_indexes.sql
--
-- Verification:
--   SELECT indexname, indexdef FROM pg_indexes
--   WHERE tablename IN ('ads', 'embedding_items') AND indexname LIKE '%hnsw%';

-- Ensure pgvector extension is enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- 1. Add embedding column to ads table (if not exists)
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ads' AND column_name = 'embedding'
    ) THEN
        ALTER TABLE ads ADD COLUMN embedding vector(1536);
        RAISE NOTICE 'Added embedding column to ads table';
    ELSE
        RAISE NOTICE 'Embedding column already exists on ads table';
    END IF;
END;
$$;

-- ============================================================================
-- 2. Create HNSW index on ads.embedding for semantic search
-- ============================================================================
-- HNSW parameters:
-- - m=16: Number of connections per layer (default is 16, good balance)
-- - ef_construction=64: Build-time exploration factor (higher = better recall, slower build)
--
-- CONCURRENTLY allows the table to remain available during index creation
-- This is important for production deployments

DROP INDEX IF EXISTS idx_ads_embedding_hnsw;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ads_embedding_hnsw
ON ads USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- ============================================================================
-- 3. Create HNSW index on embedding_items.embedding
-- ============================================================================
-- This table is used for more granular semantic search (chunks, claims, etc.)

DROP INDEX IF EXISTS idx_embedding_items_embedding_hnsw;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_embedding_items_embedding_hnsw
ON embedding_items USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- ============================================================================
-- 4. Optional: Set HNSW search parameters for better recall
-- ============================================================================
-- ef_search controls query-time exploration (default 40, increase for better recall)
-- This is set per-connection, so we just document it here:
--
-- SET hnsw.ef_search = 100;  -- Run this before queries if needed

-- ============================================================================
-- Verification queries (run manually)
-- ============================================================================
-- Check indexes were created:
--   SELECT indexname, indexdef FROM pg_indexes
--   WHERE indexname LIKE '%hnsw%';
--
-- Check index size:
--   SELECT pg_size_pretty(pg_relation_size('idx_ads_embedding_hnsw'));
--   SELECT pg_size_pretty(pg_relation_size('idx_embedding_items_embedding_hnsw'));
--
-- Test search performance:
--   EXPLAIN ANALYZE
--   SELECT id, 1 - (embedding <=> '[0.1,0.2,...]'::vector) as similarity
--   FROM ads
--   WHERE embedding IS NOT NULL
--   ORDER BY embedding <=> '[0.1,0.2,...]'::vector
--   LIMIT 10;
