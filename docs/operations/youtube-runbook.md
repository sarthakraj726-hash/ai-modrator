# YouTube Engine Operations Runbook

## 1. Environment Configuration & Secrets

Configure the following variables in Railway or local `.env`:

```bash
# YouTube API Keys (3-Key Pool)
YOUTUBE_API_KEY_1=AIzaSy...
YOUTUBE_API_KEY_2=AIzaSy...
YOUTUBE_API_KEY_3=AIzaSy...

# Quota Safety Limits
YOUTUBE_QUOTA_DAILY_LIMIT=40000
YOUTUBE_QUOTA_COST_VIDEOS_LIST=1
YOUTUBE_QUOTA_COST_CHANNELS_LIST=1
YOUTUBE_QUOTA_COST_LIVE_CHAT_STREAM_LIST=1
YOUTUBE_QUOTA_COST_LIVE_CHAT_LIST=1

# WebSub Hub Configuration
WEBSUB_HUB_URL=https://pubsubhubbub.appspot.com/subscribe
WEBSUB_CALLBACK_URL=https://<your-railway-app>.up.railway.app/webhooks/youtube/websub
WEBSUB_LEASE_SECONDS=864000
```

---

## 2. Real-Time Operational Diagnostics

### 2.1 Checking Engine Health
```bash
curl -X GET "https://<app-domain>/youtube/status" \
  -H "X-Admin-Secret: <ADMIN_SECRET>"
```
Sample output:
```json
{
  "status": "operational",
  "daily_budget": 4000,
  "remaining_quota": 3995,
  "percentage_quota_used": 0.125,
  "key_pool_total": 3,
  "key_pool_available": 3,
  "discovery_active": true,
  "active_stream_sessions": 2
}
```

### 2.2 Key Pool Diagnostics
```bash
curl -X GET "https://<app-domain>/youtube/keys" \
  -H "X-Admin-Secret: <ADMIN_SECRET>"
```

### 2.3 Quota Breakdown
```bash
curl -X GET "https://<app-domain>/youtube/quota" \
  -H "X-Admin-Secret: <ADMIN_SECRET>"
```

---

## 3. Standard Operating Procedures (SOP)

### SOP-1: Key Rotation & Zero-Downtime Swap
1. Update `YOUTUBE_API_KEY_1`, `2`, or `3` in the Railway dashboard environment settings.
2. Railway will trigger a rolling restart.
3. The startup reconciler (`reconcile_on_startup`) will automatically resume all active live stream workers and chat ingestion loops with zero missed messages.

### SOP-2: Resubscribing Expired WebSub Feeds
To resubscribe a creator's WebSub feed:
```bash
curl -X POST "https://<app-domain>/creators/<creator_id>/websub/subscribe" \
  -H "X-Admin-Secret: <ADMIN_SECRET>"
```

### SOP-3: Emergency Quota Exhaustion
If the safety budget or Google quota is exhausted:
1. Engine immediately rejects non-essential outgoing requests with `QuotaExceededError`.
2. Existing long-lived streaming connections (`streamList`) remain active and unaffected.
3. Increase `YOUTUBE_QUOTA_DAILY_LIMIT` via environment variable or add a fresh key in `YOUTUBE_API_KEY_3`.
