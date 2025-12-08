-- Job Queue Heartbeat & Stage Tracking Migration
-- Adds production hardening columns for observability and lease management

-- ============================================================================
-- Add new columns to ingestion_jobs
-- ============================================================================
DO $$
BEGIN
    -- Processing timestamps
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ingestion_jobs' AND column_name = 'processing_started_at'
    ) THEN
        ALTER TABLE ingestion_jobs ADD COLUMN processing_started_at timestamptz;
        COMMENT ON COLUMN ingestion_jobs.processing_started_at IS
        'Timestamp when processing actually began (first attempt)';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ingestion_jobs' AND column_name = 'processing_completed_at'
    ) THEN
        ALTER TABLE ingestion_jobs ADD COLUMN processing_completed_at timestamptz;
        COMMENT ON COLUMN ingestion_jobs.processing_completed_at IS
        'Timestamp when processing finished (success or final failure)';
    END IF;

    -- Heartbeat for lease management
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ingestion_jobs' AND column_name = 'last_heartbeat_at'
    ) THEN
        ALTER TABLE ingestion_jobs ADD COLUMN last_heartbeat_at timestamptz;
        COMMENT ON COLUMN ingestion_jobs.last_heartbeat_at IS
        'Last heartbeat from worker. Jobs with stale heartbeats can be reclaimed.';
    END IF;

    -- Current stage tracking
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ingestion_jobs' AND column_name = 'stage'
    ) THEN
        ALTER TABLE ingestion_jobs ADD COLUMN stage text;
        COMMENT ON COLUMN ingestion_jobs.stage IS
        'Current pipeline stage: claimed, video_load, transcription, llm_analysis, etc.';
    END IF;

    -- Progress tracking (0..1)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ingestion_jobs' AND column_name = 'progress'
    ) THEN
        ALTER TABLE ingestion_jobs ADD COLUMN progress float DEFAULT 0
            CHECK (progress >= 0 AND progress <= 1);
        COMMENT ON COLUMN ingestion_jobs.progress IS
        'Processing progress from 0.0 to 1.0';
    END IF;
END;
$$;

-- ============================================================================
-- Index for heartbeat-based stale job detection
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_heartbeat_stale
    ON ingestion_jobs (status, last_heartbeat_at)
    WHERE status = 'RUNNING';

-- ============================================================================
-- Update claim_jobs to set heartbeat and stage
-- ============================================================================
CREATE OR REPLACE FUNCTION claim_jobs(
    p_limit int DEFAULT 1,
    p_worker_id text DEFAULT 'worker-default'
)
RETURNS TABLE (
    job_id uuid,
    job_input jsonb,
    job_attempts int,
    job_max_attempts int,
    job_created_at timestamptz
) AS $$
BEGIN
    RETURN QUERY
    WITH claimable AS (
        SELECT id
        FROM ingestion_jobs
        WHERE status IN ('QUEUED', 'RETRY')
          AND run_after <= now()
        ORDER BY priority DESC, created_at ASC
        LIMIT p_limit
        FOR UPDATE SKIP LOCKED
    ),
    claimed AS (
        UPDATE ingestion_jobs j
        SET
            status = 'RUNNING',
            locked_at = now(),
            locked_by = p_worker_id,
            attempts = attempts + 1,
            started_at = COALESCE(started_at, now()),
            -- New: heartbeat and stage tracking
            processing_started_at = COALESCE(processing_started_at, now()),
            last_heartbeat_at = now(),
            stage = 'claimed',
            progress = 0
        FROM claimable c
        WHERE j.id = c.id
        RETURNING j.id, j.input, j.attempts, j.max_attempts, j.created_at
    )
    SELECT
        claimed.id as job_id,
        claimed.input as job_input,
        claimed.attempts as job_attempts,
        claimed.max_attempts as job_max_attempts,
        claimed.created_at as job_created_at
    FROM claimed;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Function: update_job_heartbeat (for worker to call during processing)
-- ============================================================================
CREATE OR REPLACE FUNCTION update_job_heartbeat(
    p_job_id uuid,
    p_stage text DEFAULT NULL,
    p_progress float DEFAULT NULL
)
RETURNS void AS $$
BEGIN
    UPDATE ingestion_jobs
    SET
        last_heartbeat_at = now(),
        stage = COALESCE(p_stage, stage),
        progress = COALESCE(p_progress, progress)
    WHERE id = p_job_id AND status = 'RUNNING';
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Update complete_job to set final stage and timestamps
-- ============================================================================
CREATE OR REPLACE FUNCTION complete_job(
    p_job_id uuid,
    p_output jsonb DEFAULT '{}'::jsonb,
    p_ad_id uuid DEFAULT NULL
)
RETURNS void AS $$
BEGIN
    UPDATE ingestion_jobs
    SET
        status = 'SUCCEEDED',
        output = p_output,
        ad_id = p_ad_id,
        completed_at = now(),
        processing_completed_at = now(),
        locked_at = NULL,
        locked_by = NULL,
        stage = 'succeeded',
        progress = 1.0,
        last_heartbeat_at = now()
    WHERE id = p_job_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Update fail_job to set failure stage
