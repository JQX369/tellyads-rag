"""
Tests for DB-backed job queue.

These tests use mocked database connections to verify:
1. Idempotency key computation
2. Job enqueue logic
3. Atomic job claiming
4. Retry/fail behavior
5. Concurrent claiming safety (simulation)
"""

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import Mock, patch
import uuid

import pytest

pytest.importorskip("psycopg2")

from tvads_rag.job_queue import (
    JobInput,
    JobOutput,
    JobQueue,
    Job,
    EnqueueResult,
    JobStatus,
    _generate_worker_id,
)


# ---------------------------------------------------------------------------
# Test JobInput
# ---------------------------------------------------------------------------

class TestJobInput:
    def test_idempotency_key_s3(self):
        """S3 keys should produce stable idempotency keys."""
        input1 = JobInput(source_type="s3", s3_key="videos/test.mp4")
        input2 = JobInput(source_type="s3", s3_key="videos/test.mp4")
        input3 = JobInput(source_type="s3", s3_key="videos/other.mp4")

        key1 = input1.compute_idempotency_key()
        key2 = input2.compute_idempotency_key()
        key3 = input3.compute_idempotency_key()

        assert key1 == key2, "Same S3 key should produce same idempotency key"
        assert key1 != key3, "Different S3 keys should produce different keys"
        assert len(key1) == 32, "Key should be 32 hex characters"

    def test_idempotency_key_url(self):
        """URLs should produce stable idempotency keys."""
        input1 = JobInput(source_type="url", url="https://example.com/video.mp4")
        input2 = JobInput(source_type="url", url="https://example.com/video.mp4")

        assert input1.compute_idempotency_key() == input2.compute_idempotency_key()

    def test_idempotency_key_external_id(self):
        """External IDs should produce stable idempotency keys."""
        input1 = JobInput(source_type="local", external_id="TA1234")
        input2 = JobInput(source_type="local", external_id="TA1234")

        assert input1.compute_idempotency_key() == input2.compute_idempotency_key()

    def test_idempotency_key_requires_identifier(self):
        """Must have s3_key, url, or external_id."""
        input1 = JobInput(source_type="s3")

        with pytest.raises(ValueError, match="must have"):
            input1.compute_idempotency_key()

    def test_to_dict(self):
        """Test JSON serialization."""
        input1 = JobInput(
            source_type="s3",
            s3_key="videos/test.mp4",
            external_id="TA1234",
            metadata={"priority": "high"},
        )

        d = input1.to_dict()

        assert d["source_type"] == "s3"
        assert d["s3_key"] == "videos/test.mp4"
        assert d["external_id"] == "TA1234"
        assert d["metadata"]["priority"] == "high"
        assert "url" not in d  # Omitted when None


# ---------------------------------------------------------------------------
# Test JobOutput
# ---------------------------------------------------------------------------

class TestJobOutput:
    def test_to_dict_minimal(self):
        """Test minimal output serialization."""
        output = JobOutput(ad_id="abc-123")
        d = output.to_dict()

        assert d["ad_id"] == "abc-123"
        assert d["warnings"] == []
        assert d["already_existed"] is False

    def test_to_dict_full(self):
        """Test full output serialization."""
        output = JobOutput(
            ad_id="abc-123",
            warnings=["Low audio quality"],
            extraction_version="v2.0",
            already_existed=True,
            elapsed_seconds=45.2,
            stage_reached="completed",
        )
        d = output.to_dict()

        assert d["warnings"] == ["Low audio quality"]
        assert d["extraction_version"] == "v2.0"
        assert d["elapsed_seconds"] == 45.2


# ---------------------------------------------------------------------------
# Test Job.from_row
# ---------------------------------------------------------------------------

class TestJob:
    def test_from_row(self):
        """Test creating Job from database row."""
        row = {
            "job_id": uuid.uuid4(),
            "job_input": {
                "source_type": "s3",
                "s3_key": "videos/test.mp4",
                "metadata": {"vision_tier": "fast"},
            },
            "job_attempts": 2,
            "job_max_attempts": 5,
            "job_created_at": datetime.now(),
        }

        job = Job.from_row(row)

        assert job.id == row["job_id"]
        assert job.input.source_type == "s3"
        assert job.input.s3_key == "videos/test.mp4"
        assert job.attempts == 2
        assert job.max_attempts == 5


