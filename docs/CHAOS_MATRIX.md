# Goddess AI / AI-Modrator — Chaos & Fault Injection Matrix

This document defines all simulated fault modes, recovery behaviors, automated mitigations, and verification results across Goddess AI subsystems.

---

## Fault Injection Matrix

| Fault ID | Injected Failure | Target Subsystem | Expected System Behavior | Automated Mitigation | Verification Test | Result |
|---|---|---|---|---|---|---|
| **CHAOS-01** | Redis server killed or connection dropped | Cache, PubSub, Distributed Locks | In unified mode: fallback to in-memory store. In decoupled mode: DistributedLock fails closed and EventBus reports DEGRADED/UNHEALTHY to prevent duplicate workers. | `InMemoryRedisFallback` auto-engages in unified; `DistributedLock` fails closed in decoupled; health reports `DEGRADED`. | `tests/chaos/test_redis_failure_modes.py` | **PASS** |
| **CHAOS-02** | YouTube quota 100% depleted (4,000 units consumed) | YouTube Ingestion | Hard cap enforced. Prevent further polling calls that incur quota cost. | Polling intervals stretch to 15s; `YouTubeQuotaWarning` event emitted; Discord alert dispatched. | `tests/chaos/test_quota_stress.py` | **PASS** |
| **CHAOS-03** | YouTube API returns HTTP 403 quotaExceeded on key slot 0 | API Key Pool | Key marked `EXHAUSTED` and placed in cooldown. Active requests seamlessly switch to slot 1. | `ApiKeyPool` activates slot 1; emits `YouTubeKeyCooldown` event; no chat message drops. | `tests/chaos/test_youtube_chaos.py` | **PASS** |
| **CHAOS-04** | Primary OpenRouter model timeout / 500 error | AI Gateway / Co-Host | Fast failure detection; fallback model triggered without user interruption. | Circuit breaker records failure; `ModelRouter` cascades to `google/gemini-2.0-flash-001`. | `tests/chaos/test_ai_chaos.py` | **PASS** |
| **CHAOS-05** | OpenRouter continuous outage (5 consecutive failures) | AI Gateway | Circuit breaker trips to `OPEN` state. Fast-fails requests without exhausting credits or blocking chat loops. | Co-host falls back to local deterministic rule templates; health reports `openrouter: DEGRADED`. | `tests/unit/test_circuit_breaker.py` | **PASS** |
| **CHAOS-06** | Stream worker session crashes due to malformed XML feed | Stream Ingestion | Crashed stream enters `RECONNECTING` with exponential backoff and jitter. Unrelated streams unaffected. | Stream worker supervisor restarts session; other 6 streams continue running without disruption. | `tests/chaos/test_stream_failure_matrix.py` | **PASS** |
| **CHAOS-07** | Concurrent administrative actions on same stream session | Stream Control API | Race conditions prevented via per-stream mutex locks. | Idempotent control endpoint returns stable state; second call acknowledges action already completed. | `tests/unit/test_stream_control_idempotency.py` | **PASS** |
| **CHAOS-08** | Injected double-entry ledger imbalance | Economy Ledger | Detected by automated background integrity check. | `IntegrityCheckService` catches non-zero transaction balance; dispatches `CRITICAL` incident. | `tests/unit/test_integrity_pipeline.py` | **PASS** |
| **CHAOS-09** | Concurrent incident creation for identical outage | Incident Engine | Prevents alert storms and duplicate database records. | Fingerprint lock groups identical failures into existing active incident; increments recurrence counter. | `tests/unit/test_incident_race_conditions.py` | **PASS** |
| **CHAOS-10** | Discord API outage / 503 / 429 rate limit | Discord Ops | Prevents chat worker threads from blocking or failing when Discord is down. | Messages buffered in bounded async retry queue (max 1000); exponential backoff draining on recovery. | `tests/unit/test_discord_operations.py` | **PASS** |
