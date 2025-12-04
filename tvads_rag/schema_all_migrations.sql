-- =============================================================================
-- CONSOLIDATED MIGRATIONS - Run All (Safe to run multiple times)
-- =============================================================================
--
-- This file consolidates all additive migrations for the TellyAds RAG system.
-- All statements use IF NOT EXISTS, so it's safe to run multiple times.
--
-- Run this in Supabase SQL Editor or via psql:
--   psql $SUPABASE_DB_URL -f tvads_rag/schema_all_migrations.sql
--
-- =============================================================================

-- =============================================================================
-- 1. EXTRACTION OBSERVABILITY (schema_extraction_columns.sql)
-- =============================================================================

ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS extraction_warnings jsonb DEFAULT '[]'::jsonb;

ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS extraction_fill_rate jsonb DEFAULT '{}'::jsonb;

ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS extraction_validation jsonb DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_ads_extraction_fill_rate
ON public.ads ((extraction_fill_rate->>'overall'))
WHERE extraction_fill_rate IS NOT NULL;

-- =============================================================================
-- 2. CLAIMS EVIDENCE GROUNDING (schema_claims_supers_evidence.sql)
-- =============================================================================

-- Claims: timestamps, evidence, confidence
ALTER TABLE public.ad_claims
ADD COLUMN IF NOT EXISTS timestamp_start_s float DEFAULT NULL;

ALTER TABLE public.ad_claims
ADD COLUMN IF NOT EXISTS timestamp_end_s float DEFAULT NULL;

ALTER TABLE public.ad_claims
ADD COLUMN IF NOT EXISTS evidence jsonb DEFAULT '{}'::jsonb;

ALTER TABLE public.ad_claims
ADD COLUMN IF NOT EXISTS confidence float DEFAULT NULL;

-- Supers: evidence, confidence (start_time/end_time already exist)
ALTER TABLE public.ad_supers
ADD COLUMN IF NOT EXISTS evidence jsonb DEFAULT '{}'::jsonb;

ALTER TABLE public.ad_supers
ADD COLUMN IF NOT EXISTS confidence float DEFAULT NULL;

-- Indexes for claims/supers
CREATE INDEX IF NOT EXISTS idx_ad_claims_confidence ON public.ad_claims(confidence)
WHERE confidence IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ad_supers_confidence ON public.ad_supers(confidence)
WHERE confidence IS NOT NULL;

-- =============================================================================
-- 3. TOXICITY SCORING (schema_toxicity_columns.sql)
-- =============================================================================

ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS toxicity_total float DEFAULT NULL;

ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS toxicity_risk_level text DEFAULT NULL;

ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS toxicity_labels jsonb DEFAULT '[]'::jsonb;

ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS toxicity_subscores jsonb DEFAULT '{}'::jsonb;

ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS toxicity_version text DEFAULT NULL;

ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS toxicity_report jsonb DEFAULT '{}'::jsonb;

-- Toxicity indexes
CREATE INDEX IF NOT EXISTS idx_ads_toxicity_total
ON public.ads (toxicity_total)
WHERE toxicity_total IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ads_toxicity_risk_level
ON public.ads (toxicity_risk_level)
WHERE toxicity_risk_level IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ads_has_toxicity
ON public.ads ((toxicity_total IS NOT NULL))
WHERE toxicity_total IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ads_toxicity_labels_gin
ON public.ads USING gin (toxicity_labels jsonb_path_ops);

-- =============================================================================
-- 4. REGULATORY CLEARANCE (schema_clearance.sql)
-- =============================================================================

ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS clearance_body text DEFAULT NULL;

ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS clearance_id text DEFAULT NULL;

ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS clearance_country text DEFAULT NULL;

-- Clearance indexes
CREATE INDEX IF NOT EXISTS idx_ads_clearance_body
ON public.ads (clearance_body)
WHERE clearance_body IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ads_clearance_id
ON public.ads (clearance_id)
WHERE clearance_id IS NOT NULL;

-- =============================================================================
-- VERIFICATION QUERIES (run after to confirm all columns exist)
-- =============================================================================

-- Uncomment and run these to verify:

-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_schema = 'public' AND table_name = 'ads'
-- AND column_name IN (
--     'extraction_warnings', 'extraction_fill_rate', 'extraction_validation',
--     'toxicity_total', 'toxicity_risk_level', 'toxicity_labels', 'toxicity_subscores', 'toxicity_version', 'toxicity_report',
--     'clearance_body', 'clearance_id', 'clearance_country'
-- )
-- ORDER BY column_name;

-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_schema = 'public' AND table_name = 'ad_claims'
-- AND column_name IN ('timestamp_start_s', 'timestamp_end_s', 'evidence', 'confidence')
-- ORDER BY column_name;

-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_schema = 'public' AND table_name = 'ad_supers'
-- AND column_name IN ('evidence', 'confidence')
-- ORDER BY column_name;

-- =============================================================================
-- DONE
-- =============================================================================
