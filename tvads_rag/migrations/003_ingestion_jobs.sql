-- Ingestion Jobs Schema Migration
-- DB-backed job queue for TellyAds RAG ingestion pipeline
-- Supports atomic claiming with SKIP LOCKED for multiple workers

-- ============================================================================
-- Table: ingestion_jobs
-- ============================================================================
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    -- Primary key
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Timestamps
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz,

    -- Job state machine: QUEUED -> RUNNING -> SUCCEEDED/FAILED/RETRY
    status text NOT NULL DEFAULT 'QUEUED'
        CHECK (status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'RETRY')),

    -- Scheduling
    priority int NOT NULL DEFAULT 0,  -- Higher = more urgent
    attempts int NOT NULL DEFAULT 0,
    max_attempts int NOT NULL DEFAULT 5,
    locked_at timestamptz,
    locked_by text,  -- Worker instance ID for debugging
    run_after timestamptz NOT NULL DEFAULT now(),  -- For backoff scheduling

    -- Error tracking
    last_error text,
    error_code text,  -- Structured error classification

    -- Job payload
    input jsonb NOT NULL,  -- { source_type, s3_key, url, external_id, metadata }
    output jsonb,  -- { ad_id, warnings, extraction_version, already_existed }

    -- Idempotency: stable hash to prevent duplicates
    idempotency_key text NOT NULL UNIQUE,

    -- Optional: link to ad once created
    ad_id uuid REFERENCES ads(id) ON DELETE SET NULL
);

-- ============================================================================
-- Indexes for efficient job claiming
-- ============================================================================

-- Primary claiming index: status + priority + run_after + created_at
-- Used by: SELECT ... WHERE status IN ('QUEUED','RETRY') AND run_after <= now()
--          ORDER BY priority DESC, created_at ASC FOR UPDATE SKIP LOCKED
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_claimable
    ON ingestion_jobs (status, priority DESC, run_after, created_at)
    WHERE status IN ('QUEUED', 'RETRY');

-- Admin dashboard queries
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status
    ON ingestion_jobs (status, created_at DESC);

-- Lookup by ad_id (find job that created an ad)
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_ad_id
    ON ingestion_jobs (ad_id)
    WHERE ad_id IS NOT NULL;

-- Idempotency key is already unique (implicit index)

-- ============================================================================
-- Trigger: auto-update updated_at
-- ============================================================================
CREATE OR REPLACE FUNCTION update_ingestion_jobs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_ingestion_jobs_updated_at ON ingestion_jobs;
CREATE TRIGGER trigger_ingestion_jobs_updated_at
    BEFORE UPDATE ON ingestion_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_ingestion_jobs_updated_at();

-- ============================================================================
-- View: dead_letter_jobs (failed jobs that exceeded max_attempts)
-- ============================================================================
CREATE OR REPLACE VIEW dead_letter_jobs AS
SELECT
    id,
    created_at,
    updated_at,
    attempts,
    max_attempts,
    last_error,
    error_code,
    input,
    idempotency_key
FROM ingestion_jobs
WHERE status = 'FAILED' AND attempts >= max_attempts
ORDER BY updated_at DESC;

-- ============================================================================
-- View: job_queue_stats (dashboard metrics)
-- ============================================================================
CREATE OR REPLACE VIEW job_queue_stats AS
SELECT
    status,
    COUNT(*) as count,
    AVG(attempts) as avg_attempts,
    MIN(created_at) as oldest,
    MAX(created_at) as newest
FROM ingestion_jobs
GROUP BY status
ORDER BY
    CASE status
        WHEN 'RUNNING' THEN 1
        WHEN 'QUEUED' THEN 2
        WHEN 'RETRY' THEN 3
        WHEN 'FAILED' THEN 4
        WHEN 'SUCCEEDED' THEN 5
        WHEN 'CANCELLED' THEN 6
    END;

