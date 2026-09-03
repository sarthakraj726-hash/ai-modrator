# Incident Runbook: Discord Outage and Alert Backlog Recovery

## Severity
- **LOW** / **INFORMATIONAL**: Discord is an observability sink and never blocks core stream processing.

## Architectural Guarantees
- A failure in Discord MUST NOT stop the bot or chat ingestion.
- Asynchronous dispatch queues discard or retry non-critical logs, protecting application responsiveness.

## Symptoms
- Discord webhooks return HTTP 429 (rate-limited) or 5xx Cloudflare errors.
- Creator Discord log feeds lag behind real-time stream activity.

## Immediate Mitigation Steps
1. **Verify Discord API Status**:
   - Check status.discord.com for public API disruptions.
2. **Inspect Webhook URL Validity**:
   - Ensure webhook tokens have not been regenerated or deleted in creator Discord channels.
   - Test sending via `POST /api/v1/dashboard/creators` test ping.
3. **Alert Fatigue Suppression**:
   - The built-in `DiscordOperationsService` enforces a 5-minute deduplication window on non-critical warnings.
   - Critical incidents always bypass suppression.

## Post-Recovery Actions
- Once Discord connectivity restores, queued alerts and end-of-stream summaries will dispatch cleanly.
