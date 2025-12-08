# Job Queue Verification Checklist

This document provides manual verification steps for the DB-backed ingestion job queue.

## Prerequisites

1. **Apply the migrations:**
   ```bash
   psql "$SUPABASE_DB_URL" -f tvads_rag/migrations/003_ingestion_jobs.sql
   psql "$SUPABASE_DB_URL" -f tvads_rag/migrations/004_job_queue_heartbeat.sql
   ```

2. **Verify table exists with all columns:**
   ```sql
   SELECT column_name, data_type
   FROM information_schema.columns
   WHERE table_name = 'ingestion_jobs'
   ORDER BY ordinal_position;
   ```

   Expected columns include:
   - `id`, `status`, `priority`, `attempts`, `max_attempts`
   - `locked_at`, `locked_by`, `run_after`
   - `processing_started_at`, `processing_completed_at`  (from 004)
   - `last_heartbeat_at`, `stage`, `progress`  (from 004)
   - `input`, `output`, `idempotency_key`

3. **Verify functions exist:**
   ```sql
   SELECT routine_name
   FROM information_schema.routines
   WHERE routine_schema = 'public'
     AND routine_name IN (
       'claim_jobs', 'enqueue_job', 'complete_job', 'fail_job',
       'cancel_job', 'release_stale_jobs', 'update_job_heartbeat'
     );
   ```

4. **Verify views exist:**
   ```sql
   SELECT table_name
   FROM information_schema.views
   WHERE table_schema = 'public'
     AND table_name IN (
       'dead_letter_jobs', 'job_queue_stats',
       'running_jobs_monitor', 'job_timing_stats', 'stage_distribution'
     );
   ```

3. **Set environment variables:**
   ```bash
   export SUPABASE_DB_URL="postgresql://..."
   export ADMIN_API_KEY="your-admin-key"
   export OPENAI_API_KEY="sk-..."
   export GOOGLE_API_KEY="..."  # Optional
   ```

---

## Test 1: Create a Job via API

### Step 1.1: Enqueue a job
```bash
curl -X POST http://localhost:3000/api/ingest/enqueue \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -d '{"source_type": "s3", "s3_key": "videos/test-ad.mp4"}'
```

Expected response:
```json
{
  "job_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "status": "QUEUED",
  "already_existed": false
}
```

### Step 1.2: Verify idempotency (duplicate enqueue)
```bash
curl -X POST http://localhost:3000/api/ingest/enqueue \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -d '{"source_type": "s3", "s3_key": "videos/test-ad.mp4"}'
```

Expected: Same `job_id` with `already_existed: true`

### Step 1.3: List jobs
```bash
curl http://localhost:3000/api/ingest/jobs?stats=true \
  -H "X-Admin-Key: $ADMIN_API_KEY"
```

---

## Test 2: Run Worker Locally

### Step 2.1: Start worker (single batch)
```bash
cd tvads_rag
python -m tvads_rag.worker --once --limit 1
```

Expected output:
```
TellyAds RAG Worker Starting
Database: postgresql://...
Worker ID: hostname-12345-abc123
Pipeline initialized with 9 stages
Worker ready - starting poll loop
Processing job xxxxxxxx... (attempt 1/5): s3:videos/test-ad.mp4
Job xxxxxxxx succeeded in 45.2s: ad_id=yyyy...
Jobs processed: 1
Jobs succeeded: 1
Jobs failed: 0
```

### Step 2.2: Verify job status changed
```bash
curl http://localhost:3000/api/ingest/jobs/JOB_ID_HERE \
  -H "X-Admin-Key: $ADMIN_API_KEY"
```

Expected: `status: "SUCCEEDED"`, `output` contains `ad_id`

---

## Test 3: Transient Error and Retry

### Step 3.1: Create a job that will fail transiently
```bash
# Create job with invalid S3 key that will fail on video load
curl -X POST http://localhost:3000/api/ingest/enqueue \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -d '{"source_type": "s3", "s3_key": "nonexistent/fake-video.mp4"}'
```

### Step 3.2: Run worker
```bash
python -m tvads_rag.worker --once --limit 1
```

### Step 3.3: Verify job status
```bash
curl http://localhost:3000/api/ingest/jobs/JOB_ID_HERE \
  -H "X-Admin-Key: $ADMIN_API_KEY"
```

Expected:
- First attempt: `status: "RETRY"`, `attempts: 1`, `run_after` in future
- After max attempts: `status: "FAILED"`, `attempts: 5`

---

## Test 4: Concurrent Workers

### Step 4.1: Create multiple jobs
```bash
for i in {1..5}; do
  curl -X POST http://localhost:3000/api/ingest/enqueue \
    -H "Content-Type: application/json" \
    -H "X-Admin-Key: $ADMIN_API_KEY" \
    -d "{\"source_type\": \"s3\", \"s3_key\": \"videos/test-$i.mp4\"}"
done
```

