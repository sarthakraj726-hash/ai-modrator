# Incident Runbook: Railway Deployment Failure or Container Crash Loop

## Severity
- **CRITICAL**: Application failing startup or readiness checks during deployment.

## Common Causes
- Alembic database migration syntax or foreign key mismatch during pre-deploy.
- Missing required environment variable (`DATABASE_URL`, `REDIS_URL`, `ADMIN_SECRET`).
- Healthcheck timeout before FastAPI lifespan startup completes.
- Incompatible dependency version in `requirements.txt`.

## Immediate Mitigation Steps
1. **Inspect Build and Deploy Logs on Railway**:
   - Check Railway Dashboard -> Deployments -> View Build / Deploy Logs.
   - Look for tracebacks during `preDeployCommand = "alembic upgrade head"`.
2. **Execute Rollback to Last Known Good Deployment**:
   - In Railway Deployments tab, locate the previous active deployment with green checkmark.
   - Click **Redeploy** on that deployment to instantly revert production traffic.
3. **Verify Database Migration Compatibility**:
   - Ensure new migrations are backward-compatible (expand before contract).
   - If a migration failed midway, connect via `railway run alembic current` to verify migration version.
4. **Inspect Healthcheck Configuration**:
   - Railway requires `/health/live` to return 200 within `healthcheckTimeout = 15`.
   - Ensure the port environment variable `PORT` is respected by Uvicorn.
