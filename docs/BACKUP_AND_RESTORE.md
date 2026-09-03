# Goddess AI / AI-Modrator — Backup & Disaster Recovery Guide

This runbook outlines authoritative procedures for cold and warm backups, point-in-time recovery, and data verification drills for Goddess AI.

---

## 1. Storage Architecture Overview
- **Durable Source of Truth**: PostgreSQL database (tables: `creators`, `stream_sessions`, `economy_accounts`, `economy_transactions`, `economy_ledger_entries`, `store_items`, `viewer_inventories`, `moderation_reviews`, `incidents`, `audit_events`, `feature_flags`, `websub_subscriptions`).
- **Non-Authoritative Cache**: Redis (rate limits, locks, cached metrics, pub/sub). Redis data is ephemeral and does not require durable backups.

---

## 2. Automated Daily Snapshot (Railway / Cloud Provider)
When deployed on Railway:
1. Automated daily snapshots are managed by Railway PostgreSQL.
2. Retention policy: 7 days rolling retention.

---

## 3. Manual Cold Backup Procedure

### Exporting Database Schema and Data
To perform a manual logical backup:
```bash
pg_dump -U postgres -d goddess_ai \
  --clean --if-exists --no-owner --no-privileges \
  --format=custom \
  --file=goddess_ai_backup_$(date +%Y%m%d_%H%M%S).dump
```

### Selective Entity Backup (JSON Export)
For emergency JSON state preservation:
```bash
python -c "
import asyncio, json
from sqlalchemy import select
from app.db.session import async_session_maker
from app.db.models.creator import Creator
from app.db.models.economy import EconomyAccount

async def export():
    async with async_session_maker() as session:
        creators = (await session.execute(select(Creator))).scalars().all()
        accounts = (await session.execute(select(EconomyAccount))).scalars().all()
        data = {
            'creators': [{'id': c.id, 'channel_id': c.youtube_channel_id, 'name': c.channel_name} for c in creators],
            'accounts': [{'id': a.id, 'creator_id': a.creator_id, 'viewer': a.viewer_channel_id, 'balance': a.balance} for a in accounts],
        }
        with open('emergency_backup.json', 'w') as f:
            json.dump(data, f, indent=2)
asyncio.run(export())
"
```

---

## 4. Disaster Recovery & Restoration Procedure

### Restoring from Dump File
To restore into a clean PostgreSQL instance:
```bash
# 1. Terminate existing connections
psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'goddess_ai';"

# 2. Restore schema and data
pg_restore -U postgres -d goddess_ai \
  --clean --if-exists --no-owner \
  goddess_ai_backup_YYYYMMDD_HHMMSS.dump
```

### Post-Restore Verification Drill
After any restoration, execute the post-restore integrity drill:
```bash
pytest tests/integration/test_backup_restore.py -v
```
And trigger a full domain integrity audit via the API:
```bash
curl -H "X-Admin-Secret: $ADMIN_SECRET" https://your-domain/api/v1/dashboard/economy
```
Verify that `ledger_balanced` is `true` and `negative_balances_count` is `0`.
