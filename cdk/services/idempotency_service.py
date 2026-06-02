"""
Idempotency Service

Ensures pipeline operations can be safely retried without data duplication.
Uses unique idempotency keys derived from contract_id, operation_type, and
a content hash of the payload to detect and prevent duplicate processing.

Records are stored with a TTL so stale entries are automatically cleaned up.

Requirements: 15.6
"""
import hashlib
import json
import logging
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# Default TTL: 24 hours in seconds
DEFAULT_TTL_SECONDS = 24 * 60 * 60

# Idempotency record statuses
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


class IdempotencyError(Exception):
    """Base exception for idempotency operations."""

    def __init__(self, message: str, step: str = "idempotency", contract_id: str = ""):
        self.step = step
        self.contract_id = contract_id
        super().__init__(message)


class IdempotentOperationInProgressError(IdempotencyError):
    """Raised when an identical operation is already in progress."""

    def __init__(self, idempotency_key: str, contract_id: str = ""):
        self.idempotency_key = idempotency_key
        super().__init__(
            f"Operation with idempotency key '{idempotency_key}' is already in progress.",
            step="idempotency_in_progress",
            contract_id=contract_id,
        )


class IdempotencyService:
    """
    Service for maintaining idempotency of pipeline operations.

    Stores idempotency records keyed by a hash of (contract_id, operation_type,
    payload).  When a duplicate request arrives the service returns the cached
    result (if completed) or raises if the operation is still running.

    For production use, pass a DynamoDB Table resource.  For testing, the
    default in-memory dict store is used.
    """

    def __init__(
        self,
        dynamodb_table=None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        clock: Optional[Callable[[], float]] = None,
    ):
        """
        Args:
            dynamodb_table: boto3 DynamoDB Table resource (optional).
                            When *None* an in-memory dict is used.
            ttl_seconds: Time-to-live for idempotency records.
            clock: Callable returning current epoch seconds (for testing).
        """
        self._table = dynamodb_table
        self._ttl_seconds = ttl_seconds
        self._clock = clock or time.time
        # In-memory store used when no DynamoDB table is provided
        self._store: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def generate_idempotency_key(
        contract_id: str, operation_type: str, payload: Any
    ) -> str:
        """
        Derive a deterministic idempotency key from the operation parameters.

        The key is a SHA-256 hex digest of ``contract_id|operation_type|<payload_json>``.
        """
        payload_json = json.dumps(payload, sort_keys=True, default=str)
        raw = f"{contract_id}|{operation_type}|{payload_json}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def check_and_record(
        self, idempotency_key: str, operation_details: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """
        Check whether an operation has already been executed.

        Returns:
            - The cached *result* if the operation already completed successfully.
            - *None* if the key is new (caller should proceed with the operation).

        Raises:
            IdempotentOperationInProgressError: if the operation is currently running.
        """
        record = self._get_record(idempotency_key)

        if record is not None:
            # Expired records are treated as non-existent
            if self._is_expired(record):
                self._delete_record(idempotency_key)
            else:
                status = record.get("status")
                if status == STATUS_COMPLETED:
                    logger.info("Idempotent hit (completed) for key=%s", idempotency_key)
                    return record.get("result")
                if status == STATUS_IN_PROGRESS:
                    raise IdempotentOperationInProgressError(
                        idempotency_key=idempotency_key,
                        contract_id=record.get("contract_id", ""),
                    )
                # STATUS_FAILED → allow retry, fall through to re-record

        # Record as in_progress
        now = self._clock()
        new_record = {
            "idempotency_key": idempotency_key,
            "status": STATUS_IN_PROGRESS,
            "created_at": now,
            "ttl": int(now + self._ttl_seconds),
            "operation_details": operation_details or {},
            "result": None,
            "error_message": None,
        }
        self._put_record(idempotency_key, new_record)
        return None

    def mark_completed(self, idempotency_key: str, result: Any) -> None:
        """Mark an in-progress operation as completed and cache its result."""
        record = self._get_record(idempotency_key)
        if record is None:
            logger.warning("mark_completed called for unknown key=%s", idempotency_key)
            return
        record["status"] = STATUS_COMPLETED
        record["result"] = result
        record["completed_at"] = self._clock()
        self._put_record(idempotency_key, record)

    def mark_failed(self, idempotency_key: str, error_message: str) -> None:
        """Mark an in-progress operation as failed so it can be retried."""
        record = self._get_record(idempotency_key)
        if record is None:
            logger.warning("mark_failed called for unknown key=%s", idempotency_key)
            return
        record["status"] = STATUS_FAILED
        record["error_message"] = error_message
        record["failed_at"] = self._clock()
        self._put_record(idempotency_key, record)

    # ------------------------------------------------------------------
    # Storage helpers (in-memory or DynamoDB)
    # ------------------------------------------------------------------

    def _get_record(self, key: str) -> Optional[Dict[str, Any]]:
        if self._table is not None:
            resp = self._table.get_item(Key={"idempotency_key": key})
            return resp.get("Item")
        return self._store.get(key)

    def _put_record(self, key: str, record: Dict[str, Any]) -> None:
        if self._table is not None:
            self._table.put_item(Item=record)
        else:
            self._store[key] = record

    def _delete_record(self, key: str) -> None:
        if self._table is not None:
            self._table.delete_item(Key={"idempotency_key": key})
        else:
            self._store.pop(key, None)

    def _is_expired(self, record: Dict[str, Any]) -> bool:
        ttl = record.get("ttl")
        if ttl is None:
            return False
        return self._clock() >= ttl



class PipelineIdempotencyGuard:
    """
    High-level wrapper that adds idempotency to any pipeline operation.

    Usage::

        guard = PipelineIdempotencyGuard(idempotency_service)
        result = guard.execute(
            contract_id="CMO-ALPHA-BATCH-001",
            operation_type="bronze_ingest",
            payload={"file": "data.parquet"},
            func=lambda: do_ingest(),
        )

    If the same (contract_id, operation_type, payload) combination has already
    completed, the cached result is returned without calling *func* again.
    """

    def __init__(self, idempotency_service: IdempotencyService):
        self._service = idempotency_service

    def execute(
        self,
        contract_id: str,
        operation_type: str,
        payload: Any,
        func: Callable[[], Any],
    ) -> Any:
        """
        Execute *func* with idempotency guarantees.

        1. Generate idempotency key from the operation parameters.
        2. If already completed → return cached result.
        3. If new → record as in_progress, call *func*.
        4. On success → mark completed with result.
        5. On failure → mark failed (allows future retry).

        Raises:
            IdempotentOperationInProgressError: if the same operation is
                already running.
        """
        key = IdempotencyService.generate_idempotency_key(
            contract_id, operation_type, payload
        )

        cached = self._service.check_and_record(
            key,
            operation_details={
                "contract_id": contract_id,
                "operation_type": operation_type,
            },
        )
        if cached is not None:
            logger.info(
                "Returning cached result for contract=%s op=%s",
                contract_id,
                operation_type,
            )
            return cached

        try:
            result = func()
            self._service.mark_completed(key, result)
            return result
        except Exception as exc:
            self._service.mark_failed(key, str(exc))
            raise
