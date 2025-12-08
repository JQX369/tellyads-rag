-- Toxicity Scoring Schema Migration
-- Adds toxicity_report column to store calculated toxicity scores and analysis

-- Add toxicity_report column to ads table
DO $$
BEGIN
    -- Toxicity Report column (Dec 2025)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ads' AND column_name = 'toxicity_report'
    ) THEN
        ALTER TABLE ads ADD COLUMN toxicity_report jsonb DEFAULT '{}'::jsonb;
        
        -- Add index for querying by toxicity score
        CREATE INDEX IF NOT EXISTS idx_ads_toxicity_score 
        ON ads ((toxicity_report->>'toxic_score'));
        
        -- Add index for querying by risk level
        CREATE INDEX IF NOT EXISTS idx_ads_risk_level 
        ON ads ((toxicity_report->>'risk_level'));
        
        -- Add GIN index for querying breakdown flags
        CREATE INDEX IF NOT EXISTS idx_ads_toxicity_breakdown 
        ON ads USING gin((toxicity_report->'breakdown'));
        
        COMMENT ON COLUMN ads.toxicity_report IS 
        'Toxicity scoring report (0-100) with breakdown by physiological, psychological, and regulatory risk. Includes dark patterns detected and AI analysis if enabled.';
    END IF;
END;
$$;




