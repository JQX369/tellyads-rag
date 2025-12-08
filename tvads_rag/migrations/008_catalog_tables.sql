-- Catalog Import Schema Migration
-- DB-backed catalog for bulk ad metadata import from CSV files
-- Supports 20k+ row imports via worker processing (not Vercel runtime)

-- ============================================================================
-- Table: ad_catalog_imports (track CSV upload batches)
-- ============================================================================
CREATE TABLE IF NOT EXISTS ad_catalog_imports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    -- Status workflow: UPLOADED -> PROCESSING -> SUCCEEDED/FAILED
    status text NOT NULL DEFAULT 'UPLOADED'
        CHECK (status IN ('UPLOADED', 'PROCESSING', 'SUCCEEDED', 'FAILED')),

    -- Source file location (S3 key or Supabase Storage path)
    source_file_path text NOT NULL,
    original_filename text,

    -- Processing stats
    rows_total int DEFAULT 0,
    rows_ok int DEFAULT 0,
    rows_failed int DEFAULT 0,

    -- Error tracking
    last_error text,
    error_details jsonb DEFAULT '[]'::jsonb,

    -- Job reference
    job_id uuid REFERENCES ingestion_jobs(id) ON DELETE SET NULL,

    -- Admin who initiated the import
    initiated_by text
);

CREATE INDEX IF NOT EXISTS idx_ad_catalog_imports_status
    ON ad_catalog_imports (status, created_at DESC);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_ad_catalog_imports_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_ad_catalog_imports_updated_at ON ad_catalog_imports;
CREATE TRIGGER trigger_ad_catalog_imports_updated_at
    BEFORE UPDATE ON ad_catalog_imports
    FOR EACH ROW
    EXECUTE FUNCTION update_ad_catalog_imports_updated_at();

-- ============================================================================
-- Table: ad_catalog (master catalog of all known ads)
-- ============================================================================
CREATE TABLE IF NOT EXISTS ad_catalog (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    -- External identifier (unique across all sources)
    external_id text NOT NULL UNIQUE,

    -- Metadata from CSV
    brand_name text,
    title text,
    description text,

    -- Date handling with confidence tracking
    air_date date,
    air_date_raw text,  -- Original string from CSV
    date_parse_confidence float DEFAULT 1.0
        CHECK (date_parse_confidence >= 0 AND date_parse_confidence <= 1),
    date_parse_warning text,

    -- Time dimensions
    year int,
    decade text,  -- e.g., '1990s', '2000s'

    -- Geography
    country text,
    region text,
    language text,

    -- Media mapping
    s3_key text,
    video_url text,

    -- Seeded engagement metrics (from external sources)
    views_seeded bigint DEFAULT 0,
    likes_seeded bigint DEFAULT 0,

    -- Import tracking
    import_id uuid REFERENCES ad_catalog_imports(id) ON DELETE SET NULL,
    source_row_number int,

    -- Link to processed ad (once ingested)
    ad_id uuid REFERENCES ads(id) ON DELETE SET NULL,

    -- Processing flags
    is_mapped boolean GENERATED ALWAYS AS (
        s3_key IS NOT NULL OR video_url IS NOT NULL
    ) STORED,
    is_ingested boolean GENERATED ALWAYS AS (
        ad_id IS NOT NULL
    ) STORED
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_ad_catalog_brand
    ON ad_catalog (brand_name);

CREATE INDEX IF NOT EXISTS idx_ad_catalog_air_date
    ON ad_catalog (air_date DESC);

CREATE INDEX IF NOT EXISTS idx_ad_catalog_year
    ON ad_catalog (year DESC);

CREATE INDEX IF NOT EXISTS idx_ad_catalog_country
    ON ad_catalog (country);

CREATE INDEX IF NOT EXISTS idx_ad_catalog_import
    ON ad_catalog (import_id);

CREATE INDEX IF NOT EXISTS idx_ad_catalog_mapping_status
    ON ad_catalog (is_mapped, is_ingested);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_ad_catalog_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_ad_catalog_updated_at ON ad_catalog;
CREATE TRIGGER trigger_ad_catalog_updated_at
    BEFORE UPDATE ON ad_catalog
    FOR EACH ROW
    EXECUTE FUNCTION update_ad_catalog_updated_at();

-- ============================================================================
-- View: catalog_summary (for admin dashboard)
-- ============================================================================
CREATE OR REPLACE VIEW catalog_summary AS
SELECT
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE is_mapped) as mapped,
    COUNT(*) FILTER (WHERE NOT is_mapped) as unmapped,
    COUNT(*) FILTER (WHERE is_ingested) as ingested,
    COUNT(*) FILTER (WHERE NOT is_ingested) as not_ingested,
    COUNT(*) FILTER (WHERE date_parse_confidence < 0.8) as low_confidence_dates,
    COUNT(DISTINCT brand_name) as unique_brands,
    COUNT(DISTINCT country) as unique_countries,
    MIN(air_date) as earliest_date,
    MAX(air_date) as latest_date
FROM ad_catalog;

-- ============================================================================
-- View: catalog_by_decade (for filtering)
-- ============================================================================
CREATE OR REPLACE VIEW catalog_by_decade AS
SELECT
    decade,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE is_mapped) as mapped,
    COUNT(*) FILTER (WHERE is_ingested) as ingested
FROM ad_catalog
WHERE decade IS NOT NULL
GROUP BY decade
ORDER BY decade;

