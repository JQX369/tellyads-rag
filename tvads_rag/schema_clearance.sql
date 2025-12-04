-- Migration: Add regulatory clearance tracking columns
-- Run this in Supabase SQL Editor or via psql
-- Safe to run multiple times (uses IF NOT EXISTS)

-- =============================================================================
-- CLEARANCE TRACKING COLUMNS
-- =============================================================================

-- Regulatory body that cleared the ad (e.g., "UK Clearcast", "ARPP France")
ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS clearance_body text DEFAULT NULL;

-- Official clearance ID from that body (e.g., "TABC1234" for Clearcast)
ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS clearance_id text DEFAULT NULL;

-- Country where the ad was officially cleared (known, not estimated)
-- This is different from "country" which is the estimated target market
ALTER TABLE public.ads
ADD COLUMN IF NOT EXISTS clearance_country text DEFAULT NULL;

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Index for filtering by clearance body
CREATE INDEX IF NOT EXISTS idx_ads_clearance_body
ON public.ads (clearance_body)
WHERE clearance_body IS NOT NULL;

-- Index for looking up by clearance ID
CREATE INDEX IF NOT EXISTS idx_ads_clearance_id
ON public.ads (clearance_id)
WHERE clearance_id IS NOT NULL;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON COLUMN public.ads.clearance_body IS
'Regulatory body that approved the ad: UK Clearcast, ARPP France, FTC USA, etc.';

COMMENT ON COLUMN public.ads.clearance_id IS
'Official clearance reference number from the regulatory body.';

COMMENT ON COLUMN public.ads.clearance_country IS
'Country where the ad was officially cleared (known fact, not estimated).';

-- =============================================================================
-- KNOWN CLEARANCE BODY PREFIXES
-- =============================================================================
--
-- When ingesting ads, we infer clearance from external_id prefixes:
--
-- | Prefix | Clearance Body | Country |
-- |--------|---------------|---------|
-- | TA*    | UK Clearcast  | UK      |
-- | (more to be added as identified) |
--
-- =============================================================================
