# Production Operations Readiness Checklist

Comprehensive verification checklist before connecting live broadcast streams to Goddess AI on Railway.

---

## 1. Environment & Secrets
- [x] `DATABASE_URL` provisioned with async PostgreSQL (`postgresql+asyncpg://...`).
- [x] `REDIS_URL` provisioned with secure connection parameters.
- [x] `ADMIN_SECRET` configured with 64-character cryptographically secure token.
- [x] `YOUTUBE_API_KEYS` populated with 3+ distinct Google Cloud project API keys.
- [x] `OPENROUTER_API_KEY` configured and funded with usage credits.
- [x] `WEBSUB_SECRET` set to high-entropy shared secret.
- [x] Zero real secrets committed to git repository (verified by pre-commit regex scan).

---

## 2. Infrastructure & Railway Configuration
- [x] `railway.toml` configured with `preDeployCommand = "alembic upgrade head"`.
- [x] Healthcheck path configured as `/health/live` with 15s timeout.
- [x] Dual-service or unified deployment mode verified (`APP_SERVICE_MODE: unified`).
- [x] Container restart policy set to `on-failure` with max retries.
- [x] Memory limit configured with headroom for 7 concurrent stream workers.

---

## 3. Database & Ledger State
- [x] Alembic migrations verified at head (`alembic upgrade head`).
- [x] Double-entry ledger audit passes with zero delta ($\sum D == \sum C$).
- [x] All economy accounts have non-negative balances ($\ge 0$).
- [x] Stale stream sessions cleaned up or marked ended.

---

## 4. Subsystem Health Verification
- [x] `/health/live` returns HTTP 200 within <10ms.
- [x] `/health/ready` confirms database connectivity.
- [x] `/health/detailed` reports all subsystems as `HEALTHY` or `DEGRADED` (never `CRITICAL`).
- [x] Multi-key pool rotation verified under synthetic load.

---

## 5. Developer Control Center
- [x] Next.js frontend builds without TypeScript or styling errors (`npm run build`).
- [x] Live Stream Grid renders up to 7 concurrent channels with status indicators.
- [x] Manual connect modal resolves YouTube URLs and Video IDs safely.
- [x] Real-time SSE stream (`/api/v1/dashboard/events/stream`) pushes live telemetry.
- [x] HITL moderation queue allows approving or dismissing flagged messages.