### Step 4.2: Start two workers in parallel
```bash
# Terminal 1
python -m tvads_rag.worker --limit 1 --poll-interval 2 &

# Terminal 2
python -m tvads_rag.worker --limit 1 --poll-interval 2 &
```

### Step 4.3: Verify no double-processing
```bash
# Check that each job is processed exactly once
curl "http://localhost:3000/api/ingest/jobs?limit=10" \
  -H "X-Admin-Key: $ADMIN_API_KEY" | jq '.jobs[] | {id, attempts, locked_by}'
```

Expected: Each job should have `attempts: 1` (unless it failed and retried)

### Step 4.4: Verify different lock owners
```sql
-- In psql, check that jobs were locked by different workers
SELECT id, locked_by, status
FROM ingestion_jobs
WHERE status = 'SUCCEEDED'
ORDER BY completed_at DESC
LIMIT 10;
```

---

## Test 5: Stale Job Release

### Step 5.1: Simulate crashed worker
```sql
-- Manually set a job to RUNNING with old locked_at
UPDATE ingestion_jobs
SET status = 'RUNNING', locked_at = NOW() - INTERVAL '1 hour', locked_by = 'crashed-worker'
WHERE id = 'JOB_ID_HERE';
```

### Step 5.2: Release stale jobs
```bash
python -m tvads_rag.worker --release-stale
```

Expected: "Released 1 stale jobs"

### Step 5.3: Verify job is now RETRY
```bash
curl http://localhost:3000/api/ingest/jobs/JOB_ID_HERE \
  -H "X-Admin-Key: $ADMIN_API_KEY"
```

Expected: `status: "RETRY"`, `last_error` contains "worker timed out"

---

## Test 6: Job Actions (Cancel/Retry)

### Step 6.1: Cancel a queued job
```bash
# Create a new job
JOB_ID=$(curl -s -X POST http://localhost:3000/api/ingest/enqueue \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -d '{"source_type": "s3", "s3_key": "videos/to-cancel.mp4"}' | jq -r '.job_id')

# Cancel it
curl -X POST "http://localhost:3000/api/ingest/jobs/$JOB_ID" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -d '{"action": "cancel"}'
```

Expected: `success: true`, `message: "Job cancelled successfully"`

### Step 6.2: Retry a failed job
```bash
# Find a failed job
FAILED_ID=$(curl -s "http://localhost:3000/api/ingest/jobs?status=FAILED" \
  -H "X-Admin-Key: $ADMIN_API_KEY" | jq -r '.jobs[0].id')

# Retry it
curl -X POST "http://localhost:3000/api/ingest/jobs/$FAILED_ID" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -d '{"action": "retry"}'
```

Expected: `success: true`, job status changes to "QUEUED"

---

## Test 7: Queue Stats

```bash
curl http://localhost:3000/api/ingest/stats \
  -H "X-Admin-Key: $ADMIN_API_KEY"
```

Expected response:
```json
{
  "stats": {
    "by_status": {
      "QUEUED": 2,
      "RUNNING": 0,
      "SUCCEEDED": 10,
      "FAILED": 1,
      "RETRY": 0
    },
    "total": 13
  },
  "health": "degraded",
  "summary": {
    "running": 0,
    "pending": 2,
    "failed": 1,
    "has_dead_letter": true
  }
}
```

---

## Test 8: Run Python Tests

```bash
cd tvads_rag
pytest tests/test_job_queue.py -v
```

Expected: All tests pass

---

## Test 9: Run Frontend Tests

```bash
cd frontend
npm test -- lib/__tests__/job-queue.test.ts
```

Expected: All tests pass

---

## Cleanup

```sql
-- Remove test jobs
DELETE FROM ingestion_jobs WHERE input->>'s3_key' LIKE 'videos/test%';
DELETE FROM ingestion_jobs WHERE input->>'s3_key' LIKE '%fake-video%';
DELETE FROM ingestion_jobs WHERE input->>'s3_key' LIKE '%to-cancel%';
```

---

## Troubleshooting

### Worker can't connect to database
- Verify `SUPABASE_DB_URL` is set correctly
- Check firewall rules allow connection to Supabase

### Jobs stuck in RUNNING
- Run `python -m tvads_rag.worker --release-stale`
- Check if worker crashed (view logs)

### Duplicate jobs being processed
- Verify idempotency key is computed consistently
- Check for race conditions in enqueue logic

### High failure rate
- Check `last_error` and `error_code` in failed jobs
- Review API key validity
- Check S3 bucket permissions

---

## Production Monitoring SQL

### View currently running jobs with stage and progress
```sql
SELECT * FROM running_jobs_monitor;
```

