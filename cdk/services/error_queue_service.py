"""
Error Queue Service

Queues failed pipeline records for reprocessing with exponential backoff
retry logic. Classifies errors by type (network, validation, timeout, unknown)
and routes non-retryable failures to a dead-letter queue. Logs detailed error
messages with record identifiers in a CloudWatch-compatible format.

Requirements: 15.3, 15.4
"""
import json
import logging
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Retry defaults
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0  # seconds

# Queue record statuses
STATUS_QUEUED = "queued"
STATUS_PROCESSING = "processing"
STATUS_DEAD_LETTER = "dead_letter"

# Error type constants
ERROR_NETWORK = "network"
ERROR_VALIDATION = "validation"
ERROR_TIMEOUT = "timeout"
ERROR_UNKNOWN = "unknown"

VALID_ERROR_TYPES = {ERROR_NETWORK, ERROR_VALIDATION, ERROR_TIMEOUT, ERROR_UNKNOWN}


class ErrorQueueError(Exception):
    """Base exception for error queue operations."""

    def __init__(self, message: str, step: str = "error_queue", contract_id: str = ""):
        self.step = step
        self.contract_id = contract_id
        super().__init__(message)


class ErrorClassifier:
    """
    Utility for classifying exceptions into error types and determining
    whether they are retryable.
    """

    # Exception class names / substrings that map to known error types
    _NETWORK_INDICATORS = (
        "ConnectionError", "ConnectionRefusedError", "ConnectionResetError",
        "BrokenPipeError", "ConnectionAbortedError", "EndpointConnectionError",
        "NetworkError", "SocketError", "DNSError",
    )
    _TIMEOUT_INDICATORS = (
        "TimeoutError", "ReadTimeoutError", "ConnectTimeoutError",
        "SocketTimeoutError", "Timeout",
    )
    _VALIDATION_INDICATORS = (
        "ValidationError", "SchemaValidationError", "ValueError",
        "InvalidSchema", "DataValidationError",
    )

    @staticmethod
    def classify(exception: Exception) -> str:
        """
        Classify an exception into an error type string.

        Returns one of: "network", "validation", "timeout", "unknown".
        """
        exc_name = type(exception).__name__
        exc_str = str(exception).lower()

        for indicator in ErrorClassifier._NETWORK_INDICATORS:
            if indicator in exc_name or indicator.lower() in exc_str:
                return ERROR_NETWORK

        for indicator in ErrorClassifier._TIMEOUT_INDICATORS:
            if indicator in exc_name or indicator.lower() in exc_str:
                return ERROR_TIMEOUT

        for indicator in ErrorClassifier._VALIDATION_INDICATORS:
            if indicator in exc_name or indicator.lower() in exc_str:
                return ERROR_VALIDATION

        return ERROR_UNKNOWN

    @staticmethod
    def is_retryable(error_type: str) -> bool:
        """
        Return True if the error type is retryable.

        Network and timeout errors are retryable; validation errors are not.
        """
        return error_type in {ERROR_NETWORK, ERROR_TIMEOUT}


