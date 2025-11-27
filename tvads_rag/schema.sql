-- TV Ads RAG Supabase schema
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Ads master table
CREATE TABLE IF NOT EXISTS ads (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id text,
    s3_key text,
    duration_seconds numeric,
    width integer,
    height integer,
    aspect_ratio text,
    fps numeric,
    brand_name text,
    product_name text,
    product_category text,
    product_subcategory text,
    country text,
    region text,
    language text,
    year integer,
    objective text,
    funnel_stage text,
    primary_kpi text,
    format_type text,
    primary_setting text,
    has_voiceover boolean,
    has_dialogue boolean,
    has_on_screen_text boolean,
    has_celeb boolean,
    has_ugc_style boolean,
    music_style text,
    editing_pace text,
    colour_mood text,
    overall_structure text,
    one_line_summary text,
    story_summary text,
    has_supers boolean,
    has_price_claims boolean,
    has_risk_disclaimer boolean,
    regulator_sensitive boolean,
    performance_metrics jsonb DEFAULT '{}'::jsonb,
    hero_analysis jsonb,
    raw_transcript jsonb,
    analysis_json jsonb,
    -- Extended extraction fields (Nov 2025)
    cta_offer jsonb,
    brand_asset_timeline jsonb,
    audio_fingerprint jsonb,
    creative_dna jsonb,
    claims_compliance jsonb,
    -- Extraction v2.0 fields (Nov 2025)
    impact_scores jsonb,         -- Pulse, Echo, Hook Power, Brand Integration, Emotional Resonance, Clarity, Distinctiveness
    emotional_metrics jsonb,     -- emotional_timeline, brain_balance, attention_dynamics
    effectiveness jsonb,         -- effectiveness_drivers, memorability, competitive_context
    extraction_version text DEFAULT '1.0',  -- Track which extraction schema was used
    processing_notes jsonb,      -- Track any issues during ingestion (safety blocks, timeouts, etc.)
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ads_external_id ON ads (external_id) WHERE external_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ads_s3_key ON ads (s3_key) WHERE s3_key IS NOT NULL;

-- Prevent duplicate ads (same external_id)
CREATE UNIQUE INDEX IF NOT EXISTS idx_ads_external_id_unique ON ads (external_id) WHERE external_id IS NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ads' AND column_name = 'performance_metrics'
    ) THEN
        ALTER TABLE ads ADD COLUMN performance_metrics jsonb DEFAULT '{}'::jsonb;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ads' AND column_name = 'hero_analysis'
    ) THEN
        ALTER TABLE ads ADD COLUMN hero_analysis jsonb;
    END IF;

    -- Extended extraction fields (Nov 2025)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ads' AND column_name = 'cta_offer'
    ) THEN
        ALTER TABLE ads ADD COLUMN cta_offer jsonb;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ads' AND column_name = 'brand_asset_timeline'
    ) THEN
        ALTER TABLE ads ADD COLUMN brand_asset_timeline jsonb;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ads' AND column_name = 'audio_fingerprint'
    ) THEN
        ALTER TABLE ads ADD COLUMN audio_fingerprint jsonb;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ads' AND column_name = 'creative_dna'
    ) THEN
        ALTER TABLE ads ADD COLUMN creative_dna jsonb;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ads' AND column_name = 'claims_compliance'
    ) THEN
        ALTER TABLE ads ADD COLUMN claims_compliance jsonb;
    END IF;

    -- Extraction v2.0 columns (Nov 2025)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ads' AND column_name = 'impact_scores'
    ) THEN
        ALTER TABLE ads ADD COLUMN impact_scores jsonb;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ads' AND column_name = 'emotional_metrics'
    ) THEN
        ALTER TABLE ads ADD COLUMN emotional_metrics jsonb;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ads' AND column_name = 'effectiveness'
    ) THEN
        ALTER TABLE ads ADD COLUMN effectiveness jsonb;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ads' AND column_name = 'extraction_version'
    ) THEN
        ALTER TABLE ads ADD COLUMN extraction_version text DEFAULT '1.0';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ads' AND column_name = 'processing_notes'
    ) THEN
        ALTER TABLE ads ADD COLUMN processing_notes jsonb;
    END IF;
END;
$$;

-- Segments
CREATE TABLE IF NOT EXISTS ad_segments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id uuid NOT NULL REFERENCES ads(id) ON DELETE CASCADE,
    segment_type text,
    aida_stage text,
    emotion_focus text,
    start_time numeric,
    end_time numeric,
    transcript_text text,
    summary text
);

CREATE INDEX IF NOT EXISTS idx_ad_segments_ad_id ON ad_segments(ad_id);

