# Incident Runbook: Redis Outage and Cache Recovery

## Severity
- **HIGH** / **DEGRADED**: Redis is non-authoritative. The system automatically engages safe degradation mode.

## Architectural Guarantees
- Redis is NEVER the sole authority for coins, XP, audit logs, or creator settings.
- PostgreSQL holds durable truth. In memory, Goddess AI automatically engages `InMemoryRedisFallback`.

## Symptoms
- Health endpoint `/health/detailed` reports `redis.status: DEGRADED`.
- Discord alert: `[WARNING] Redis connection failure, switched to in-memory fallback`.
- Rate limiting and deduplication fall back to local in-process memory rings.

## Immediate Mitigation Steps
1. **Verify Redis Container on Railway**:
   - Check Railway Dashboard -> Redis Plugin -> Logs and Metrics.
   - Inspect for Out-of-Memory (OOM) eviction or network partition.
2. **Restart Redis Service on Railway**:
   - If Redis is unresponsive, click **Restart** on the Railway Redis service.
   - Goddess AI automatically reconnects with exponential backoff.
3. **Flush Stale Ephemeral Keys (if corrupted)**:
   - Connect via `railway run redis-cli` and run `PING` followed by inspection of `DBSIZE`.
   - Never worry about data loss: domain data resides in PostgreSQL.

## Post-Recovery Actions
- Verify health returns to `HEALTHY` on `/health/detailed`.
- Check that stream sessions remain connected without chat message loss.
