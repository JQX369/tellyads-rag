-- Migration: Add evidence, timestamps, and confidence to claims and supers
-- Run this in Supabase SQL Editor or via psql
-- Safe to run multiple times (uses IF NOT EXISTS)

-- =============================================================================
-- Claims: Add timestamps, evidence, confidence
-- =============================================================================

-- Timestamp columns for claims (start and end in seconds)
ALTER TABLE public.ad_claims
ADD COLUMN IF NOT EXISTS timestamp_start_s float DEFAULT NULL;

ALTER TABLE public.ad_claims
ADD COLUMN IF NOT EXISTS timestamp_end_s float DEFAULT NULL;

-- Evidence JSONB for claims
-- Schema: {source: "transcript"|"super"|"vision"|"unknown", excerpt: string, match_method: "exact"|"fuzzy"|"range"|"none"}
ALTER TABLE public.ad_claims
ADD COLUMN IF NOT EXISTS evidence jsonb DEFAULT '{}'::jsonb;

-- Confidence score (0.0-1.0) for claims
ALTER TABLE public.ad_claims
ADD COLUMN IF NOT EXISTS confidence float DEFAULT NULL;

-- =============================================================================
-- Supers: Add evidence, confidence (already have start_time, end_time)
-- =============================================================================

-- Evidence JSONB for supers
-- Schema: {source: "ocr"|"vision"|"unknown", excerpt: string, match_method: "exact"|"fuzzy"|"none"}
ALTER TABLE public.ad_supers
ADD COLUMN IF NOT EXISTS evidence jsonb DEFAULT '{}'::jsonb;

-- Confidence score (0.0-1.0) for supers
ALTER TABLE public.ad_supers
ADD COLUMN IF NOT EXISTS confidence float DEFAULT NULL;

-- =============================================================================
-- Indexes for filtering (optional but useful)
-- =============================================================================

-- Index on confidence for filtering low-confidence claims/supers
CREATE INDEX IF NOT EXISTS idx_ad_claims_confidence ON public.ad_claims(confidence)
WHERE confidence IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ad_supers_confidence ON public.ad_supers(confidence)
WHERE confidence IS NOT NULL;

-- =============================================================================
-- Verification queries (run after migration to confirm columns exist)
-- =============================================================================

-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_schema = 'public'
--   AND table_name = 'ad_claims'
--   AND column_name IN ('timestamp_start_s', 'timestamp_end_s', 'evidence', 'confidence');

-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_schema = 'public'
--   AND table_name = 'ad_supers'
--   AND column_name IN ('evidence', 'confidence');