-- ============================================================================
-- Function: upsert_catalog_entry (idempotent row insertion)
-- ============================================================================
CREATE OR REPLACE FUNCTION upsert_catalog_entry(
    p_external_id text,
    p_brand_name text DEFAULT NULL,
    p_title text DEFAULT NULL,
    p_description text DEFAULT NULL,
    p_air_date date DEFAULT NULL,
    p_air_date_raw text DEFAULT NULL,
    p_date_parse_confidence float DEFAULT 1.0,
    p_date_parse_warning text DEFAULT NULL,
    p_year int DEFAULT NULL,
    p_country text DEFAULT NULL,
    p_region text DEFAULT NULL,
    p_language text DEFAULT NULL,
    p_s3_key text DEFAULT NULL,
    p_video_url text DEFAULT NULL,
    p_views_seeded bigint DEFAULT 0,
    p_likes_seeded bigint DEFAULT 0,
    p_import_id uuid DEFAULT NULL,
    p_source_row_number int DEFAULT NULL
)
RETURNS TABLE (
    catalog_id uuid,
    was_created boolean
) AS $$
DECLARE
    v_id uuid;
    v_created boolean := false;
    v_decade text;
BEGIN
    -- Compute decade
    IF p_year IS NOT NULL THEN
        v_decade := (FLOOR(p_year / 10) * 10)::text || 's';
    ELSIF p_air_date IS NOT NULL THEN
        v_decade := (FLOOR(EXTRACT(YEAR FROM p_air_date) / 10) * 10)::text || 's';
    END IF;

    -- Try insert first
    INSERT INTO ad_catalog (
        external_id, brand_name, title, description,
        air_date, air_date_raw, date_parse_confidence, date_parse_warning,
        year, decade, country, region, language,
        s3_key, video_url, views_seeded, likes_seeded,
        import_id, source_row_number
    )
    VALUES (
        p_external_id, p_brand_name, p_title, p_description,
        p_air_date, p_air_date_raw, p_date_parse_confidence, p_date_parse_warning,
        COALESCE(p_year, EXTRACT(YEAR FROM p_air_date)::int), v_decade,
        p_country, p_region, p_language,
        p_s3_key, p_video_url, p_views_seeded, p_likes_seeded,
        p_import_id, p_source_row_number
    )
    ON CONFLICT (external_id)
    DO UPDATE SET
        brand_name = COALESCE(EXCLUDED.brand_name, ad_catalog.brand_name),
        title = COALESCE(EXCLUDED.title, ad_catalog.title),
        description = COALESCE(EXCLUDED.description, ad_catalog.description),
        air_date = COALESCE(EXCLUDED.air_date, ad_catalog.air_date),
        air_date_raw = COALESCE(EXCLUDED.air_date_raw, ad_catalog.air_date_raw),
        date_parse_confidence = CASE
            WHEN EXCLUDED.air_date IS NOT NULL THEN EXCLUDED.date_parse_confidence
            ELSE ad_catalog.date_parse_confidence
        END,
        date_parse_warning = CASE
            WHEN EXCLUDED.air_date IS NOT NULL THEN EXCLUDED.date_parse_warning
            ELSE ad_catalog.date_parse_warning
        END,
        year = COALESCE(EXCLUDED.year, ad_catalog.year),
        decade = COALESCE(
            CASE WHEN EXCLUDED.year IS NOT NULL THEN (FLOOR(EXCLUDED.year / 10) * 10)::text || 's' END,
            ad_catalog.decade
        ),
        country = COALESCE(EXCLUDED.country, ad_catalog.country),
        region = COALESCE(EXCLUDED.region, ad_catalog.region),
        language = COALESCE(EXCLUDED.language, ad_catalog.language),
        s3_key = COALESCE(EXCLUDED.s3_key, ad_catalog.s3_key),
        video_url = COALESCE(EXCLUDED.video_url, ad_catalog.video_url),
        views_seeded = CASE
            WHEN EXCLUDED.views_seeded > 0 THEN EXCLUDED.views_seeded
            ELSE ad_catalog.views_seeded
        END,
        likes_seeded = CASE
            WHEN EXCLUDED.likes_seeded > 0 THEN EXCLUDED.likes_seeded
            ELSE ad_catalog.likes_seeded
        END,
        import_id = COALESCE(EXCLUDED.import_id, ad_catalog.import_id),
        source_row_number = COALESCE(EXCLUDED.source_row_number, ad_catalog.source_row_number)
    RETURNING id, (xmax = 0) INTO v_id, v_created;

    RETURN QUERY SELECT v_id, v_created;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Comments
-- ============================================================================
COMMENT ON TABLE ad_catalog_imports IS
'Tracks CSV catalog import jobs. Status flows: UPLOADED -> PROCESSING -> SUCCEEDED/FAILED';

COMMENT ON TABLE ad_catalog IS
'Master catalog of all known ads, imported from CSV. Links to ads table once processed.';

COMMENT ON COLUMN ad_catalog.date_parse_confidence IS
'Confidence score for date parsing. 1.0 = unambiguous, <0.8 = possibly wrong (dd/mm vs mm/dd ambiguity)';

COMMENT ON COLUMN ad_catalog.date_parse_warning IS
'Warning message if date was ambiguous (e.g., "Assumed DD/MM format for 01/02/1995")';

COMMENT ON FUNCTION upsert_catalog_entry IS
'Idempotent catalog entry creation/update. Returns catalog_id and whether a new row was created.';
