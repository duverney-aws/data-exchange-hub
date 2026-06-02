"""
Unit Tests for CircuitBreakerService.

Validates:
- Circuit breaker state transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
- Failure threshold tracking
- Recovery timeout behaviour
- ServiceCallWrapper for Glue, Athena, Bedrock

Requirements: 15.5
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.circuit_breaker_service import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerOpenError,
    CircuitState,
    ServiceCallWrapper,
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_RECOVERY_TIMEOUT,
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
def breaker(clock):
    return CircuitBreaker(
        service_name="test-service",
        failure_threshold=3,
        recovery_timeout=30,
        clock=clock,
    )


# ---------------------------------------------------------------------------
# CircuitBreaker — CLOSED state
# ---------------------------------------------------------------------------

class TestClosedState:
    """Requirement 15.5: Normal operation passes calls through."""

    def test_initial_state_is_closed(self, breaker):
        assert breaker.get_state() == "CLOSED"
        assert breaker.get_failure_count() == 0

    def test_successful_call_returns_result(self, breaker):
        result = breaker.call(_ok_func, "hello")
        assert result == "hello"
        assert breaker.get_state() == "CLOSED"
        assert breaker.get_failure_count() == 0

    def test_failure_increments_count(self, breaker):
        with pytest.raises(RuntimeError):
            breaker.call(_fail_func)
        assert breaker.get_failure_count() == 1
        assert breaker.get_state() == "CLOSED"

    def test_success_resets_failure_count(self, breaker):
        # Two failures, then a success
        for _ in range(2):
            with pytest.raises(RuntimeError):
                breaker.call(_fail_func)
        assert breaker.get_failure_count() == 2

        breaker.call(_ok_func)
        assert breaker.get_failure_count() == 0
        assert breaker.get_state() == "CLOSED"


# ---------------------------------------------------------------------------
# CircuitBreaker — CLOSED → OPEN transition
# ---------------------------------------------------------------------------

class TestClosedToOpen:
    """Requirement 15.5: Opens after failure_threshold consecutive failures."""

    def test_transitions_to_open_at_threshold(self, breaker):
        for _ in range(3):
            with pytest.raises(RuntimeError):
                breaker.call(_fail_func)
        assert breaker.get_state() == "OPEN"
        assert breaker.get_failure_count() == 3

    def test_stays_closed_below_threshold(self, breaker):
        for _ in range(2):
            with pytest.raises(RuntimeError):
                breaker.call(_fail_func)
        assert breaker.get_state() == "CLOSED"


# ---------------------------------------------------------------------------
# CircuitBreaker — OPEN state
# ---------------------------------------------------------------------------

class TestOpenState:
    """Requirement 15.5: OPEN rejects calls immediately."""

    def test_rejects_call_with_circuit_breaker_open_error(self, breaker):
        # Trip the breaker
        for _ in range(3):
            with pytest.raises(RuntimeError):
                breaker.call(_fail_func)

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            breaker.call(_ok_func)
        assert "test-service" in str(exc_info.value)

    def test_does_not_invoke_function_when_open(self, breaker):
        for _ in range(3):
            with pytest.raises(RuntimeError):
                breaker.call(_fail_func)

        call_count = 0

        def counting_func():
            nonlocal call_count
            call_count += 1
            return "result"

        with pytest.raises(CircuitBreakerOpenError):
            breaker.call(counting_func)
        assert call_count == 0


# ---------------------------------------------------------------------------
# CircuitBreaker — OPEN → HALF_OPEN transition
# ---------------------------------------------------------------------------

class TestOpenToHalfOpen:
    """Requirement 15.5: Transitions to HALF_OPEN after recovery_timeout."""

    def test_transitions_after_timeout(self, breaker, clock):
        for _ in range(3):
            with pytest.raises(RuntimeError):
                breaker.call(_fail_func)
        assert breaker.get_state() == "OPEN"

        clock.advance(30)
        assert breaker.get_state() == "HALF_OPEN"

    def test_stays_open_before_timeout(self, breaker, clock):
        for _ in range(3):
            with pytest.raises(RuntimeError):
                breaker.call(_fail_func)

        clock.advance(29)
        assert breaker.get_state() == "OPEN"


# ---------------------------------------------------------------------------
# CircuitBreaker — HALF_OPEN state
# ---------------------------------------------------------------------------

class TestHalfOpenState:
    """Requirement 15.5: HALF_OPEN allows one test call."""

    def test_success_transitions_to_closed(self, breaker, clock):
        for _ in range(3):
            with pytest.raises(RuntimeError):
                breaker.call(_fail_func)
        clock.advance(30)
        assert breaker.get_state() == "HALF_OPEN"

        result = breaker.call(_ok_func, "recovered")
        assert result == "recovered"
        assert breaker.get_state() == "CLOSED"
        assert breaker.get_failure_count() == 0

    def test_failure_transitions_back_to_open(self, breaker, clock):
        for _ in range(3):
            with pytest.raises(RuntimeError):
                breaker.call(_fail_func)
        clock.advance(30)
        assert breaker.get_state() == "HALF_OPEN"

        with pytest.raises(RuntimeError):
            breaker.call(_fail_func)
        assert breaker.get_state() == "OPEN"


# ---------------------------------------------------------------------------
# CircuitBreaker — reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_manual_reset_returns_to_closed(self, breaker):
        for _ in range(3):
            with pytest.raises(RuntimeError):
                breaker.call(_fail_func)
        assert breaker.get_state() == "OPEN"

        breaker.reset()
        assert breaker.get_state() == "CLOSED"
        assert breaker.get_failure_count() == 0

    def test_call_works_after_reset(self, breaker):
        for _ in range(3):
            with pytest.raises(RuntimeError):
                breaker.call(_fail_func)
        breaker.reset()

        result = breaker.call(_ok_func, "after-reset")
        assert result == "after-reset"


# ---------------------------------------------------------------------------
# CircuitBreaker — default configuration
# ---------------------------------------------------------------------------

class TestDefaults:
    def test_default_threshold(self):
        cb = CircuitBreaker(service_name="svc")
        assert cb._failure_threshold == DEFAULT_FAILURE_THRESHOLD

    def test_default_recovery_timeout(self):
        cb = CircuitBreaker(service_name="svc")
        assert cb._recovery_timeout == DEFAULT_RECOVERY_TIMEOUT


# ---------------------------------------------------------------------------
# ServiceCallWrapper
# ---------------------------------------------------------------------------

class TestServiceCallWrapper:
    """Requirement 15.5: Pre-configured breakers for Glue, Athena, Bedrock."""

    def test_supported_services(self):
        wrapper = ServiceCallWrapper()
        assert ServiceCallWrapper.SUPPORTED_SERVICES == {"glue", "athena", "bedrock"}

    def test_call_through_glue_breaker(self):
        wrapper = ServiceCallWrapper()
        result = wrapper.call("glue", _ok_func, "glue-result")
        assert result == "glue-result"

    def test_call_through_athena_breaker(self):
        wrapper = ServiceCallWrapper()
        result = wrapper.call("athena", _ok_func, "athena-result")
        assert result == "athena-result"

    def test_call_through_bedrock_breaker(self):
        wrapper = ServiceCallWrapper()
        result = wrapper.call("bedrock", _ok_func, "bedrock-result")
        assert result == "bedrock-result"

    def test_unsupported_service_raises_value_error(self):
        wrapper = ServiceCallWrapper()
        with pytest.raises(ValueError, match="Unsupported service"):
            wrapper.call("dynamodb", _ok_func)

    def test_case_insensitive_service_name(self):
        wrapper = ServiceCallWrapper()
        result = wrapper.call("Glue", _ok_func, "ok")
        assert result == "ok"

    def test_get_breaker_returns_instance(self):
        wrapper = ServiceCallWrapper()
        breaker = wrapper.get_breaker("athena")
        assert isinstance(breaker, CircuitBreaker)

    def test_get_all_states(self):
        wrapper = ServiceCallWrapper()
        states = wrapper.get_all_states()
        assert states == {"glue": "CLOSED", "athena": "CLOSED", "bedrock": "CLOSED"}

    def test_bedrock_has_lower_threshold(self):
        wrapper = ServiceCallWrapper()
        bedrock = wrapper.get_breaker("bedrock")
        assert bedrock._failure_threshold == 3

    def test_glue_breaker_opens_after_failures(self):
        clock = FakeClock()
        wrapper = ServiceCallWrapper(clock=clock)
        # Glue threshold is 5
        for _ in range(5):
            with pytest.raises(RuntimeError):
                wrapper.call("glue", _fail_func)
        assert wrapper.get_breaker("glue").get_state() == "OPEN"

    def test_wrapper_with_custom_clock(self):
        clock = FakeClock()
        wrapper = ServiceCallWrapper(clock=clock)
        breaker = wrapper.get_breaker("bedrock")
        # Trip bedrock (threshold=3)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                wrapper.call("bedrock", _fail_func)
        assert breaker.get_state() == "OPEN"

        clock.advance(90)
        assert breaker.get_state() == "HALF_OPEN"


# ---------------------------------------------------------------------------
# Error classes
# ---------------------------------------------------------------------------

class TestErrorClasses:
    def test_circuit_breaker_error_attributes(self):
        err = CircuitBreakerError("msg", step="step1", contract_id="C-001")
        assert str(err) == "msg"
        assert err.step == "step1"
        assert err.contract_id == "C-001"

    def test_circuit_breaker_open_error_attributes(self):
        err = CircuitBreakerOpenError(service_name="glue", contract_id="C-002")
        assert "glue" in str(err)
        assert err.service_name == "glue"
        assert err.contract_id == "C-002"
        assert err.step == "circuit_breaker_open"