-- Chunks
CREATE TABLE IF NOT EXISTS ad_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id uuid NOT NULL REFERENCES ads(id) ON DELETE CASCADE,
    chunk_index integer,
    start_time numeric,
    end_time numeric,
    text text,
    aida_stage text,
    tags text[] DEFAULT '{}'::text[]
);

CREATE INDEX IF NOT EXISTS idx_ad_chunks_ad_id ON ad_chunks(ad_id);

-- Claims
CREATE TABLE IF NOT EXISTS ad_claims (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id uuid NOT NULL REFERENCES ads(id) ON DELETE CASCADE,
    text text,
    claim_type text,
    is_comparative boolean,
    likely_needs_substantiation boolean
);

CREATE INDEX IF NOT EXISTS idx_ad_claims_ad_id ON ad_claims(ad_id);

-- Supers
CREATE TABLE IF NOT EXISTS ad_supers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id uuid NOT NULL REFERENCES ads(id) ON DELETE CASCADE,
    start_time numeric,
    end_time numeric,
    text text,
    super_type text
);

CREATE INDEX IF NOT EXISTS idx_ad_supers_ad_id ON ad_supers(ad_id);

-- Storyboard shots
CREATE TABLE IF NOT EXISTS ad_storyboards (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id uuid NOT NULL REFERENCES ads(id) ON DELETE CASCADE,
    shot_index integer,
    start_time numeric,
    end_time numeric,
    shot_label text,
    description text,
    camera_style text,
    location_hint text,
    key_objects text[],
    on_screen_text text,
    mood text,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ad_storyboards_ad_id ON ad_storyboards(ad_id);

-- Embedding items
CREATE TABLE IF NOT EXISTS embedding_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id uuid NOT NULL REFERENCES ads(id) ON DELETE CASCADE,
    chunk_id uuid REFERENCES ad_chunks(id) ON DELETE SET NULL,
    segment_id uuid REFERENCES ad_segments(id) ON DELETE SET NULL,
    claim_id uuid REFERENCES ad_claims(id) ON DELETE SET NULL,
    super_id uuid REFERENCES ad_supers(id) ON DELETE SET NULL,
    storyboard_id uuid REFERENCES ad_storyboards(id) ON DELETE SET NULL,
    item_type text NOT NULL,
    text text NOT NULL,
    embedding vector(1536) NOT NULL,
    meta jsonb DEFAULT '{}'::jsonb,
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(text, ''))
    ) STORED,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_embedding_items_ad_id ON embedding_items(ad_id);