Example output:
```
id                                   | stage          | progress | running_seconds | heartbeat_age_seconds
-------------------------------------+----------------+----------+-----------------+----------------------
abc123...                            | llm_analysis   | 0.45     | 120             | 5
def456...                            | transcription  | 0.30     | 60              | 2
```

### View job timing statistics
```sql
SELECT * FROM job_timing_stats;
```

Example output:
```
status    | count | avg_duration_seconds | p50_seconds | p95_seconds
----------+-------+---------------------+-------------+------------
SUCCEEDED | 150   | 45                  | 40          | 90
FAILED    | 5     | 30                  | 25          | 60
```

### View stage distribution (identify bottlenecks)
```sql
SELECT * FROM stage_distribution;
```

### Find jobs stuck without heartbeat
```sql
SELECT id, stage, last_heartbeat_at,
       EXTRACT(EPOCH FROM (NOW() - last_heartbeat_at))::int as heartbeat_age_seconds
FROM ingestion_jobs
WHERE status = 'RUNNING'
  AND last_heartbeat_at < NOW() - INTERVAL '5 minutes'
ORDER BY last_heartbeat_at ASC;
```

### View dead letter jobs (failed after max retries)
```sql
SELECT * FROM dead_letter_jobs LIMIT 10;
```

### Inspect a specific job's full history
```sql
SELECT
    id,
    status,
    stage,
    progress,
    attempts,
    max_attempts,
    created_at,
    processing_started_at,
    processing_completed_at,
    EXTRACT(EPOCH FROM (processing_completed_at - processing_started_at))::int as duration_seconds,
    last_error,
    error_code,
    input,
    output
FROM ingestion_jobs
WHERE id = 'JOB_ID_HERE';
```

---

## Test 10: Verify Heartbeat Updates

### Step 10.1: Start worker and watch heartbeats
```bash
# In terminal 1: Start worker
python -m tvads_rag.worker --limit 1 --poll-interval 5

# In terminal 2: Watch heartbeats
watch -n 2 "psql \$SUPABASE_DB_URL -c \"SELECT id, stage, progress,
  EXTRACT(EPOCH FROM (NOW() - last_heartbeat_at))::int as heartbeat_age
  FROM ingestion_jobs WHERE status='RUNNING'\""
```

Expected: `heartbeat_age` should stay < 30 seconds while job is processing

### Step 10.2: Verify stage transitions
```bash
# While a job is processing, query stages
psql "$SUPABASE_DB_URL" -c "
  SELECT stage, COUNT(*)
  FROM ingestion_jobs
  WHERE status IN ('RUNNING', 'SUCCEEDED')
  GROUP BY stage
"
```

Expected stages: `claimed` → `validating_input` → `pipeline_running` → `succeeded`

---

## Test 11: Heartbeat-Based Stale Recovery

### Step 11.1: Simulate stuck job (no heartbeat)
```sql
-- Set job to RUNNING with stale heartbeat
UPDATE ingestion_jobs
SET
    status = 'RUNNING',
    locked_at = NOW() - INTERVAL '10 minutes',
    locked_by = 'crashed-worker',
    last_heartbeat_at = NOW() - INTERVAL '10 minutes',
    stage = 'llm_analysis'
WHERE id = 'JOB_ID_HERE';
```

### Step 11.2: Release stale jobs (using heartbeat)
```bash
python -m tvads_rag.worker --release-stale
```

### Step 11.3: Verify job was released based on heartbeat
```sql
SELECT id, status, stage, last_error, error_code
FROM ingestion_jobs
WHERE id = 'JOB_ID_HERE';
```

Expected:
- `status`: `RETRY`
- `stage`: `released_stale`
- `error_code`: `HEARTBEAT_TIMEOUT`

---

## Test 12: Show Running Jobs CLI

```bash
python -m tvads_rag.worker --show-running
```

Expected output:
```
Running jobs: 2
  abc123...: stage=llm_analysis progress=60% running=120s heartbeat_age=5s
  def456...: stage=transcription progress=30% running=60s heartbeat_age=2s
```

---

## Test 13: Concurrency Control

### Step 13.1: Start worker with concurrency limit
```bash
# Start worker with concurrency=2
python -m tvads_rag.worker --concurrency 2 --limit 5
```

### Step 13.2: Enqueue multiple jobs
```bash
for i in {1..5}; do
  curl -X POST http://localhost:3000/api/ingest/enqueue \
    -H "Content-Type: application/json" \
    -H "X-Admin-Key: $ADMIN_API_KEY" \
    -d "{\"source_type\": \"s3\", \"s3_key\": \"videos/concurrent-$i.mp4\"}"
done
```

### Step 13.3: Verify max 2 jobs running at once
```sql
SELECT COUNT(*) as running_count
FROM ingestion_jobs
WHERE status = 'RUNNING';
```

Expected: Never more than 2 jobs running simultaneously
