# Operational Alerting Architecture & Tiered Routing

Goddess AI enforces a multi-tier alert hierarchy designed to prevent alert fatigue while ensuring immediate developer mobilization for critical failures.

---

## 1. Alert Severity Matrix

| Severity | Color | Channel Target | Fatigue Suppression | Trigger Conditions |
| :--- | :--- | :--- | :--- | :--- |
| `CRITICAL` | 🔴 Rose `#f43f5e` | Developer Operations Channel | **NEVER SUPPRESSED** | Quota >95% or all keys exhausted, DB down, Ledger imbalance, Process crash |
| `ERROR` | 🟠 Amber `#f59e0b` | Developer Operations Channel | 5-minute cooldown | Single stream worker crash, Redis down, OpenRouter 5xx spike |
| `WARNING` | 🟡 Yellow `#eab308` | Creator Alert Channel | 5-minute cooldown | Quota >=80%, Key cooldown, High memory usage, Rate limit backoff |
| `INFO` | 🔵 Cyan `#06b6d4` | Creator Log Channel | Real-time | Stream connected/ended, WebSub renewal, Daily digest |

---

## 2. Multi-Tenant Discord Routing

Every creator has dedicated Discord routing configured in `creator_discord_configs`:
- `log_channel_id`: Receives stream started/ended, moderation audit trails, and command usage.
- `alert_channel_id`: Receives creator-specific warnings (e.g. stream disconnected, quota backoff).
- `summary_channel_id`: Receives rich post-stream analytics embed upon stream conclusion.

System-level operational alerts route directly to the centralized developer channel configured via `DISCORD_DEV_ALERT_CHANNEL_ID`.

---

## 3. Alert Fatigue Suppression Algorithm
To prevent alert storms during cascading network failures:
1. Every outgoing alert generates a fingerprint: `{service}:{severity}:{summary_hash}`.
2. For `INFO`, `WARNING`, and `ERROR` alerts, if an identical fingerprint was dispatched in the last 300 seconds (5 minutes), the message is silently suppressed.
3. `CRITICAL` alerts bypass deduplication entirely and are dispatched immediately.