-- ============================================================================
CREATE OR REPLACE FUNCTION fail_job(
    p_job_id uuid,
    p_error text,
    p_error_code text DEFAULT NULL,
    p_permanent boolean DEFAULT false
)
RETURNS void AS $$
DECLARE
    v_attempts int;
    v_max_attempts int;
    v_new_status text;
    v_backoff_seconds int;
    v_new_stage text;
BEGIN
    -- Get current attempts
    SELECT attempts, max_attempts INTO v_attempts, v_max_attempts
    FROM ingestion_jobs WHERE id = p_job_id;

    -- Determine next status and stage
    IF p_permanent OR v_attempts >= v_max_attempts THEN
        v_new_status := 'FAILED';
        v_new_stage := 'failed';
    ELSE
        v_new_status := 'RETRY';
        v_new_stage := 'retrying';
    END IF;

    -- Exponential backoff with jitter: 5s, 15s, 60s, 5m, 30m (capped)
    v_backoff_seconds := LEAST(
        POWER(3, LEAST(v_attempts, 5)) * 5 + (random() * 10)::int,
        1800  -- Cap at 30 minutes
    );

    UPDATE ingestion_jobs
    SET
        status = v_new_status,
        last_error = p_error,
        error_code = p_error_code,
        run_after = CASE
            WHEN v_new_status = 'RETRY' THEN now() + (v_backoff_seconds || ' seconds')::interval
            ELSE run_after
        END,
        locked_at = NULL,
        locked_by = NULL,
        completed_at = CASE WHEN v_new_status = 'FAILED' THEN now() ELSE NULL END,
        processing_completed_at = CASE WHEN v_new_status = 'FAILED' THEN now() ELSE NULL END,
        stage = v_new_stage,
        last_heartbeat_at = now()
    WHERE id = p_job_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Update release_stale_jobs to use heartbeat (more accurate than locked_at)
-- ============================================================================
CREATE OR REPLACE FUNCTION release_stale_jobs(
    p_stale_threshold_minutes int DEFAULT 30
)
RETURNS int AS $$
DECLARE
    v_released int;
BEGIN
    WITH stale AS (
        UPDATE ingestion_jobs
        SET
            status = 'RETRY',
            locked_at = NULL,
            locked_by = NULL,
            last_error = 'Released: worker heartbeat timeout after ' || p_stale_threshold_minutes || ' minutes',
            error_code = 'HEARTBEAT_TIMEOUT',
            stage = 'released_stale',
            last_heartbeat_at = now()
        WHERE status = 'RUNNING'
          AND (
              -- Use heartbeat if available (more accurate)
              (last_heartbeat_at IS NOT NULL AND last_heartbeat_at < now() - (p_stale_threshold_minutes || ' minutes')::interval)
              OR
              -- Fall back to locked_at if no heartbeat
              (last_heartbeat_at IS NULL AND locked_at < now() - (p_stale_threshold_minutes || ' minutes')::interval)
          )
        RETURNING id
    )
    SELECT COUNT(*) INTO v_released FROM stale;

    RETURN v_released;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- View: running_jobs_monitor (for ops dashboard)
-- ============================================================================
CREATE OR REPLACE VIEW running_jobs_monitor AS
SELECT
    id,
    created_at,
    processing_started_at,
    last_heartbeat_at,
    EXTRACT(EPOCH FROM (now() - processing_started_at))::int as running_seconds,
    EXTRACT(EPOCH FROM (now() - last_heartbeat_at))::int as heartbeat_age_seconds,
    stage,
    progress,
    attempts,
    max_attempts,
    locked_by,
    input->>'s3_key' as s3_key,
    input->>'external_id' as external_id
FROM ingestion_jobs
WHERE status = 'RUNNING'
ORDER BY processing_started_at ASC;

COMMENT ON VIEW running_jobs_monitor IS
'Monitor currently running jobs with timing and progress info. Use for ops dashboards.';

-- ============================================================================
-- View: job_timing_stats (for performance analysis)
-- ============================================================================
CREATE OR REPLACE VIEW job_timing_stats AS
SELECT
    status,
    COUNT(*) as count,
    AVG(EXTRACT(EPOCH FROM (processing_completed_at - processing_started_at)))::int as avg_duration_seconds,
    MIN(EXTRACT(EPOCH FROM (processing_completed_at - processing_started_at)))::int as min_duration_seconds,
    MAX(EXTRACT(EPOCH FROM (processing_completed_at - processing_started_at)))::int as max_duration_seconds,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (processing_completed_at - processing_started_at)))::int as p50_seconds,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (processing_completed_at - processing_started_at)))::int as p95_seconds
FROM ingestion_jobs
WHERE processing_started_at IS NOT NULL
  AND processing_completed_at IS NOT NULL
GROUP BY status;

COMMENT ON VIEW job_timing_stats IS
'Job duration statistics by status. Use for performance monitoring.';

-- ============================================================================
-- View: stage_distribution (for debugging bottlenecks)
-- ============================================================================
CREATE OR REPLACE VIEW stage_distribution AS
SELECT
    stage,
    status,
    COUNT(*) as count
FROM ingestion_jobs
WHERE stage IS NOT NULL
GROUP BY stage, status
ORDER BY count DESC;

COMMENT ON VIEW stage_distribution IS
'Distribution of jobs by stage and status. Use to identify pipeline bottlenecks.';
