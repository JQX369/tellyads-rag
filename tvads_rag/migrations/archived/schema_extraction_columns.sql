-- Extraction Observability Columns Migration
-- Run this in Supabase SQL Editor (paste entire file)
--
-- Adds three JSONB columns for extraction observability:
-- - extraction_warnings: Array of warning objects from extraction/normalization
-- - extraction_fill_rate: Fill rate metrics (overall %, by section, missing fields)
-- - extraction_validation: Validation results (valid bool, errors array)

-- ============================================================================
-- COLUMNS
-- ============================================================================

-- Add extraction_warnings column
ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS extraction_warnings jsonb DEFAULT '[]'::jsonb;

-- Add extraction_fill_rate column
ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS extraction_fill_rate jsonb DEFAULT '{}'::jsonb;

-- Add extraction_validation column
ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS extraction_validation jsonb DEFAULT '{}'::jsonb;

-- ============================================================================
-- INDEXES (optional but recommended for querying)
-- ============================================================================

-- GIN index for searching warning codes (e.g. WHERE extraction_warnings @> '[{"code":"SCORE_CLAMPED"}]')
CREATE INDEX IF NOT EXISTS idx_ads_extraction_warnings_gin
ON public.ads USING gin (extraction_warnings jsonb_path_ops);

-- Index for querying by overall fill rate
CREATE INDEX IF NOT EXISTS idx_ads_fill_rate_overall
ON public.ads (((extraction_fill_rate->>'overall')::float));

-- Index for finding invalid extractions
CREATE INDEX IF NOT EXISTS idx_ads_extraction_invalid
ON public.ads ((extraction_validation->>'valid'))
WHERE extraction_validation->>'valid' = 'false';

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON COLUMN public.ads.extraction_warnings IS
'Array of extraction warning objects: [{code, message, meta, ts}, ...]';

COMMENT ON COLUMN public.ads.extraction_fill_rate IS
'Fill rate metrics: {overall, by_section, missing_top, filled_fields, total_fields, critical_sections_present, critical_sections_missing}';

COMMENT ON COLUMN public.ads.extraction_validation IS
'Validation results: {valid: bool, errors: [...]}';
