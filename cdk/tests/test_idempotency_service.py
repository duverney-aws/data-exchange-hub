"""
Unit Tests for IdempotencyService and PipelineIdempotencyGuard.

Validates:
- Idempotency key generation (deterministic, unique per input)
- check_and_record behaviour for new / in_progress / completed / failed keys
- mark_completed and mark_failed transitions
- TTL expiration of stale records
- PipelineIdempotencyGuard end-to-end flow

Requirements: 15.6
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.idempotency_service import (
    DEFAULT_TTL_SECONDS,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_IN_PROGRESS,
    IdempotencyError,
    IdempotencyService,
    IdempotentOperationInProgressError,
    PipelineIdempotencyGuard,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeClock:
    """Controllable clock for deterministic TTL tests."""

    def __init__(self, start: float = 1_000_000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def service(clock):
    return IdempotencyService(ttl_seconds=DEFAULT_TTL_SECONDS, clock=clock)


# ---------------------------------------------------------------------------
# generate_idempotency_key
# ---------------------------------------------------------------------------

class TestGenerateIdempotencyKey:
    """Requirement 15.6: Unique identifiers for deduplication."""

    def test_deterministic_for_same_inputs(self):
        k1 = IdempotencyService.generate_idempotency_key("C-001", "ingest", {"a": 1})
        k2 = IdempotencyService.generate_idempotency_key("C-001", "ingest", {"a": 1})
        assert k1 == k2

    def test_different_contract_ids_produce_different_keys(self):
        k1 = IdempotencyService.generate_idempotency_key("C-001", "ingest", {"a": 1})
        k2 = IdempotencyService.generate_idempotency_key("C-002", "ingest", {"a": 1})
        assert k1 != k2

    def test_different_operation_types_produce_different_keys(self):
        k1 = IdempotencyService.generate_idempotency_key("C-001", "ingest", {"a": 1})
        k2 = IdempotencyService.generate_idempotency_key("C-001", "validate", {"a": 1})
        assert k1 != k2

    def test_different_payloads_produce_different_keys(self):
        k1 = IdempotencyService.generate_idempotency_key("C-001", "ingest", {"a": 1})
        k2 = IdempotencyService.generate_idempotency_key("C-001", "ingest", {"a": 2})
        assert k1 != k2

    def test_key_is_hex_string(self):
        key = IdempotencyService.generate_idempotency_key("C-001", "op", {})
        assert isinstance(key, str)
        assert len(key) == 64  # SHA-256 hex digest

    def test_payload_key_order_does_not_matter(self):
        k1 = IdempotencyService.generate_idempotency_key("C-001", "op", {"b": 2, "a": 1})
        k2 = IdempotencyService.generate_idempotency_key("C-001", "op", {"a": 1, "b": 2})
        assert k1 == k2


# ---------------------------------------------------------------------------
# check_and_record — new key
# ---------------------------------------------------------------------------

class TestCheckAndRecordNewKey:
    """Requirement 15.6: Check for existing records before insertion."""

    def test_returns_none_for_new_key(self, service):
        result = service.check_and_record("new-key")
        assert result is None

    def test_records_in_progress_for_new_key(self, service):
        service.check_and_record("new-key")
        record = service._store["new-key"]
        assert record["status"] == STATUS_IN_PROGRESS

    def test_stores_operation_details(self, service):
        service.check_and_record("k", operation_details={"contract_id": "C-001"})
        assert service._store["k"]["operation_details"]["contract_id"] == "C-001"


# ---------------------------------------------------------------------------
# check_and_record — completed key
# ---------------------------------------------------------------------------

class TestCheckAndRecordCompleted:
    """Requirement 15.6: Idempotent response for completed operations."""

    def test_returns_cached_result(self, service):
        service.check_and_record("k")
        service.mark_completed("k", {"rows": 42})

        result = service.check_and_record("k")
        assert result == {"rows": 42}

    def test_does_not_overwrite_completed_record(self, service):
        service.check_and_record("k")
        service.mark_completed("k", "first")

        # Second call should return cached, not re-record
        service.check_and_record("k")
        assert service._store["k"]["status"] == STATUS_COMPLETED
        assert service._store["k"]["result"] == "first"


# ---------------------------------------------------------------------------
# check_and_record — in_progress key
# ---------------------------------------------------------------------------

class TestCheckAndRecordInProgress:
    """Requirement 15.6: Prevent duplicate concurrent operations."""

    def test_raises_for_in_progress_key(self, service):
        service.check_and_record("k")
        with pytest.raises(IdempotentOperationInProgressError) as exc_info:
            service.check_and_record("k")
        assert "k" in str(exc_info.value)

    def test_error_contains_idempotency_key(self, service):
        service.check_and_record("k")
        with pytest.raises(IdempotentOperationInProgressError) as exc_info:
            service.check_and_record("k")
        assert exc_info.value.idempotency_key == "k"


# ---------------------------------------------------------------------------
# check_and_record — failed key (allows retry)
# ---------------------------------------------------------------------------

class TestCheckAndRecordFailed:
    """Requirement 15.6: Safe retries without data duplication."""

    def test_allows_retry_after_failure(self, service):
        service.check_and_record("k")
        service.mark_failed("k", "timeout")

        # Should allow retry (return None, re-record as in_progress)
        result = service.check_and_record("k")
        assert result is None
        assert service._store["k"]["status"] == STATUS_IN_PROGRESS


# ---------------------------------------------------------------------------
# mark_completed / mark_failed
# ---------------------------------------------------------------------------

class TestMarkCompleted:
    def test_sets_status_and_result(self, service, clock):
        service.check_and_record("k")
        service.mark_completed("k", {"ok": True})
        record = service._store["k"]
        assert record["status"] == STATUS_COMPLETED
        assert record["result"] == {"ok": True}
        assert record["completed_at"] == clock.now

    def test_no_op_for_unknown_key(self, service):
        # Should not raise
        service.mark_completed("missing", "val")


class TestMarkFailed:
    def test_sets_status_and_error(self, service, clock):
        service.check_and_record("k")
        service.mark_failed("k", "boom")
        record = service._store["k"]
        assert record["status"] == STATUS_FAILED
        assert record["error_message"] == "boom"
        assert record["failed_at"] == clock.now

    def test_no_op_for_unknown_key(self, service):
        service.mark_failed("missing", "err")


# ---------------------------------------------------------------------------
# TTL expiration
# ---------------------------------------------------------------------------

class TestTTLExpiration:
    """Requirement 15.6: TTL for idempotency records (default 24h)."""

    def test_expired_record_treated_as_new(self, service, clock):
        service.check_and_record("k")
        service.mark_completed("k", "old-result")

        # Advance past TTL
        clock.advance(DEFAULT_TTL_SECONDS + 1)

        result = service.check_and_record("k")
        assert result is None  # treated as new
        assert service._store["k"]["status"] == STATUS_IN_PROGRESS

    def test_non_expired_record_still_valid(self, service, clock):
        service.check_and_record("k")
        service.mark_completed("k", "result")

        clock.advance(DEFAULT_TTL_SECONDS - 1)

        result = service.check_and_record("k")
        assert result == "result"

    def test_default_ttl_is_24_hours(self):
        assert DEFAULT_TTL_SECONDS == 86400


# ---------------------------------------------------------------------------
# PipelineIdempotencyGuard
# ---------------------------------------------------------------------------

class TestPipelineIdempotencyGuard:
    """Requirement 15.6: Wraps pipeline operations with idempotency."""

    @pytest.fixture
    def guard(self, service):
        return PipelineIdempotencyGuard(service)

    def test_first_call_executes_func(self, guard):
        calls = []

        def work():
            calls.append(1)
            return "done"

        result = guard.execute("C-001", "ingest", {"file": "a.parquet"}, work)
        assert result == "done"
        assert len(calls) == 1

    def test_second_call_returns_cached_result(self, guard):
        calls = []

        def work():
            calls.append(1)
            return "done"

        guard.execute("C-001", "ingest", {"file": "a.parquet"}, work)
        result = guard.execute("C-001", "ingest", {"file": "a.parquet"}, work)
        assert result == "done"
        assert len(calls) == 1  # func called only once

    def test_different_payloads_execute_separately(self, guard):
        calls = []

        def work():
            calls.append(1)
            return f"run-{len(calls)}"

        r1 = guard.execute("C-001", "ingest", {"file": "a.parquet"}, work)
        r2 = guard.execute("C-001", "ingest", {"file": "b.parquet"}, work)
        assert r1 == "run-1"
        assert r2 == "run-2"
        assert len(calls) == 2

    def test_failure_marks_failed_and_reraises(self, guard, service):
        def failing():
            raise RuntimeError("network error")

        with pytest.raises(RuntimeError, match="network error"):
            guard.execute("C-001", "ingest", {"file": "a.parquet"}, failing)

        # The record should be marked failed
        key = IdempotencyService.generate_idempotency_key(
            "C-001", "ingest", {"file": "a.parquet"}
        )
        assert service._store[key]["status"] == STATUS_FAILED

    def test_retry_after_failure_executes_func_again(self, guard):
        attempt = {"n": 0}

        def work():
            attempt["n"] += 1
            if attempt["n"] == 1:
                raise RuntimeError("transient")
            return "success"

        with pytest.raises(RuntimeError):
            guard.execute("C-001", "ingest", {"f": 1}, work)

        result = guard.execute("C-001", "ingest", {"f": 1}, work)
        assert result == "success"
        assert attempt["n"] == 2

    def test_in_progress_raises(self, service):
        """Concurrent duplicate should raise."""
        guard = PipelineIdempotencyGuard(service)

        # Manually record as in_progress
        key = IdempotencyService.generate_idempotency_key("C-001", "op", {})
        service.check_and_record(key)

        with pytest.raises(IdempotentOperationInProgressError):
            guard.execute("C-001", "op", {}, lambda: "x")


# ---------------------------------------------------------------------------
# Error classes
# ---------------------------------------------------------------------------

class TestErrorClasses:
    def test_idempotency_error_attributes(self):
        err = IdempotencyError("msg", step="step1", contract_id="C-001")
        assert str(err) == "msg"
        assert err.step == "step1"
        assert err.contract_id == "C-001"

    def test_in_progress_error_attributes(self):
        err = IdempotentOperationInProgressError(
            idempotency_key="abc123", contract_id="C-002"
        )
        assert "abc123" in str(err)
        assert err.idempotency_key == "abc123"
        assert err.contract_id == "C-002"
        assert err.step == "idempotency_in_progress"
