# Incident Runbook: YouTube API Outage or Quota Depletion

## Severity
- **CRITICAL**: Quota > 95% consumed or all API keys in pool enter cooldown.
- **WARNING**: Quota >= 80% consumed or individual API key in cooldown.

## Symptoms
- System alert on Developer Discord: `[CRITICAL] YouTube API quota exhausted` or `All keys in cooldown`.
- HTTP 429 or 403 quotaExceeded errors in `goddess-worker` logs.
- Stream sessions enter `DEGRADED` status with increased polling intervals.

## Immediate Mitigation Steps
1. **Inspect Quota Gauge**:
   - Access Developer Control Center at `/dashboard` -> Quota Governance tab.
   - Verify consumed units against daily budget (4,000 units default).
2. **Review Key Pool Health**:
   - Inspect status of Key 1, Key 2, Key 3 in the Multi-Key Pool.
   - If a key was falsely marked in cooldown due to transient network glitch, click **RESET COOLDOWN** in Developer Control Center or execute:
     ```bash
     curl -X POST https://api.yourdomain.com/api/v1/dashboard/youtube-keys/0/reset \
       -H "X-Admin-Secret: $ADMIN_SECRET"
     ```
3. **Trigger Adaptive Polling Backoff**:
   - The system automatically engages adaptive rate backoff (extending polling interval from 1.5s to 5.0s+).
   - If quota is critically low (<200 units), temporarily disconnect non-priority test streams to protect primary broadcasts.
4. **Provision Additional API Key**:
   - In Google Cloud Console, generate a new YouTube Data API v3 key.
   - Set Railway environment variable `YOUTUBE_API_KEY_4` or update `YOUTUBE_API_KEYS`.
   - Railway will trigger zero-downtime rolling restart.

## Root Cause Analysis & Prevention
- Daily quota resets at midnight Pacific Time (PST/PDT).
- Review historical method usage in `GET /api/v1/dashboard/quota` to detect any rogue loops.
