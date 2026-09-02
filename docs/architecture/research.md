# Architecture Research & Engineering Principles

## 1. Multi-Stream Isolation Architecture
**Problem**: In a multi-channel YouTube live system handling 6–7 concurrent streams, any unexpected runtime exception (e.g., chat parsing error, YouTube HTTP 500/429, memory spike) in one stream worker must never crash or degrade any other active stream worker.

**Research & Reference Patterns**:
- **Actor / Isolated Task Pattern**: Erlang/Elixir supervision trees and Python `asyncio` task supervision.
- **Decision**: Each YouTube stream connection is encapsulated within its own dedicated `StreamSession` instance managed by `WorkerManager`. Each session has its own cancellation token (`asyncio.Event`), independent error boundary, separate state tracking, and independent log/correlation context. Global stream variables (e.g., `current_stream`) are strictly prohibited.

## 2. YouTube Data API Quota Management & Budgeting
**Problem**: Standard YouTube Data API v3 daily quota is limited (default 10,000 units, allocated application budget: 4,000 units/day). Unchecked polling or frequent requests quickly exhaust the quota.

**Research & Reference Patterns**:
- **Pre-allocation / Reservation Pattern**: Two-phase reservation (`reserve()` -> execute -> `consume()` or `release_if_failed_before_request()`).
- **Distributed Token / Unit Tracking**: Atomic counter tracking in Redis with in-memory synchronization fallback.
- **Multi-Key Pooling**: Resilient round-robin / least-used key allocation across `YOUTUBE_API_KEY_1`, `YOUTUBE_API_KEY_2`, `YOUTUBE_API_KEY_3` with individual health status, cooldown timers, and error recording.

## 3. Resilience, Circuit Breakers & Backoff
**Problem**: Remote API outages, temporary network drops, and transient HTTP 5xx errors require retries, while permanent errors (HTTP 401, 403, 400, quota exhausted) should never be retried.

**Research & Reference Patterns**:
- **Martin Fowler Circuit Breaker Pattern**: `CLOSED` (normal operation) -> `OPEN` (fail fast on threshold exceeded) -> `HALF-OPEN` (probe with canary request).
- **Full Jitter Exponential Backoff**: Prevents thundering herd problems (`sleep = min(max_delay, base_delay * 2^attempt) * random(0.5, 1.5)`).

## 4. Database & Storage Strategy
**Problem**: Need high-performance async relational storage with transactional integrity, JSONB support for flexible metadata/audit payloads, and automated migration management.

**Decision**:
- **SQLAlchemy 2.0 (Async)** with `asyncpg` for PostgreSQL in production.
- **Alembic** for schema migrations (never modify schemas at runtime).
- Tables: `creators`, `stream_sessions`, `audit_events`, `system_events` with proper UUIDs, foreign keys, cascading rules, and indexes.
- SQLite async (`aiosqlite`) support for automated testing and offline development.

## 5. Event-Driven Architecture
**Problem**: Decoupling stream workers, API handlers, future AI moderation, persona engines, and Discord logging.

**Decision**:
- Typed Pydantic events (`CreatorRegistered`, `StreamConnectRequested`, `StreamConnected`, `StreamDisconnected`, `StreamStarted`, `StreamEnded`, `StreamError`, `SystemWarning`, `SystemError`, `SystemCritical`).
- Redis Pub/Sub / Stream abstraction (`EventBus`) with local in-memory event dispatching fallback.
