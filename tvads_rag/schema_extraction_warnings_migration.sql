-- Extraction Warnings Schema Migration
-- Adds explicit columns for extraction warnings and fill rate metrics
-- These are also stored in analysis_json but having dedicated columns enables
-- efficient querying and indexing.

-- Add extraction_warnings column (array of warning objects)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ads' AND column_name = 'extraction_warnings'
    ) THEN
        ALTER TABLE ads ADD COLUMN extraction_warnings jsonb DEFAULT '[]'::jsonb;

        -- Index for finding ads with warnings
        CREATE INDEX IF NOT EXISTS idx_ads_has_warnings
        ON ads ((jsonb_array_length(extraction_warnings) > 0))
        WHERE jsonb_array_length(extraction_warnings) > 0;

        -- GIN index for searching warning codes
        CREATE INDEX IF NOT EXISTS idx_ads_warning_codes
        ON ads USING gin (extraction_warnings jsonb_path_ops);

        COMMENT ON COLUMN ads.extraction_warnings IS
        'Array of extraction warning objects: [{code, message, meta, ts}, ...]';
    END IF;
END;
$$;

-- Add extraction_fill_rate column (fill rate metrics)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ads' AND column_name = 'extraction_fill_rate'
    ) THEN
        ALTER TABLE ads ADD COLUMN extraction_fill_rate jsonb DEFAULT '{}'::jsonb;

        -- Index for querying by overall fill rate
        CREATE INDEX IF NOT EXISTS idx_ads_fill_rate_overall
        ON ads (((extraction_fill_rate->>'overall')::float));

        COMMENT ON COLUMN ads.extraction_fill_rate IS
        'Fill rate metrics: {overall, by_section, missing_top, ...}';
    END IF;
END;
$$;

-- Add extraction_validation column (validation results)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ads' AND column_name = 'extraction_validation'
    ) THEN
        ALTER TABLE ads ADD COLUMN extraction_validation jsonb DEFAULT '{}'::jsonb;

        -- Index for finding invalid extractions
        CREATE INDEX IF NOT EXISTS idx_ads_extraction_invalid
        ON ads ((extraction_validation->>'valid'))
        WHERE extraction_validation->>'valid' = 'false';

        COMMENT ON COLUMN ads.extraction_validation IS
        'Validation results: {valid: bool, errors: [...]}';
    END IF;
END;
$$;

-- Add generated column for warning count (for efficient filtering)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ads' AND column_name = 'extraction_warning_count'
    ) THEN
        ALTER TABLE ads ADD COLUMN extraction_warning_count int
        GENERATED ALWAYS AS (jsonb_array_length(COALESCE(extraction_warnings, '[]'::jsonb))) STORED;

        CREATE INDEX IF NOT EXISTS idx_ads_warning_count
        ON ads (extraction_warning_count)
        WHERE extraction_warning_count > 0;
    END IF;
END;
$$;
