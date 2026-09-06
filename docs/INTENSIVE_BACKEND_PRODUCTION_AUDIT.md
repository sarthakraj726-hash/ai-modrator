# Intensive backend production audit

## 1. Executive summary

The backend was inspected through runtime entry points, authentication, dashboard operations, AI moderation/co-host dispatch, YouTube clients, quota/key pools, workers, SSE, migrations, Redis fallbacks, repositories, WebSub, and economy tests. Five verified defects were fixed. The local synthetic suite exercises 269 tests across unit, integration, security, chaos, and multi-stream simulation paths.

## 2. Baseline state

`compileall` completed successfully. The bundled Python runtime initially lacked `pytest` and `ruff`; declared development dependencies were installed into the ignored `.pydeps` sandbox directory. Baseline targeted security/SSE tests passed (12). Baseline Ruff reported six hygiene faults.

## 3. Critical findings

| Severity | Subsystem | File | Problem | Reproduction | Fix | Regression test |
| --- | --- | --- | --- | --- | --- | --- |
| High | Admin/OAuth | `app/api/routes/dashboard.py` | Auth status returned a partial OAuth token. | Integration dashboard flow exposed the `ya29.` prefix. | Removed token preview entirely. | `test_dashboard_full_flow` asserts the token is absent. |
| High | Moderation | `app/moderation/engine.py` | AI classification outage converted ambiguous content to automatic allow. | Chaos provider 500 scenario. | Fail closed to `FLAG_FOR_REVIEW` with human-review requirement. | `test_moderation_ai_failure`, updated AI chaos test. |
| Medium | Workers | `app/workers/session.py` | Join-message OAuth write delayed initial chat ingestion; seven workers processed zero messages. | `test_seven_stream_concurrent_capacity`. | Supervised nonblocking greeting task, cancelled during shutdown. | Seven-stream capacity plus worker/chaos tests. |
| Medium | Coalescing | `app/ai/coalescer.py`, `app/youtube/coalescer.py` | Leader failure without followers left exception futures unobserved. | Provider timeout generated `Future exception was never retrieved`. | Mark mirrored Future failures observed while preserving follower propagation. | Coalescer regression and AI chaos run. |
| High | Deployment/migrations | `Dockerfile`, `railway.toml`, `app/db/session.py` | Migration errors were ignored or could be stamped past, permitting runtime schema drift. | Static inspection of `alembic upgrade head || true` and startup handling. | Deployment now fails before Uvicorn; production re-raises migration failure and never stamps an unknown revision. | `test_deployment_migrations`, lifecycle/startup tests. |

## 4. AI moderator and co-host verification

Moderation normalization, multilingual fixtures, local rules, policy matrix, HITL service, provider failure, and golden data tests passed. Provider failures now route ambiguous messages to a reviewer rather than auto-enforcement or auto-allow. Co-host OutputGuard, persona, trigger, and stream-intelligence integration tests passed; source inspection confirms generated replies pass through `OutputGuard.sanitize` before chat delivery.

## 5. YouTube verification

Mocked client, OAuth separation, key-pool cooldown/rotation, quota reservations, URL resolution, fake broadcast/live-chat transport, stream bootstrap, WebSub parser/lifecycle, and chaos failure tests passed. Read/write credential separation is verified through unit fixtures. **NOT VERIFIED — EXTERNAL ENVIRONMENT REQUIRED:** live YouTube API/OAuth behavior and provider quotas were not invoked.

## 6. Worker, Redis, database, and security verification

SQLite migrations/startup/shutdown, repositories, ledger integrity, bounded chat queue, Redis in-memory fallback, distributed lock behavior, event bus, worker lifecycle, and seven-stream isolation were exercised. Auth/RBAC, creator isolation, redaction, CORS, config validation, and dashboard authentication tests passed. Docker was unavailable, so container build was not executed.

## 7. Sandbox results

The sandbox used in-memory SQLite, the test Redis fallback, fake OpenRouter/YouTube adapters, ASGI clients, and mocked external HTTP. Results: unit **200 passed**, chaos **18 passed**, integration/security/simulation **51 passed** (269 total). Targeted post-fix lifecycle/security checks: **13 passed**. Ruff: **passed**. Python syntax compilation: **passed**.

## 8. Remaining risks

- **NOT VERIFIED — EXTERNAL ENVIRONMENT REQUIRED:** real PostgreSQL, Redis, Railway container, YouTube OAuth/Data API, OpenRouter, and Discord operations require non-production sandbox credentials and infrastructure.
- The process executes migrations both in the deploy command and application startup. This is safe only if migrations are serialized by the deployment platform; concurrent multi-replica releases should use a dedicated one-shot migration job.

## 9. Production readiness decision

**READY WITH EXTERNAL VERIFICATION REQUIRED.** Local correctness, failure injection, concurrency, isolation, security, and startup evidence is strong. The listed external services and a containerized PostgreSQL/Redis deployment still require validation before declaring live production readiness.