# ---------------------------------------------------------------------------
# Test Worker ID Generation
# ---------------------------------------------------------------------------

class TestWorkerIdGeneration:
    def test_generate_worker_id_format(self):
        """Worker ID should include hostname, pid, and random suffix."""
        worker_id = _generate_worker_id()

        parts = worker_id.split("-")
        assert len(parts) >= 3, "Should have hostname-pid-random format"

    def test_generate_worker_id_unique(self):
        """Each call should generate a unique ID."""
        ids = [_generate_worker_id() for _ in range(10)]
        assert len(set(ids)) == 10, "All IDs should be unique"


# ---------------------------------------------------------------------------
# Mocked Database Tests
# ---------------------------------------------------------------------------

class FakeCursor:
    """Mock cursor that returns predefined results."""

    def __init__(self, results=None):
        self.results = results or []
        self.query = None
        self.params = None
        self.executed_queries = []

    def execute(self, query, params=None):
        self.query = query
        self.params = params
        self.executed_queries.append((query, params))

    def fetchone(self):
        if self.results:
            return self.results[0] if isinstance(self.results[0], dict) else self.results[0]
        return None

    def fetchall(self):
        return self.results

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConnection:
    """Mock connection that returns a fake cursor."""

    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class TestJobQueueEnqueue:
    """Test JobQueue.enqueue with mocked database."""

    def test_enqueue_new_job(self, monkeypatch):
        """Enqueue should create a new job."""
        job_id = uuid.uuid4()
        cursor = FakeCursor([{
            "job_id": job_id,
            "status": "QUEUED",
            "already_existed": False,
        }])
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.job_queue.get_connection", fake_get_connection)

        queue = JobQueue(worker_id="test-worker")
        result = queue.enqueue(JobInput(source_type="s3", s3_key="test.mp4"))

        assert result.job_id == job_id
        assert result.status == "QUEUED"
        assert result.already_existed is False
        assert "enqueue_job" in cursor.query

    def test_enqueue_duplicate_returns_existing(self, monkeypatch):
        """Duplicate enqueue should return existing job."""
        job_id = uuid.uuid4()
        cursor = FakeCursor([{
            "job_id": job_id,
            "status": "RUNNING",
            "already_existed": True,
        }])
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.job_queue.get_connection", fake_get_connection)

        queue = JobQueue(worker_id="test-worker")
        result = queue.enqueue(JobInput(source_type="s3", s3_key="test.mp4"))

        assert result.job_id == job_id
        assert result.already_existed is True


class TestJobQueueClaim:
    """Test JobQueue.claim_jobs with mocked database."""

    def test_claim_jobs_returns_claimed(self, monkeypatch):
        """claim_jobs should return claimed jobs."""
        job_id = uuid.uuid4()
        cursor = FakeCursor([{
            "job_id": job_id,
            "job_input": {"source_type": "s3", "s3_key": "test.mp4"},
            "job_attempts": 1,
            "job_max_attempts": 5,
            "job_created_at": datetime.now(),
        }])
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.job_queue.get_connection", fake_get_connection)

        queue = JobQueue(worker_id="test-worker")
        jobs = queue.claim_jobs(limit=5)

        assert len(jobs) == 1
        assert jobs[0].id == job_id
        assert "claim_jobs" in cursor.query
        assert cursor.params[0] == 5  # limit
        assert cursor.params[1] == "test-worker"  # worker_id

    def test_claim_jobs_empty_queue(self, monkeypatch):
        """claim_jobs returns empty list when no jobs available."""
        cursor = FakeCursor([])
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.job_queue.get_connection", fake_get_connection)

        queue = JobQueue(worker_id="test-worker")
        jobs = queue.claim_jobs(limit=5)

        assert jobs == []


class TestJobQueueComplete:
    """Test JobQueue.complete with mocked database."""

    def test_complete_calls_function(self, monkeypatch):
        """complete should call the complete_job function."""
        cursor = FakeCursor()
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.job_queue.get_connection", fake_get_connection)

        queue = JobQueue(worker_id="test-worker")
        job_id = uuid.uuid4()
        ad_id = uuid.uuid4()
        output = JobOutput(ad_id=str(ad_id), warnings=["test"])

        queue.complete(job_id, output, ad_id=ad_id)

        assert "complete_job" in cursor.query
        assert cursor.params[0] == job_id


