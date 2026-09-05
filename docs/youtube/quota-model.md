# YouTube API Quota Budget & Mathematical Model

## 1. Daily Quota Allocation & Budget Limits

The standard YouTube Data API v3 daily quota is **10,000 units** per Google Cloud project (resetting at 00:00 PST / 08:00 UTC).

In `GODDESS AI / AI-MODRATOR`, we configure a strict safety cap:
- **`YOUTUBE_QUOTA_DAILY_LIMIT`**: **40,000 units** (default, scalable for high-volume live chat co-hosting and moderation).
- **Hard Enforcement**: Once reserved units reach `YOUTUBE_QUOTA_DAILY_LIMIT`, all subsequent outgoing calls throw `QuotaExceededError` before hitting the network.

---

## 2. Per-Method Quota Costs

All costs are registered in `YouTubeQuotaCostRegistry`:

| YouTube v3 Endpoint / Method | Default Cost | Strategy in GODDESS AI |
| :--- | :--- | :--- |
| `videos.list` | 1 unit | Used for broadcast resolution and live status checks |
| `channels.list` | 1 unit | Used for UCID and handle resolution |
| `liveChatMessages.streamList` | 1 unit | Primary streaming connection establishment |
| `liveChatMessages.list` | 1 unit | Fallback polling batch (fetches up to 2,000 messages) |
| `liveChatMessages.insert` | 50 units | Outgoing moderation / persona chat messages |
| `liveChatMessages.delete` | 50 units | Moderation message removals |
| `liveChatBans.insert` | 50 units | Moderation user timeouts and permanent bans |
| `search.list` | **100 units** | **PROHIBITED IN PRODUCTION WORKFLOWS** |

---

## 3. Mathematical Concurrency & Ingestion Model

### 3.1 Streaming Mode (`streamList`)
- Initial connection cost: **1 unit**.
- Ongoing message streaming over long-lived HTTP connection: **0 additional units**.
- Total quota cost for a 4-hour stream in streaming mode: **1 unit**.

### 3.2 Polling Mode (`list` Fallback)
- Adaptive polling interval $T_{poll} \approx 3.0\text{ s}$.
- Polling requests per hour: $\frac{3600}{3.0} = 1200\text{ calls/hr}$.
- Quota cost per stream per hour in polling mode: **1,200 units/hr**.

### 3.3 6-Stream Concurrency under Budget
Across 3 active API keys ($3 \times 10,000 = 30,000\text{ raw units}$):
- With 6 concurrent streams in **Primary Streaming Mode** running for 5 hours:
  $$\text{Total Quota} = 6 \text{ streams} \times 1 \text{ unit} = 6 \text{ units (99.98\% safety margin)}.$$
- If 1 stream falls back to **Adaptive Polling** for 1 hour:
  $$\text{Total Quota} = 1200 + 5 = 1205 \text{ units (within 4,000 budget)}.$$

---

## 4. Key Cooldown & Exponential Backoff Formula

When a key receives a 5xx error or transient rate limit:
$$T_{cooldown} = \min\left(T_{max}, T_{base} \times 2^{\text{failure\_count} - 1}\right)$$
- $T_{base} = 30\text{ seconds}$
- $T_{max} = 900\text{ seconds (15 minutes)}$
- Maximum consecutive failures before permanent mark: 5