-- ============================================================================
-- Function: claim_jobs (atomic job claiming with SKIP LOCKED)
-- Returns claimed job IDs after updating their status
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
            started_at = COALESCE(started_at, now())
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
-- Function: complete_job (mark job as succeeded)
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
        locked_at = NULL,
        locked_by = NULL
    WHERE id = p_job_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Function: fail_job (mark job as failed or retry)
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
BEGIN
    -- Get current attempts
    SELECT attempts, max_attempts INTO v_attempts, v_max_attempts
    FROM ingestion_jobs WHERE id = p_job_id;

    -- Determine next status
    IF p_permanent OR v_attempts >= v_max_attempts THEN
        v_new_status := 'FAILED';
    ELSE
        v_new_status := 'RETRY';
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
        completed_at = CASE WHEN v_new_status = 'FAILED' THEN now() ELSE NULL END
    WHERE id = p_job_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Function: enqueue_job (idempotent job creation)
-- ============================================================================
CREATE OR REPLACE FUNCTION enqueue_job(
    p_input jsonb,
    p_idempotency_key text,
    p_priority int DEFAULT 0,
    p_max_attempts int DEFAULT 5
)
RETURNS TABLE (
    job_id uuid,
    status text,
    already_existed boolean
) AS $$
DECLARE
    v_job_id uuid;
    v_status text;
    v_existed boolean := false;
BEGIN
    -- Try to find existing job with same idempotency key
    SELECT id, ingestion_jobs.status INTO v_job_id, v_status
    FROM ingestion_jobs
    WHERE idempotency_key = p_idempotency_key;

    IF v_job_id IS NOT NULL THEN
        v_existed := true;
    ELSE
        -- Create new job
        INSERT INTO ingestion_jobs (input, idempotency_key, priority, max_attempts)
        VALUES (p_input, p_idempotency_key, p_priority, p_max_attempts)
        RETURNING id, ingestion_jobs.status INTO v_job_id, v_status;
    END IF;

    RETURN QUERY SELECT v_job_id, v_status, v_existed;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Function: cancel_job (mark job as cancelled)
-- ============================================================================
CREATE OR REPLACE FUNCTION cancel_job(p_job_id uuid)
RETURNS boolean AS $$
DECLARE
    v_updated boolean;
BEGIN
    UPDATE ingestion_jobs
    SET
        status = 'CANCELLED',
        completed_at = now(),
        locked_at = NULL,
        locked_by = NULL
    WHERE id = p_job_id
      AND status IN ('QUEUED', 'RETRY')
    RETURNING true INTO v_updated;

    RETURN COALESCE(v_updated, false);
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Function: release_stale_jobs (unlock jobs stuck in RUNNING)
-- Call periodically to handle crashed workers
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
            last_error = 'Released: worker timed out after ' || p_stale_threshold_minutes || ' minutes',
            error_code = 'WORKER_TIMEOUT'
        WHERE status = 'RUNNING'
          AND locked_at < now() - (p_stale_threshold_minutes || ' minutes')::interval
        RETURNING id
    )
    SELECT COUNT(*) INTO v_released FROM stale;

    RETURN v_released;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Comments
-- ============================================================================
COMMENT ON TABLE ingestion_jobs IS
'DB-backed job queue for TellyAds RAG ingestion. Supports atomic claiming with SKIP LOCKED for concurrent workers.';

COMMENT ON COLUMN ingestion_jobs.idempotency_key IS
'Stable hash of canonical input to prevent duplicate jobs. Format: sha256(source_type:s3_key) or sha256(url).';

COMMENT ON COLUMN ingestion_jobs.input IS
'Job payload: { source_type: "s3"|"url"|"local", s3_key?: string, url?: string, external_id?: string, metadata?: object }';

COMMENT ON COLUMN ingestion_jobs.output IS
'Job result: { ad_id?: uuid, warnings?: string[], extraction_version?: string, already_existed?: boolean }';

COMMENT ON FUNCTION claim_jobs IS
'Atomically claim N jobs for processing. Uses FOR UPDATE SKIP LOCKED to prevent double-claiming.';

COMMENT ON FUNCTION release_stale_jobs IS
'Release jobs stuck in RUNNING state (crashed workers). Call from a cron job every 5-10 minutes.';