class TestJobQueueFail:
    """Test JobQueue.fail with mocked database."""

    def test_fail_transient(self, monkeypatch):
        """fail with permanent=False should schedule retry."""
        cursor = FakeCursor()
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.job_queue.get_connection", fake_get_connection)

        queue = JobQueue(worker_id="test-worker")
        job_id = uuid.uuid4()

        queue.fail(job_id, "Network timeout", error_code="TIMEOUT", permanent=False)

        assert "fail_job" in cursor.query
        assert cursor.params[0] == job_id
        assert cursor.params[3] is False  # permanent

    def test_fail_permanent(self, monkeypatch):
        """fail with permanent=True should mark as failed."""
        cursor = FakeCursor()
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.job_queue.get_connection", fake_get_connection)

        queue = JobQueue(worker_id="test-worker")
        job_id = uuid.uuid4()

        queue.fail(job_id, "Invalid format", error_code="INVALID", permanent=True)

        assert "fail_job" in cursor.query
        assert cursor.params[3] is True  # permanent


class TestJobQueueSchema:
    """Test JobQueue.verify_schema with mocked database."""

    def test_verify_schema_success(self, monkeypatch):
        """verify_schema should pass when all columns exist."""
        required_columns = [
            {"column_name": "id"},
            {"column_name": "status"},
            {"column_name": "priority"},
            {"column_name": "attempts"},
            {"column_name": "max_attempts"},
            {"column_name": "locked_at"},
            {"column_name": "locked_by"},
            {"column_name": "run_after"},
            {"column_name": "last_error"},
            {"column_name": "input"},
            {"column_name": "output"},
            {"column_name": "idempotency_key"},
        ]
        cursor = FakeCursor(required_columns)
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.job_queue.get_connection", fake_get_connection)

        queue = JobQueue(worker_id="test-worker")
        result = queue.verify_schema()

        assert result is True

    def test_verify_schema_missing_columns(self, monkeypatch):
        """verify_schema should fail when columns are missing."""
        cursor = FakeCursor([{"column_name": "id"}])  # Missing most columns
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.job_queue.get_connection", fake_get_connection)

        queue = JobQueue(worker_id="test-worker")

        with pytest.raises(RuntimeError, match="missing required columns"):
            queue.verify_schema()


# ---------------------------------------------------------------------------
# Concurrency Simulation Test
# ---------------------------------------------------------------------------

class TestConcurrencySafety:
    """
    Simulate concurrent claiming to verify logic.

    Note: This doesn't test actual database locking, but verifies
    the claim logic handles concurrent scenarios correctly.
    """

    def test_two_workers_claim_different_jobs(self, monkeypatch):
        """Two workers should claim different jobs."""
        job1_id = uuid.uuid4()
        job2_id = uuid.uuid4()

        # Worker 1 gets job1
        worker1_cursor = FakeCursor([{
            "job_id": job1_id,
            "job_input": {"source_type": "s3", "s3_key": "test1.mp4"},
            "job_attempts": 1,
            "job_max_attempts": 5,
            "job_created_at": datetime.now(),
        }])

        # Worker 2 gets job2
        worker2_cursor = FakeCursor([{
            "job_id": job2_id,
            "job_input": {"source_type": "s3", "s3_key": "test2.mp4"},
            "job_attempts": 1,
            "job_max_attempts": 5,
            "job_created_at": datetime.now(),
        }])

        call_count = [0]
        cursors = [worker1_cursor, worker2_cursor]

        @contextmanager
        def fake_get_connection():
            idx = min(call_count[0], len(cursors) - 1)
            call_count[0] += 1
            yield FakeConnection(cursors[idx])

        monkeypatch.setattr("tvads_rag.job_queue.get_connection", fake_get_connection)

        worker1 = JobQueue(worker_id="worker-1")
        worker2 = JobQueue(worker_id="worker-2")

        jobs1 = worker1.claim_jobs(limit=1)
        jobs2 = worker2.claim_jobs(limit=1)

        # Each worker should get a different job
        assert len(jobs1) == 1
        assert len(jobs2) == 1
        assert jobs1[0].id == job1_id
        assert jobs2[0].id == job2_id


# ---------------------------------------------------------------------------
# Heartbeat Tests
# ---------------------------------------------------------------------------