class ErrorQueueService:
    """
    Queues failed pipeline records for reprocessing with exponential backoff.

    For production use, pass an SQS client and CloudWatch client.
    For testing, the default in-memory stores are used.
    """

    def __init__(
        self,
        sqs_client=None,
        cloudwatch_client=None,
        queue_url: str = "",
        dlq_url: str = "",
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        clock: Optional[Callable[[], float]] = None,
        jitter: Optional[Callable[[], float]] = None,
    ):
        """
        Args:
            sqs_client: boto3 SQS client (optional). When None, in-memory queue is used.
            cloudwatch_client: boto3 CloudWatch client (optional). When None, in-memory log list is used.
            queue_url: SQS queue URL for production use.
            dlq_url: SQS dead-letter queue URL for production use.
            max_retries: Maximum retry attempts before moving to dead-letter queue.
            base_delay: Base delay in seconds for exponential backoff.
            clock: Callable returning current epoch seconds (for testing).
            jitter: Callable returning a random float in [0, 1) (for testing).
        """
        self._sqs = sqs_client
        self._cloudwatch = cloudwatch_client
        self._queue_url = queue_url
        self._dlq_url = dlq_url
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._clock = clock or time.time
        self._jitter = jitter or random.random

        # In-memory stores (used when no AWS clients are provided)
        self._queue: List[Dict[str, Any]] = []
        self._dead_letter: List[Dict[str, Any]] = []
        self._error_logs: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def enqueue_failed_record(
        self,
        record_id: str,
        contract_id: str,
        error_type: str,
        error_message: str,
        record_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Queue a failed record with all context needed for reprocessing.

        Args:
            record_id: Unique identifier for the failed record.
            contract_id: Associated data contract ID.
            error_type: One of "network", "validation", "timeout", "unknown".
            error_message: Human-readable error description.
            record_data: The original record payload.
            metadata: Additional context (e.g. step, source).

        Returns:
            The queued record dict.
        """
        if error_type not in VALID_ERROR_TYPES:
            error_type = ERROR_UNKNOWN

        record = {
            "queue_id": str(uuid.uuid4()),
            "record_id": record_id,
            "contract_id": contract_id,
            "error_type": error_type,
            "error_message": error_message,
            "record_data": record_data or {},
            "metadata": metadata or {},
            "retry_count": 0,
            "max_retries": self._max_retries,
            "status": STATUS_QUEUED,
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
            "timestamp": self._clock(),
        }

        self._put_record(record)

        logger.info(
            "Enqueued failed record record_id=%s contract_id=%s error_type=%s",
            record_id,
            contract_id,
            error_type,
        )
        return record

    def dequeue_records(self, max_records: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve up to *max_records* queued records for reprocessing.

        Marks returned records as "processing".
        """
        records: List[Dict[str, Any]] = []
        for rec in self._queue:
            if rec["status"] == STATUS_QUEUED:
                rec["status"] = STATUS_PROCESSING
                records.append(rec)
                if len(records) >= max_records:
                    break
        return records

    def reprocess_record(
        self, queued_record: Dict[str, Any], func: Callable[[], Any]
    ) -> Any:
        """
        Attempt to reprocess a queued record.

        - Increments retry_count.
        - If retry_count > max_retries, moves to dead-letter queue.
        - On success, removes from queue.
        - On failure, re-enqueues with incremented retry_count.

        Returns:
            The result of *func* on success.

        Raises:
            ErrorQueueError: If the record has exceeded max retries.
        """
        queued_record["retry_count"] += 1
        retry_count = queued_record["retry_count"]
        max_retries = queued_record.get("max_retries", self._max_retries)

        if retry_count > max_retries:
            self._move_to_dead_letter(queued_record)
            raise ErrorQueueError(
                f"Record {queued_record['record_id']} exceeded max retries ({max_retries}). "
                f"Moved to dead-letter queue.",
                step="reprocess",
                contract_id=queued_record.get("contract_id", ""),
            )

        # Calculate exponential backoff with jitter
        delay = self._calculate_backoff(retry_count)
        logger.info(
            "Reprocessing record_id=%s retry=%d/%d backoff=%.2fs",
            queued_record["record_id"],
            retry_count,
            max_retries,
            delay,
        )

        try:
            result = func()
            # Success — remove from queue
            self._remove_record(queued_record["queue_id"])
            return result
        except Exception as exc:
            # Failure — re-enqueue with incremented retry_count
            queued_record["status"] = STATUS_QUEUED
            queued_record["error_message"] = str(exc)
            queued_record["timestamp"] = self._clock()
            logger.warning(
                "Reprocess failed for record_id=%s retry=%d: %s",
                queued_record["record_id"],
                retry_count,
                exc,
            )
            raise

    def get_dead_letter_records(self) -> List[Dict[str, Any]]:
        """Return all records that exceeded max retries."""
        return list(self._dead_letter)

    def log_error(
        self,
        record_id: str,
        contract_id: str,
        error_type: str,
        error_message: str,
        step: str = "unknown",
    ) -> Dict[str, Any]:
        """
        Log a detailed error with record identifiers in CloudWatch-compatible format.

        Returns:
            The structured log entry dict.
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": "ERROR",
            "record_id": record_id,
            "contract_id": contract_id,
            "error_type": error_type,
            "error_message": error_message,
            "step": step,
            "action": self._suggest_action(error_type),
        }

        self._error_logs.append(log_entry)

        logger.error(
            "record_id=%s contract_id=%s step=%s error_type=%s: %s",
            record_id,
            contract_id,
            step,
            error_type,
            error_message,
        )
        return log_entry

    def get_queue_stats(self) -> Dict[str, int]:
        """Return counts by status: queued, processing, dead_letter."""
        stats = {STATUS_QUEUED: 0, STATUS_PROCESSING: 0, STATUS_DEAD_LETTER: 0}
        for rec in self._queue:
            status = rec.get("status", STATUS_QUEUED)
            if status in stats:
                stats[status] += 1
        stats[STATUS_DEAD_LETTER] = len(self._dead_letter)
        return stats

    def get_error_logs(self) -> List[Dict[str, Any]]:
        """Return all logged errors (in-memory mode)."""
        return list(self._error_logs)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _calculate_backoff(self, retry_count: int) -> float:
        """Exponential backoff: base_delay * 2^(retry_count-1) + jitter."""
        delay = self._base_delay * (2 ** (retry_count - 1))
        jitter = self._jitter() * self._base_delay
        return delay + jitter

    def _move_to_dead_letter(self, record: Dict[str, Any]) -> None:
        """Move a record to the dead-letter queue."""
        record["status"] = STATUS_DEAD_LETTER
        record["dead_letter_at"] = datetime.now(timezone.utc).isoformat()
        self._remove_record(record["queue_id"])
        self._dead_letter.append(record)
        logger.warning(
            "Record moved to dead-letter queue: record_id=%s contract_id=%s",
            record["record_id"],
            record.get("contract_id", ""),
        )

    def _put_record(self, record: Dict[str, Any]) -> None:
        """Add a record to the queue."""
        self._queue.append(record)

    def _remove_record(self, queue_id: str) -> None:
        """Remove a record from the queue by queue_id."""
        self._queue = [r for r in self._queue if r["queue_id"] != queue_id]

    @staticmethod
    def _suggest_action(error_type: str) -> str:
        """Return an actionable suggestion based on error type."""
        actions = {
            ERROR_NETWORK: "Retry after verifying network connectivity.",
            ERROR_TIMEOUT: "Retry with increased timeout or check service health.",
            ERROR_VALIDATION: "Fix record data to match schema before resubmitting.",
            ERROR_UNKNOWN: "Investigate error details and retry if appropriate.",
        }
        return actions.get(error_type, actions[ERROR_UNKNOWN])
