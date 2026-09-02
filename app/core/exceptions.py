"""Application domain and infrastructure exceptions."""

from typing import Any


class AppException(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, status_code: int = 500, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ConfigurationError(AppException):
    """Raised when required configuration or secrets are missing or invalid."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message=message, status_code=500, details=details)


class AuthenticationError(AppException):
    """Raised when authentication credentials are missing or invalid."""

    def __init__(self, message: str = "Invalid or missing authentication credentials"):
        super().__init__(message=message, status_code=401)


class AuthorizationError(AppException):
    """Raised when an authenticated actor lacks required permissions."""

    def __init__(self, message: str = "Forbidden: Insufficient permissions"):
        super().__init__(message=message, status_code=403)


class EntityNotFoundError(AppException):
    """Raised when a requested resource is not found."""

    def __init__(self, entity_type: str, identifier: Any):
        super().__init__(
            message=f"{entity_type} with identifier '{identifier}' not found",
            status_code=404,
            details={"entity_type": entity_type, "identifier": str(identifier)},
        )


class EntityAlreadyExistsError(AppException):
    """Raised when an entity with unique constraint already exists."""

    def __init__(self, entity_type: str, identifier: Any):
        super().__init__(
            message=f"{entity_type} with identifier '{identifier}' already exists",
            status_code=409,
            details={"entity_type": entity_type, "identifier": str(identifier)},
        )


class DatabaseError(AppException):
    """Raised on database failures."""

    def __init__(self, message: str = "Database operation failed", details: dict[str, Any] | None = None):
        super().__init__(message=message, status_code=500, details=details)


class RedisConnectionError(AppException):
    """Raised when Redis connection fails."""

    def __init__(self, message: str = "Redis service unavailable"):
        super().__init__(message=message, status_code=503)


class LockAcquisitionError(AppException):
    """Raised when a distributed lock cannot be acquired within timeout."""

    def __init__(self, lock_key: str):
        super().__init__(
            message=f"Could not acquire distributed lock for resource: '{lock_key}'",
            status_code=409,
            details={"lock_key": lock_key},
        )


class RateLimitExceededError(AppException):
    """Raised when a client or action exceeds the rate limit."""

    def __init__(self, retry_after_seconds: int = 60):
        super().__init__(
            message="Rate limit exceeded. Please try again later.",
            status_code=429,
            details={"retry_after_seconds": retry_after_seconds},
        )


# ==============================================================================
# YouTube Subsystem Exceptions
# ==============================================================================

class YouTubeAPIError(AppException):
    """Base exception for YouTube API interactions."""

    def __init__(self, message: str, status_code: int = 502, details: dict[str, Any] | None = None):
        super().__init__(message=message, status_code=status_code, details=details)


class YouTubeQuotaExceededError(YouTubeAPIError):
    """Raised when the 4,000 daily quota budget is exhausted."""

    def __init__(self, current_used: int, max_limit: int):
        super().__init__(
            message=f"YouTube daily quota limit reached ({current_used}/{max_limit} units)",
            status_code=429,
            details={"quota_used": current_used, "quota_limit": max_limit},
        )


class YouTubeKeyPoolExhaustedError(YouTubeAPIError):
    """Raised when all configured YouTube API keys are unavailable or in cooldown."""

    def __init__(self, message: str = "All YouTube API keys in pool are exhausted or in cooldown"):
        super().__init__(message=message, status_code=503)


class CircuitBreakerOpenError(AppException):
    """Raised when circuit breaker is open to prevent cascading failures."""

    def __init__(self, circuit_name: str, reset_time_seconds: float):
        super().__init__(
            message=f"Circuit breaker '{circuit_name}' is OPEN. Requests blocked to prevent failure cascade.",
            status_code=503,
            details={"circuit_name": circuit_name, "reset_time_seconds": reset_time_seconds},
        )


# ==============================================================================
# Stream Worker Exceptions
# ==============================================================================

class StreamSessionError(AppException):
    """Base exception for stream session workers."""

    def __init__(self, message: str, status_code: int = 500, details: dict[str, Any] | None = None):
        super().__init__(message=message, status_code=status_code, details=details)


class StreamSessionNotFoundError(StreamSessionError):
    """Raised when a stream session worker does not exist."""

    def __init__(self, session_id: str):
        super().__init__(
            message=f"Stream session '{session_id}' not found",
            status_code=404,
            details={"session_id": session_id},
        )


class StreamSessionAlreadyActiveError(StreamSessionError):
    """Raised when attempting to start a stream session that is already running."""

    def __init__(self, session_id: str):
        super().__init__(
            message=f"Stream session '{session_id}' is already active and running",
            status_code=409,
            details={"session_id": session_id},
        )
