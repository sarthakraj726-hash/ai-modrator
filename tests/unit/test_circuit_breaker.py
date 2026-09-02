"""Unit tests for Circuit Breaker."""

import pytest

from app.core.exceptions import CircuitBreakerOpenError
from app.utils.circuit_breaker import CircuitBreaker, CircuitState


@pytest.mark.asyncio
async def test_circuit_breaker_tripping():
    cb = CircuitBreaker(
        name="test-breaker",
        failure_threshold=3,
        recovery_timeout_seconds=0.5,
    )
    assert cb.state == CircuitState.CLOSED

    async def faulty_task():
        raise RuntimeError("Service failure")

    # 3 failures trip circuit
    for _ in range(3):
        with pytest.raises(RuntimeError):
            await cb.execute(faulty_task)

    assert cb.state == CircuitState.OPEN

    # While OPEN, calls fail fast with CircuitBreakerOpenError
    with pytest.raises(CircuitBreakerOpenError):
        await cb.execute(faulty_task)
