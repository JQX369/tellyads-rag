-- Toxicity Scoring Columns Migration
-- Run this in Supabase SQL Editor (paste entire file)
--
-- Adds explicit columns for toxicity filtering and querying.
-- The full toxicity_report JSONB is also kept for detailed analysis.

-- ============================================================================
-- COLUMNS
-- ============================================================================

-- Total toxicity score (0-100)
ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS toxicity_total float DEFAULT NULL;

-- Risk level enum (LOW, MEDIUM, HIGH)
ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS toxicity_risk_level text DEFAULT NULL;

-- Dark pattern labels detected (array of strings)
ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS toxicity_labels jsonb DEFAULT '[]'::jsonb;

-- Subscores by category (physiological, psychological, regulatory)
ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS toxicity_subscores jsonb DEFAULT '{}'::jsonb;

-- Toxicity scoring version for tracking algorithm changes
ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS toxicity_version text DEFAULT NULL;

-- Full toxicity report (if not already present from previous migration)
ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS toxicity_report jsonb DEFAULT '{}'::jsonb;

-- ============================================================================
-- INDEXES (for efficient filtering)
-- ============================================================================

-- Index for filtering by total toxicity score
CREATE INDEX IF NOT EXISTS idx_ads_toxicity_total
ON public.ads (toxicity_total)
WHERE toxicity_total IS NOT NULL;

-- Index for filtering by risk level
CREATE INDEX IF NOT EXISTS idx_ads_toxicity_risk_level
ON public.ads (toxicity_risk_level)
WHERE toxicity_risk_level IS NOT NULL;

-- Index for checking if toxicity has been computed
CREATE INDEX IF NOT EXISTS idx_ads_has_toxicity
ON public.ads ((toxicity_total IS NOT NULL))
WHERE toxicity_total IS NOT NULL;

-- GIN index for searching dark pattern labels
CREATE INDEX IF NOT EXISTS idx_ads_toxicity_labels_gin
ON public.ads USING gin (toxicity_labels jsonb_path_ops);

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON COLUMN public.ads.toxicity_total IS
'Toxicity score 0-100 (0=safe, 100=maximum toxicity). Weighted sum of physiological, psychological, regulatory scores.';

COMMENT ON COLUMN public.ads.toxicity_risk_level IS
'Risk level: LOW (0-30), MEDIUM (31-60), HIGH (61+). Derived from toxicity_total.';

COMMENT ON COLUMN public.ads.toxicity_labels IS
'Array of detected dark pattern labels, e.g., ["false_scarcity", "shaming", "forced_continuity"]';

COMMENT ON COLUMN public.ads.toxicity_subscores IS
'Breakdown by category: {"physiological": {"score": N, "flags": [...]}, "psychological": {...}, "regulatory": {...}}';

COMMENT ON COLUMN public.ads.toxicity_version IS
'Toxicity algorithm version for tracking changes, e.g., "1.0.0" or "1.1.0-ai"';