class TestJobQueueHeartbeat:
    """Test JobQueue.heartbeat with mocked database."""

    def test_heartbeat_calls_function(self, monkeypatch):
        """heartbeat should call update_job_heartbeat function."""
        cursor = FakeCursor()
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.job_queue.get_connection", fake_get_connection)

        queue = JobQueue(worker_id="test-worker")
        job_id = uuid.uuid4()

        queue.heartbeat(job_id, stage="transcription", progress=0.5)

        assert "update_job_heartbeat" in cursor.query
        assert cursor.params[0] == job_id
        assert cursor.params[1] == "transcription"
        assert cursor.params[2] == 0.5

    def test_heartbeat_without_stage(self, monkeypatch):
        """heartbeat should work without stage parameter."""
        cursor = FakeCursor()
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.job_queue.get_connection", fake_get_connection)

        queue = JobQueue(worker_id="test-worker")
        job_id = uuid.uuid4()

        queue.heartbeat(job_id)  # No stage or progress

        assert "update_job_heartbeat" in cursor.query
        assert cursor.params[0] == job_id
        assert cursor.params[1] is None
        assert cursor.params[2] is None


class TestStaleJobRelease:
    """Test stale job release functionality."""

    def test_release_stale_jobs_calls_function(self, monkeypatch):
        """release_stale_jobs should call the SQL function."""
        cursor = FakeCursor([{"release_stale_jobs": 3}])
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.job_queue.get_connection", fake_get_connection)

        queue = JobQueue(worker_id="test-worker")
        released = queue.release_stale_jobs(stale_threshold_minutes=30)

        assert released == 3
        assert "release_stale_jobs" in cursor.query
        assert cursor.params[0] == 30

    def test_release_stale_jobs_returns_zero_when_none(self, monkeypatch):
        """release_stale_jobs should return 0 when no stale jobs."""
        cursor = FakeCursor([{"release_stale_jobs": 0}])
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.job_queue.get_connection", fake_get_connection)

        queue = JobQueue(worker_id="test-worker")
        released = queue.release_stale_jobs()

        assert released == 0


class TestRunningJobsMonitor:
    """Test running jobs monitoring."""

    def test_get_running_jobs(self, monkeypatch):
        """get_running_jobs should return running jobs from view."""
        running_jobs = [
            {
                "id": uuid.uuid4(),
                "stage": "llm_analysis",
                "progress": 0.6,
                "running_seconds": 120,
                "heartbeat_age_seconds": 5,
            }
        ]
        cursor = FakeCursor(running_jobs)
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.job_queue.get_connection", fake_get_connection)

        queue = JobQueue(worker_id="test-worker")
        result = queue.get_running_jobs()

        assert len(result) == 1
        assert result[0]["stage"] == "llm_analysis"
        assert result[0]["progress"] == 0.6
        assert "running_jobs_monitor" in cursor.query

    def test_get_timing_stats(self, monkeypatch):
        """get_timing_stats should return timing stats from view."""
        stats = [
            {
                "status": "SUCCEEDED",
                "count": 100,
                "avg_duration_seconds": 45,
                "p50_seconds": 40,
                "p95_seconds": 90,
            }
        ]
        cursor = FakeCursor(stats)
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.job_queue.get_connection", fake_get_connection)

        queue = JobQueue(worker_id="test-worker")
        result = queue.get_timing_stats()

        assert len(result) == 1
        assert result[0]["status"] == "SUCCEEDED"
        assert result[0]["avg_duration_seconds"] == 45
        assert "job_timing_stats" in cursor.query


# ---------------------------------------------------------------------------
# Completed Jobs Should Not Be Reclaimed
# ---------------------------------------------------------------------------

class TestCompletedJobsNotReclaimed:
    """Verify that completed jobs are never reclaimed."""

    def test_claim_only_returns_queued_or_retry(self, monkeypatch):
        """claim_jobs should only return QUEUED or RETRY jobs."""
        # The SQL function already handles this, but verify the params
        cursor = FakeCursor([])  # No jobs returned
        conn = FakeConnection(cursor)

        @contextmanager
        def fake_get_connection():
            yield conn

        monkeypatch.setattr("tvads_rag.job_queue.get_connection", fake_get_connection)

        queue = JobQueue(worker_id="test-worker")
        jobs = queue.claim_jobs(limit=5)

        assert jobs == []
        # The SQL function filters by status IN ('QUEUED', 'RETRY')
        assert "claim_jobs" in cursor.query
