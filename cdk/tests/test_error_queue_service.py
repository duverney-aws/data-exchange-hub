"""
Unit Tests for ErrorQueueService.

Validates:
- Error queuing and classification
- Exponential backoff retry mechanism
- Dead-letter queue for exceeded retries
- Detailed error logging with record identifiers

Requirements: 15.3, 15.4
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.error_queue_service import (
    ErrorClassifier,
    ErrorQueueError,
    ErrorQueueService,
    DEFAULT_BASE_DELAY,
    DEFAULT_MAX_RETRIES,
    ERROR_NETWORK,
    ERROR_TIMEOUT,
    ERROR_UNKNOWN,
    ERROR_VALIDATION,
    STATUS_DEAD_LETTER,
    STATUS_PROCESSING,
    STATUS_QUEUED,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeClock:
    """Controllable clock for deterministic tests."""

    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _ok_func(value="ok"):
    """A callable that always succeeds."""
    return value


def _fail_func():
    """A callable that always raises."""
    raise RuntimeError("downstream failure")


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def service(clock):
    return ErrorQueueService(
        max_retries=3,
        base_delay=1.0,
        clock=clock,
        jitter=lambda: 0.0,  # deterministic — no jitter
    )


# ---------------------------------------------------------------------------
# ErrorClassifier
# ---------------------------------------------------------------------------

class TestErrorClassifier:
    """Requirement 15.3: Classify errors by type."""

    def test_classify_connection_error(self):
        assert ErrorClassifier.classify(ConnectionError("refused")) == ERROR_NETWORK

    def test_classify_connection_reset(self):
        assert ErrorClassifier.classify(ConnectionResetError("reset")) == ERROR_NETWORK

    def test_classify_timeout_error(self):
        assert ErrorClassifier.classify(TimeoutError("timed out")) == ERROR_TIMEOUT

    def test_classify_value_error_as_validation(self):
        assert ErrorClassifier.classify(ValueError("bad field")) == ERROR_VALIDATION

    def test_classify_generic_exception_as_unknown(self):
        assert ErrorClassifier.classify(Exception("something")) == ERROR_UNKNOWN

    def test_classify_runtime_error_as_unknown(self):
        assert ErrorClassifier.classify(RuntimeError("oops")) == ERROR_UNKNOWN

    def test_is_retryable_network(self):
        assert ErrorClassifier.is_retryable(ERROR_NETWORK) is True

    def test_is_retryable_timeout(self):
        assert ErrorClassifier.is_retryable(ERROR_TIMEOUT) is True

    def test_is_retryable_validation(self):
        assert ErrorClassifier.is_retryable(ERROR_VALIDATION) is False

    def test_is_retryable_unknown(self):
        assert ErrorClassifier.is_retryable(ERROR_UNKNOWN) is False


# ---------------------------------------------------------------------------
# Enqueue
# ---------------------------------------------------------------------------

class TestEnqueueFailedRecord:
    """Requirement 15.3: Queue failed records for reprocessing."""

    def test_enqueue_returns_record_with_required_fields(self, service):
        rec = service.enqueue_failed_record(
            record_id="REC-001",
            contract_id="CMO-ALPHA-BATCH-001",
            error_type=ERROR_NETWORK,
            error_message="Connection refused",
        )
        assert rec["record_id"] == "REC-001"
        assert rec["contract_id"] == "CMO-ALPHA-BATCH-001"
        assert rec["error_type"] == ERROR_NETWORK
        assert rec["error_message"] == "Connection refused"
        assert rec["retry_count"] == 0
        assert rec["max_retries"] == 3
        assert rec["status"] == STATUS_QUEUED
        assert "queue_id" in rec
        assert "enqueued_at" in rec
        assert "timestamp" in rec

    def test_enqueue_with_record_data_and_metadata(self, service):
        rec = service.enqueue_failed_record(
            record_id="REC-002",
            contract_id="CMO-BETA-QC-001",
            error_type=ERROR_TIMEOUT,
            error_message="Read timed out",
            record_data={"batch_id": "B-100", "yield": 95.2},
            metadata={"step": "bronze_ingest", "source": "snowflake"},
        )
        assert rec["record_data"] == {"batch_id": "B-100", "yield": 95.2}
        assert rec["metadata"]["step"] == "bronze_ingest"

    def test_invalid_error_type_defaults_to_unknown(self, service):
        rec = service.enqueue_failed_record(
            record_id="REC-003",
            contract_id="C-001",
            error_type="invalid_type",
            error_message="something",
        )
        assert rec["error_type"] == ERROR_UNKNOWN

    def test_enqueue_increments_queue_count(self, service):
        service.enqueue_failed_record("R1", "C1", ERROR_NETWORK, "err1")
        service.enqueue_failed_record("R2", "C1", ERROR_TIMEOUT, "err2")
        stats = service.get_queue_stats()
        assert stats[STATUS_QUEUED] == 2


# ---------------------------------------------------------------------------
# Dequeue
# ---------------------------------------------------------------------------

class TestDequeueRecords:
    """Requirement 15.3: Retrieve queued records for reprocessing."""

    def test_dequeue_returns_queued_records(self, service):
        service.enqueue_failed_record("R1", "C1", ERROR_NETWORK, "err")
        service.enqueue_failed_record("R2", "C1", ERROR_NETWORK, "err")
        records = service.dequeue_records(max_records=10)
        assert len(records) == 2
        assert all(r["status"] == STATUS_PROCESSING for r in records)

    def test_dequeue_respects_max_records(self, service):
        for i in range(5):
            service.enqueue_failed_record(f"R{i}", "C1", ERROR_NETWORK, "err")
        records = service.dequeue_records(max_records=2)
        assert len(records) == 2

    def test_dequeue_skips_processing_records(self, service):
        service.enqueue_failed_record("R1", "C1", ERROR_NETWORK, "err")
        service.dequeue_records()  # marks R1 as processing
        records = service.dequeue_records()
        assert len(records) == 0

    def test_dequeue_empty_queue(self, service):
        records = service.dequeue_records()
        assert records == []


# ---------------------------------------------------------------------------
# Reprocess with exponential backoff
# ---------------------------------------------------------------------------

class TestReprocessRecord:
    """Requirement 15.3: Retry mechanism with exponential backoff."""

    def test_successful_reprocess_removes_from_queue(self, service):
        service.enqueue_failed_record("R1", "C1", ERROR_NETWORK, "err")
        records = service.dequeue_records()
        result = service.reprocess_record(records[0], lambda: "success")
        assert result == "success"
        assert service.get_queue_stats()[STATUS_QUEUED] == 0
        assert service.get_queue_stats()[STATUS_PROCESSING] == 0

    def test_failed_reprocess_increments_retry_count(self, service):
        service.enqueue_failed_record("R1", "C1", ERROR_NETWORK, "err")
        records = service.dequeue_records()
        rec = records[0]
        with pytest.raises(RuntimeError):
            service.reprocess_record(rec, _fail_func)
        assert rec["retry_count"] == 1
        assert rec["status"] == STATUS_QUEUED

    def test_exceeded_retries_moves_to_dead_letter(self, service):
        service.enqueue_failed_record("R1", "C1", ERROR_NETWORK, "err")
        records = service.dequeue_records()
        rec = records[0]
        # Exhaust retries (max_retries=3, so retry_count must exceed 3)
        rec["retry_count"] = 3  # next increment makes it 4 > 3
        with pytest.raises(ErrorQueueError, match="exceeded max retries"):
            service.reprocess_record(rec, _ok_func)
        assert len(service.get_dead_letter_records()) == 1
        assert service.get_dead_letter_records()[0]["status"] == STATUS_DEAD_LETTER

    def test_exponential_backoff_calculation(self, service):
        # With jitter=0, backoff = base_delay * 2^(retry-1)
        assert service._calculate_backoff(1) == 1.0   # 1 * 2^0 = 1
        assert service._calculate_backoff(2) == 2.0   # 1 * 2^1 = 2
        assert service._calculate_backoff(3) == 4.0   # 1 * 2^2 = 4


# ---------------------------------------------------------------------------
# Dead-letter queue
# ---------------------------------------------------------------------------

class TestDeadLetterQueue:
    """Requirement 15.3: Records exceeding max retries go to dead-letter."""

    def test_dead_letter_initially_empty(self, service):
        assert service.get_dead_letter_records() == []

    def test_dead_letter_contains_failed_records(self, service):
        service.enqueue_failed_record("R1", "C1", ERROR_NETWORK, "err")
        records = service.dequeue_records()
        rec = records[0]
        rec["retry_count"] = 3
        with pytest.raises(ErrorQueueError):
            service.reprocess_record(rec, _ok_func)
        dlq = service.get_dead_letter_records()
        assert len(dlq) == 1
        assert dlq[0]["record_id"] == "R1"
        assert "dead_letter_at" in dlq[0]


# ---------------------------------------------------------------------------
# Error logging
# ---------------------------------------------------------------------------

class TestLogError:
    """Requirement 15.4: Log detailed error messages with record identifiers."""

    def test_log_error_returns_structured_entry(self, service):
        entry = service.log_error(
            record_id="REC-001",
            contract_id="CMO-ALPHA-BATCH-001",
            error_type=ERROR_VALIDATION,
            error_message="Field 'batch_id' is required",
            step="schema_validation",
        )
        assert entry["severity"] == "ERROR"
        assert entry["record_id"] == "REC-001"
        assert entry["contract_id"] == "CMO-ALPHA-BATCH-001"
        assert entry["error_type"] == ERROR_VALIDATION
        assert entry["error_message"] == "Field 'batch_id' is required"
        assert entry["step"] == "schema_validation"
        assert "timestamp" in entry
        assert "action" in entry

    def test_log_error_includes_actionable_message(self, service):
        entry = service.log_error("R1", "C1", ERROR_NETWORK, "conn refused")
        assert "network" in entry["action"].lower() or "retry" in entry["action"].lower()

    def test_log_error_stored_in_logs(self, service):
        service.log_error("R1", "C1", ERROR_VALIDATION, "bad schema", step="validate")
        service.log_error("R2", "C1", ERROR_NETWORK, "timeout", step="ingest")
        logs = service.get_error_logs()
        assert len(logs) == 2
        assert logs[0]["record_id"] == "R1"
        assert logs[1]["record_id"] == "R2"

    def test_log_error_default_step(self, service):
        entry = service.log_error("R1", "C1", ERROR_UNKNOWN, "oops")
        assert entry["step"] == "unknown"


# ---------------------------------------------------------------------------
# Queue stats
# ---------------------------------------------------------------------------

class TestQueueStats:
    """Requirement 15.3: Queue statistics by status."""

    def test_empty_stats(self, service):
        stats = service.get_queue_stats()
        assert stats == {STATUS_QUEUED: 0, STATUS_PROCESSING: 0, STATUS_DEAD_LETTER: 0}

    def test_stats_reflect_queue_state(self, service):
        service.enqueue_failed_record("R1", "C1", ERROR_NETWORK, "err")
        service.enqueue_failed_record("R2", "C1", ERROR_TIMEOUT, "err")
        service.dequeue_records(max_records=1)  # R1 → processing
        stats = service.get_queue_stats()
        assert stats[STATUS_QUEUED] == 1
        assert stats[STATUS_PROCESSING] == 1
        assert stats[STATUS_DEAD_LETTER] == 0


# ---------------------------------------------------------------------------
# Error classes
# ---------------------------------------------------------------------------

class TestErrorClasses:
    def test_error_queue_error_attributes(self):
        err = ErrorQueueError("msg", step="enqueue", contract_id="C-001")
        assert str(err) == "msg"
        assert err.step == "enqueue"
        assert err.contract_id == "C-001"
