# Incident Runbook: PostgreSQL Outage or Connection Pool Exhaustion

## Severity
- **CRITICAL**: PostgreSQL is the durable authority for economy ledger, viewer profiles, and moderation audits.

## Symptoms
- Health endpoint `/health/detailed` reports `database.status: CRITICAL`.
- API endpoints return HTTP 503 or database timeout errors.
- Active transactions fail to acquire connection locks.

## Immediate Mitigation Steps
1. **Check Railway PostgreSQL Resource Utilization**:
   - Inspect CPU, RAM, and Disk space in Railway Dashboard -> PostgreSQL.
   - If memory is pinned near 100%, check active connection count (`SELECT count(*) FROM pg_stat_activity;`).
2. **Tune Connection Pool Settings**:
   - Verify environment variables:
     - `DB_POOL_SIZE`: default 20
     - `DB_MAX_OVERFLOW`: default 10
     - `DB_POOL_TIMEOUT`: default 30s
3. **Kill Orphaned or Stale Locks**:
   - If hung transactions are locking rows in `economy_accounts`:
     ```sql
     SELECT pid, age(clock_timestamp(), query_start), usename, query 
     FROM pg_stat_activity 
     WHERE state != 'idle' AND query_start < now() - interval '5 minutes';
     ```
   - Terminate offending PID: `SELECT pg_terminate_backend(<pid>);`.
4. **Scale Up Railway Database Tier**:
   - If connections consistently saturate under 7 concurrent heavy streams, scale PostgreSQL compute on Railway from starter to pro tier.

## Post-Recovery Verification
- Run database integrity check via `GET /api/v1/dashboard/overview`.
- Ensure double-entry ledger equality holds across all accounts.
