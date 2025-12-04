-- =============================================================================
-- FIX: Drop and recreate v_ad_with_editorial view
-- Run this BEFORE schema_micro_reasons.sql if view exists with different columns
-- =============================================================================

-- Drop the existing view (safe - views have no data)
DROP VIEW IF EXISTS v_ad_with_editorial CASCADE;

-- The view will be recreated by schema_micro_reasons.sql or schema_scoring_v2.sql
