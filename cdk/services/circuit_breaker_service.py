"""
Circuit Breaker Service

Implements the circuit breaker pattern for downstream AWS service calls
(Glue, Athena, Bedrock) to prevent cascading failures when services
are unavailable.

States:
- CLOSED: Normal operation, calls pass through.
- OPEN: Service is failing, calls are rejected immediately.
- HALF_OPEN: Testing recovery, one call is allowed through.

Requirements: 15.5
"""
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# Defaults
DEFAULT_FAILURE_THRESHOLD = 5
DEFAULT_RECOVERY_TIMEOUT = 60  # seconds


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerError(Exception):
    """Base exception for circuit breaker operations."""

    def __init__(self, message: str, step: str = "circuit_breaker", contract_id: str = ""):
        self.step = step
        self.contract_id = contract_id
        super().__init__(message)


class CircuitBreakerOpenError(CircuitBreakerError):
    """Raised when a call is attempted while the circuit is OPEN."""

    def __init__(self, service_name: str = "unknown", contract_id: str = ""):
        super().__init__(
            f"Circuit breaker is OPEN for service '{service_name}'. Call rejected to prevent cascading failure.",
            step="circuit_breaker_open",
            contract_id=contract_id,
        )
        self.service_name = service_name


class CircuitBreaker:
    """
    Circuit breaker for downstream service calls.

    Tracks failures and transitions between CLOSED → OPEN → HALF_OPEN states
    to prevent cascading failures when a downstream service is unavailable.
    """

    def __init__(
        self,
        service_name: str = "unknown",
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        recovery_timeout: int = DEFAULT_RECOVERY_TIMEOUT,
        clock: Optional[Callable[[], float]] = None,
    ):
        """
        Args:
            service_name: Human-readable name of the downstream service.
            failure_threshold: Number of consecutive failures before opening.
            recovery_timeout: Seconds to wait before transitioning OPEN → HALF_OPEN.
            clock: Callable returning current time in seconds (for testing).
        """
        self._service_name = service_name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._clock = clock or time.time

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: Optional[float] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Execute *func* through the circuit breaker.

        - CLOSED: pass through; track failures.
        - OPEN: reject immediately with CircuitBreakerOpenError
                 unless recovery_timeout has elapsed (transition to HALF_OPEN).
        - HALF_OPEN: allow one test call; success → CLOSED, failure → OPEN.
        """
        self._check_state_transition()

        if self._state == CircuitState.OPEN:
            logger.warning(
                "Circuit OPEN for '%s' — rejecting call (failures=%d)",
                self._service_name,
                self._failure_count,
            )
            raise CircuitBreakerOpenError(service_name=self._service_name)

        # CLOSED or HALF_OPEN — attempt the call
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def get_state(self) -> str:
        """Return the current circuit state as a string."""
        self._check_state_transition()
        return self._state.value

    def get_failure_count(self) -> int:
        """Return the current consecutive failure count."""
        return self._failure_count

    def reset(self) -> None:
        """Manually reset the breaker to CLOSED with zero failures."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        logger.info("Circuit breaker for '%s' manually reset to CLOSED.", self._service_name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_state_transition(self) -> None:
        """Transition OPEN → HALF_OPEN if recovery_timeout has elapsed."""
        if self._state == CircuitState.OPEN and self._last_failure_time is not None:
            elapsed = self._clock() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                logger.info(
                    "Recovery timeout elapsed for '%s' — transitioning to HALF_OPEN.",
                    self._service_name,
                )
                self._state = CircuitState.HALF_OPEN

    def _on_success(self) -> None:
        """Handle a successful call."""
        if self._state == CircuitState.HALF_OPEN:
            logger.info(
                "Test call succeeded for '%s' — transitioning to CLOSED.",
                self._service_name,
            )
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None

    def _on_failure(self) -> None:
        """Handle a failed call."""
        self._failure_count += 1
        self._last_failure_time = self._clock()

        if self._state == CircuitState.HALF_OPEN:
            logger.warning(
                "Test call failed for '%s' — transitioning back to OPEN.",
                self._service_name,
            )
            self._state = CircuitState.OPEN
        elif self._failure_count >= self._failure_threshold:
            logger.warning(
                "Failure threshold reached for '%s' (%d/%d) — transitioning to OPEN.",
                self._service_name,
                self._failure_count,
                self._failure_threshold,
            )
            self._state = CircuitState.OPEN


class ServiceCallWrapper:
    """
    Pre-configured circuit breakers for the downstream AWS services
    used by the Pharma Data Exchange Hub pipeline.

    Provides named breakers for Glue, Athena, and Bedrock so callers
    don't need to manage CircuitBreaker instances directly.
    """

    # Default service configurations
    SERVICE_DEFAULTS: Dict[str, Dict[str, int]] = {
        "glue": {"failure_threshold": 5, "recovery_timeout": 60},
        "athena": {"failure_threshold": 5, "recovery_timeout": 60},
        "bedrock": {"failure_threshold": 3, "recovery_timeout": 90},
    }

    SUPPORTED_SERVICES = set(SERVICE_DEFAULTS.keys())

    def __init__(self, clock: Optional[Callable[[], float]] = None):
        self._clock = clock
        self._breakers: Dict[str, CircuitBreaker] = {}
        for name, cfg in self.SERVICE_DEFAULTS.items():
            self._breakers[name] = CircuitBreaker(
                service_name=name,
                failure_threshold=cfg["failure_threshold"],
                recovery_timeout=cfg["recovery_timeout"],
                clock=self._clock,
            )

    def call(self, service_name: str, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Execute *func* through the circuit breaker for *service_name*.

        Raises:
            ValueError: If *service_name* is not a supported service.
            CircuitBreakerOpenError: If the breaker is OPEN.
        """
        breaker = self._get_breaker(service_name)
        return breaker.call(func, *args, **kwargs)

    def get_breaker(self, service_name: str) -> CircuitBreaker:
        """Return the CircuitBreaker instance for *service_name*."""
        return self._get_breaker(service_name)

    def get_all_states(self) -> Dict[str, str]:
        """Return a dict of service_name → current state for all breakers."""
        return {name: breaker.get_state() for name, breaker in self._breakers.items()}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_breaker(self, service_name: str) -> CircuitBreaker:
        svc = service_name.lower()
        if svc not in self._breakers:
            raise ValueError(
                f"Unsupported service '{service_name}'. "
                f"Supported: {sorted(self.SUPPORTED_SERVICES)}"
            )
        return self._breakers[svc]
