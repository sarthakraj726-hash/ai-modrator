# Goddess AI / AI-Modrator — Operational Runbooks

This guide provides step-by-step Standard Operating Procedures (SOPs) for the operational maintenance and incident response of Goddess AI.

---

## Runbook 1: PostgreSQL Connection Pool Exhaustion / Failover

### Symptoms
- `/health/ready` or `/health/detailed` returns HTTP 503 or `CRITICAL` database status.
- Logs show `TimeoutError: QueuePool limit of size 20 overflow 10 reached`.
- High response latency on REST APIs.

### Diagnosis
1. Inspect active database sessions:
   ```sql
   SELECT count(*), state FROM pg_stat_activity GROUP BY state;
   ```
2. Check for long-running transactions:
   ```sql
   SELECT pid, now() - query_start AS duration, query 
   FROM pg_stat_activity 
   WHERE state != 'idle' 
   ORDER BY duration DESC;
   ```

### Mitigation
1. Terminate hung backend connections if necessary:
   ```sql
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE now() - query_start > interval '5 minutes' AND state != 'idle';
   ```
2. If primary database failed over on Railway:
   - Verify `DATABASE_URL` in environment configuration.
   - Restart the Goddess AI container to refresh the connection pool:
     ```bash
     railway restart
     ```
3. Verify recovery via:
   ```bash
   curl -H "X-Admin-Secret: $ADMIN_SECRET" https://your-domain/api/v1/health/detailed
   ```

---

## Runbook 2: Redis Disconnection & Fail-Closed Recovery

### Symptoms
- `/health/detailed` reports `subsystems.redis.status = "DEGRADED"` with `fallback_active = True`.
- Logs display `Could not connect to Redis. Falling back to InMemoryRedisFallback`.

### Impact Analysis
- **Non-authoritative degradation**: Goddess AI uses Redis strictly as a cache and pub/sub transport. Primary state remains safely durable in PostgreSQL.
- Distributed locks fail-closed to preserve ledger integrity.
- In-memory fallback handles single-process deduplication automatically.

### Mitigation
1. Verify Redis health in Railway dashboard.
2. If Redis restarted with a new IP/Port, update `REDIS_URL` and restart the API/Worker containers.
3. Test connectivity:
   ```bash
   redis-cli -u $REDIS_URL ping
   ```

---

## Runbook 3: YouTube Quota Budget Depletion & Key Pool Rotation

### Symptoms
- `/api/v1/dashboard/quota` reports `threshold_status = "CRITICAL_95"` or `remaining <= 0`.
- Workers transition to `DEGRADED` polling frequency.
- Key pool enters cooldown.

### Diagnosis
1. Query key pool status:
   ```bash
   curl -H "X-Admin-Secret: $ADMIN_SECRET" https://your-domain/api/v1/dashboard/youtube-keys
   ```
2. Review consumption distribution across registered keys.

### Mitigation
1. **Immediate**: Add a fresh secondary YouTube API key via Railway variables:
   ```bash
   YOUTUBE_API_KEYS="AIzaSyKey1,AIzaSyKey2,AIzaSyFreshKey3"
   ```
2. **If false-positive cooldown**: Reset key cooldown via the Developer Control Center or API:
   ```bash
   curl -X POST -H "X-Admin-Secret: $ADMIN_SECRET" https://your-domain/api/v1/dashboard/youtube-keys/0/reset
   ```
3. If total daily quota is exhausted across all keys:
   - Polling intervals automatically stretch to 15s to conserve units until midnight UTC reset.
   - Live stream co-host replies remain functional; only chat ingestion polling rate is throttled.

---

## Runbook 4: Stream Worker Crash & Stale Stream Reconnection

### Symptoms
- Stream marked `ACTIVE` in dashboard but `is_worker_alive = false`.
- Automated integrity check raises `STALE_STREAM_SESSION` incident.

### Diagnosis
1. Inspect stream session status in Control Center (`/dashboard/streams`).
2. Review stream worker log tail for fatal exceptions.

### Mitigation
1. Trigger idempotent stream reconciliation:
   ```bash
   curl -X POST -H "X-Admin-Secret: $ADMIN_SECRET" \
     -H "Content-Type: application/json" \
     -d '{"action": "reconcile"}' \
     https://your-domain/api/v1/dashboard/streams/{stream_id}/control
   ```
2. If the stream worker terminated due to network cut, trigger restart:
   ```bash
   curl -X POST -H "X-Admin-Secret: $ADMIN_SECRET" \
     -H "Content-Type: application/json" \
     -d '{"action": "restart"}' \
     https://your-domain/api/v1/dashboard/streams/{stream_id}/control
   ```

---

## Runbook 5: Double-Entry Ledger Imbalance Emergency Drill

### Symptoms
- Automatic `CRITICAL` incident raised with service `ECONOMY_LEDGER`.
- Discord ops alert dispatched to Developer Ops channel.

### Immediate Action
1. **Engage Kill Switch**: Disable virtual coin economy transactions immediately via feature flags:
   ```bash
   curl -X POST -H "X-Admin-Secret: $ADMIN_SECRET" \
     -H "Content-Type: application/json" \
     -d '{"key": "ECONOMY", "enabled": false, "reason": "Emergency ledger audit investigation"}' \
     https://your-domain/api/v1/dashboard/feature-flags
   ```
2. Run detailed integrity audit:
   ```sql
   SELECT transaction_id, 
          sum(CASE WHEN direction = 'DEBIT' THEN amount ELSE 0 END) AS total_debits,
          sum(CASE WHEN direction = 'CREDIT' THEN amount ELSE 0 END) AS total_credits
   FROM economy_ledger_entries
   GROUP BY transaction_id
   HAVING sum(CASE WHEN direction = 'DEBIT' THEN amount ELSE 0 END) != sum(CASE WHEN direction = 'CREDIT' THEN amount ELSE 0 END);
   ```
3. Reconcile offending transaction with compensatory administrative adjustment transaction.
4. Verify full ledger balance holds $\sum \text{Debits} == \sum \text{Credits}$.
5. Re-enable `ECONOMY` feature flag.

---

## Runbook 6: OpenRouter AI Gateway Timeout & Circuit Breaker Trip

### Symptoms
- `subsystems.openrouter.status = "DEGRADED"` with `circuit_breaker_open = true`.
- Co-host chat responses fall back to local rule-based replies.

### Diagnosis
1. Check OpenRouter endpoint latency:
   ```bash
   curl -H "Authorization: Bearer $OPENROUTER_API_KEY" https://openrouter.ai/api/v1/models
   ```
2. Check recent AI error messages in `ai_usage_records`.

### Mitigation
1. Verify OpenRouter credit balance and API key status.
2. If primary model (`anthropic/claude-3.5-sonnet`) is degraded at the provider level:
   - Update `OPENROUTER_MODEL_PRIMARY` to `google/gemini-2.0-flash-001` or `meta-llama/llama-3.3-70b-instruct`.
3. If AI service requires maintenance, disable co-host chat interaction cleanly:
   ```bash
   curl -X POST -H "X-Admin-Secret: $ADMIN_SECRET" \
     -H "Content-Type: application/json" \
     -d '{"key": "HONNEY", "enabled": false, "reason": "OpenRouter provider outage"}' \
     https://your-domain/api/v1/dashboard/feature-flags
   ```