CREATE INDEX IF NOT EXISTS idx_embedding_items_item_type ON embedding_items(item_type);
CREATE INDEX IF NOT EXISTS idx_embedding_items_meta ON embedding_items USING gin(meta);
CREATE INDEX IF NOT EXISTS idx_embedding_items_search_vector ON embedding_items USING gin(search_vector);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'embedding_items'
          AND column_name = 'search_vector'
    ) THEN
        EXECUTE $ddl$
            ALTER TABLE embedding_items
            ADD COLUMN search_vector tsvector GENERATED ALWAYS AS (
                to_tsvector('english', coalesce(text, ''))
            ) STORED
        $ddl$;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION match_embedding_items_hybrid(
    query_embedding vector(1536),
    query_text text,
    limit_count integer DEFAULT 50,
    item_types text[] DEFAULT ARRAY[
        'transcript_chunk',
        'segment_summary',
        'claim',
        'super',
        'storyboard_shot',
        'ad_summary',
        'implied_claim',
        'cta_offer',
        'creative_dna',
        'impact_summary',
        'memorable_elements',
        'emotional_peaks',
        'distinctive_assets',
        'effectiveness_insight'
    ]
)
RETURNS TABLE (
    embedding_id uuid,
    ad_id uuid,
    item_type text,
    text text,
    meta jsonb,
    brand_name text,
    product_name text,
    one_line_summary text,
    format_type text,
    hero_analysis jsonb,
    performance_metrics jsonb,
    rrf_score double precision,
    semantic_rank integer,
    lexical_rank integer
)
LANGUAGE sql
STABLE
AS $$
WITH params AS (
    SELECT
        query_embedding AS q_embedding,
        GREATEST(COALESCE(limit_count, 50), 1) AS q_limit,
        COALESCE(NULLIF(trim(query_text), ''), NULL) AS q_text,
        CASE
            WHEN item_types IS NULL OR array_length(item_types, 1) IS NULL THEN ARRAY[
                'transcript_chunk',
                'segment_summary',
                'claim',
                'super',
                'storyboard_shot',
                'ad_summary',
                'implied_claim',
                'cta_offer',
                'creative_dna',
                'impact_summary',
                'memorable_elements',
                'emotional_peaks',
                'distinctive_assets',
                'effectiveness_insight'
            ]
            ELSE item_types
        END AS q_types
),
semantic AS (
    SELECT
        ei.id,
        ei.ad_id,
        ei.item_type,
        ei.text,
        ei.meta,
        ROW_NUMBER() OVER (ORDER BY ei.embedding <-> params.q_embedding) AS rank_sem
    FROM params
    JOIN embedding_items ei ON ei.item_type = ANY(params.q_types)
),
semantic_trim AS (
    SELECT s.* FROM semantic s
    CROSS JOIN params p
    WHERE s.rank_sem <= p.q_limit * 4
),
lexical AS (
    SELECT
        ei.id,
        ei.ad_id,
        ei.item_type,
        ei.text,
        ei.meta,
        ROW_NUMBER() OVER (ORDER BY ts_rank_cd(ei.search_vector, ts.ts_query) DESC) AS rank_lex
    FROM params
    JOIN LATERAL (
        SELECT websearch_to_tsquery('english', params.q_text) AS ts_query
    ) ts ON params.q_text IS NOT NULL
    JOIN embedding_items ei ON ei.item_type = ANY(params.q_types)
    WHERE params.q_text IS NOT NULL
      AND ts.ts_query <> ''::tsquery
      AND ei.search_vector @@ ts.ts_query
),
lexical_trim AS (
    SELECT l.* FROM lexical l
    CROSS JOIN params p
    WHERE l.rank_lex <= p.q_limit * 4
),
rrf AS (
    SELECT
        COALESCE(semantic_trim.id, lexical_trim.id) AS embedding_id,
        COALESCE(semantic_trim.ad_id, lexical_trim.ad_id) AS ad_id,
        COALESCE(semantic_trim.item_type, lexical_trim.item_type) AS item_type,
        COALESCE(semantic_trim.text, lexical_trim.text) AS text,
        COALESCE(semantic_trim.meta, lexical_trim.meta) AS meta,
        semantic_trim.rank_sem,
        lexical_trim.rank_lex,
        COALESCE(1.0 / (60 + semantic_trim.rank_sem), 0) +
        COALESCE(1.0 / (60 + lexical_trim.rank_lex), 0) AS rrf_score
    FROM semantic_trim
    FULL OUTER JOIN lexical_trim ON semantic_trim.id = lexical_trim.id
),
ranked AS (
    SELECT
        rrf.embedding_id,
        rrf.ad_id,
        rrf.item_type,
        rrf.text,
        rrf.meta,
        ads.brand_name,
        ads.product_name,
        ads.one_line_summary,
        ads.format_type,
        ads.hero_analysis,
        ads.performance_metrics,
        rrf.rrf_score,
        rrf.rank_sem,
        rrf.rank_lex,
        ROW_NUMBER() OVER (ORDER BY rrf.rrf_score DESC) AS rn
    FROM rrf
    CROSS JOIN params p
    JOIN ads ON ads.id = rrf.ad_id
)
SELECT
    embedding_id,
    ad_id,
    item_type,
    text,
    meta,
    brand_name,
    product_name,
    one_line_summary,
    format_type,
    hero_analysis,
    performance_metrics,
    rrf_score,
    rank_sem,
    rank_lex
FROM ranked
CROSS JOIN params p2
WHERE rn <= p2.q_limit;
$$;

-- Efficient count aggregation function for dashboard
-- Returns all ad counts in a single query instead of N+1 queries
CREATE OR REPLACE FUNCTION get_ad_counts()
RETURNS TABLE (
    ad_id uuid,
    chunk_count bigint,
    segment_count bigint,
    storyboard_count bigint,
    embedding_count bigint
)
LANGUAGE sql
STABLE
AS $$
SELECT 
    a.id as ad_id,
    COALESCE(c.cnt, 0) as chunk_count,
    COALESCE(s.cnt, 0) as segment_count,
    COALESCE(sb.cnt, 0) as storyboard_count,
    COALESCE(e.cnt, 0) as embedding_count
FROM ads a
LEFT JOIN (SELECT ad_id, COUNT(*) as cnt FROM ad_chunks GROUP BY ad_id) c ON c.ad_id = a.id
LEFT JOIN (SELECT ad_id, COUNT(*) as cnt FROM ad_segments GROUP BY ad_id) s ON s.ad_id = a.id
LEFT JOIN (SELECT ad_id, COUNT(*) as cnt FROM ad_storyboards GROUP BY ad_id) sb ON sb.ad_id = a.id
LEFT JOIN (SELECT ad_id, COUNT(*) as cnt FROM embedding_items GROUP BY ad_id) e ON e.ad_id = a.id;
$$;

