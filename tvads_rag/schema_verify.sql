-- =============================================================================
-- DATABASE SCHEMA VERIFICATION
-- =============================================================================
--
-- Run this to check if your database has all required columns.
-- Copy and paste into Supabase SQL Editor.
--
-- =============================================================================

-- Check ads table columns
SELECT
    'ads' as table_name,
    column_name,
    data_type,
    CASE
        WHEN column_name IN (
            'extraction_warnings', 'extraction_fill_rate', 'extraction_validation',
            'toxicity_total', 'toxicity_risk_level', 'toxicity_labels',
            'toxicity_subscores', 'toxicity_version', 'toxicity_report',
            'clearance_body', 'clearance_id', 'clearance_country'
        ) THEN 'FOUND'
        ELSE 'N/A'
    END as status
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'ads'
  AND column_name IN (
      'extraction_warnings', 'extraction_fill_rate', 'extraction_validation',
      'toxicity_total', 'toxicity_risk_level', 'toxicity_labels',
      'toxicity_subscores', 'toxicity_version', 'toxicity_report',
      'clearance_body', 'clearance_id', 'clearance_country'
  )
ORDER BY column_name;

-- Check ad_claims table columns
SELECT
    'ad_claims' as table_name,
    column_name,
    data_type,
    'FOUND' as status
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'ad_claims'
  AND column_name IN ('timestamp_start_s', 'timestamp_end_s', 'evidence', 'confidence')
ORDER BY column_name;

-- Check ad_supers table columns
SELECT
    'ad_supers' as table_name,
    column_name,
    data_type,
    'FOUND' as status
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'ad_supers'
  AND column_name IN ('evidence', 'confidence')
ORDER BY column_name;

-- =============================================================================
-- SUMMARY: Expected column counts
-- =============================================================================
--
-- If your database is up to date, you should see:
--   ads table:        12 columns (extraction: 3, toxicity: 6, clearance: 3)
--   ad_claims table:  4 columns (timestamp_start_s, timestamp_end_s, evidence, confidence)
--   ad_supers table:  2 columns (evidence, confidence)
--
-- If any are missing, run: tvads_rag/schema_all_migrations.sql
--
-- =============================================================================

-- Count check
SELECT
    'SUMMARY' as check_type,
    (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = 'ads'
     AND column_name IN ('extraction_warnings', 'extraction_fill_rate', 'extraction_validation',
                         'toxicity_total', 'toxicity_risk_level', 'toxicity_labels',
                         'toxicity_subscores', 'toxicity_version', 'toxicity_report',
                         'clearance_body', 'clearance_id', 'clearance_country')
    ) as ads_new_columns,
    (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = 'ad_claims'
     AND column_name IN ('timestamp_start_s', 'timestamp_end_s', 'evidence', 'confidence')
    ) as claims_evidence_columns,
    (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = 'ad_supers'
     AND column_name IN ('evidence', 'confidence')
    ) as supers_evidence_columns,
    CASE
        WHEN (SELECT COUNT(*) FROM information_schema.columns
              WHERE table_schema = 'public' AND table_name = 'ads'
              AND column_name IN ('extraction_warnings', 'extraction_fill_rate', 'extraction_validation',
                                  'toxicity_total', 'toxicity_risk_level', 'toxicity_labels',
                                  'toxicity_subscores', 'toxicity_version', 'toxicity_report',
                                  'clearance_body', 'clearance_id', 'clearance_country')) = 12
             AND (SELECT COUNT(*) FROM information_schema.columns
                  WHERE table_schema = 'public' AND table_name = 'ad_claims'
                  AND column_name IN ('timestamp_start_s', 'timestamp_end_s', 'evidence', 'confidence')) = 4
             AND (SELECT COUNT(*) FROM information_schema.columns
                  WHERE table_schema = 'public' AND table_name = 'ad_supers'
                  AND column_name IN ('evidence', 'confidence')) = 2
        THEN 'READY FOR INGESTION'
        ELSE 'RUN MIGRATIONS: tvads_rag/schema_all_migrations.sql'
    END as status;
