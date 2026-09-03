"""Unit tests for Stream State Machine legal transitions and validation."""

from app.db.models.stream_session import StreamStatus, validate_stream_transition


def test_legal_stream_state_transitions():
    """Verify standard happy-path stream lifecycle transitions are legal."""
    assert (
        validate_stream_transition(StreamStatus.REQUESTED.value, StreamStatus.VALIDATING.value)
        is True
    )
    assert (
        validate_stream_transition(StreamStatus.VALIDATING.value, StreamStatus.RESOLVING.value)
        is True
    )
    assert (
        validate_stream_transition(StreamStatus.RESOLVING.value, StreamStatus.CONNECTING.value)
        is True
    )
    assert (
        validate_stream_transition(StreamStatus.CONNECTING.value, StreamStatus.ACTIVE.value) is True
    )
    assert (
        validate_stream_transition(StreamStatus.ACTIVE.value, StreamStatus.RECONNECTING.value)
        is True
    )
    assert (
        validate_stream_transition(StreamStatus.RECONNECTING.value, StreamStatus.ACTIVE.value)
        is True
    )
    assert validate_stream_transition(StreamStatus.ACTIVE.value, StreamStatus.ENDING.value) is True
    assert validate_stream_transition(StreamStatus.ENDING.value, StreamStatus.ENDED.value) is True


def test_illegal_stream_state_transitions_rejected():
    """Verify illegal transitions are rejected to prevent false ACTIVE states."""
    # Cannot jump straight from REQUESTED to ACTIVE
    assert (
        validate_stream_transition(StreamStatus.REQUESTED.value, StreamStatus.ACTIVE.value) is False
    )

    # Cannot jump from VALIDATING straight to ACTIVE
    assert (
        validate_stream_transition(StreamStatus.VALIDATING.value, StreamStatus.ACTIVE.value)
        is False
    )

    # Cannot transition from CANCELLED to ACTIVE
    assert (
        validate_stream_transition(StreamStatus.CANCELLED.value, StreamStatus.ACTIVE.value) is False
    )

    # Cannot jump from ENDED straight to RECONNECTING
    assert (
        validate_stream_transition(StreamStatus.ENDED.value, StreamStatus.RECONNECTING.value)
        is False
    )
