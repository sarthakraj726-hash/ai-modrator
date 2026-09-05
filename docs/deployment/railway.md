# Railway Production Deployment Guide

## Overview

The Goddess AI / AI-Modrator backend is engineered for direct deployment on [Railway](https://railway.app). The production topology consists of:

1. **API Service**: FastAPI HTTP REST server (`uvicorn app.main:app --host 0.0.0.0 --port ${PORT}`)
2. **Worker Service**: Standalone background worker process
3. **Railway PostgreSQL**: Managed relational database
4. **Railway Redis**: Managed cache, event bus, and distributed locks

---

## Step-by-Step Railway Deployment

### 1. Create a New Railway Project
1. Log into your Railway dashboard.
2. Click **New Project** -> **Deploy from GitHub repo**.
3. Select `sarthakraj726-hash/ai-modrator`.

### 2. Provision Managed Infrastructure
1. In the project canvas, click **+ Create** -> **Database** -> **Add PostgreSQL**.
2. Click **+ Create** -> **Database** -> **Add Redis**.

### 3. Configure Environment Variables
In the Railway API Service settings, configure the following variables (Railway automatically provides `DATABASE_URL`, `REDIS_URL`, and dynamic `PORT`):

| Variable | Description | Example / Default |
|---|---|---|
| `APP_ENV` | Environment identifier | `production` |
| `APP_NAME` | Application name | `goddess-ai-modrator` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `ADMIN_SECRET` | Secret token for admin endpoints | `generate-a-strong-random-token` |
| `DATABASE_URL` | PostgreSQL Async URL | `${{Postgres.DATABASE_URL}}` (with `+asyncpg`) |
| `REDIS_URL` | Redis URL | `${{Redis.REDIS_URL}}` |
| `YOUTUBE_API_KEY_1` | Primary YouTube Data API key | `AIzaSy...` |
| `YOUTUBE_API_KEY_2` | Secondary YouTube Data API key | `AIzaSy...` |
| `YOUTUBE_API_KEY_3` | Tertiary YouTube Data API key | `AIzaSy...` |
| `YOUTUBE_QUOTA_DAILY_LIMIT` | Hard daily quota cap | `40000` |
| `OPENROUTER_API_KEY` | OpenRouter API Key (Future AI) | `sk-or-v1-...` |
| `DISCORD_BOT_TOKEN` | Discord Bot Token (Future Logs) | `MTA...` |

### 4. Database Migrations
Database migrations are managed with Alembic. During deployment, run the pre-deploy migration command:
```bash
alembic upgrade head
```

### 5. Health Checks & Monitoring
- **Liveness Probe**: `GET /health/live` (Timeout: 5s, Interval: 30s)
- **Readiness Probe**: `GET /health/ready` (Validates DB and Redis connections)
- **System Overview**: `GET /health` (Reports worker count, active streams, and quota usage)

### 6. Graceful Shutdown & Rollbacks
- The application traps `SIGTERM` and `SIGINT` signals, gracefully terminating active stream workers and closing database/Redis connections without dropping requests.
- Railway's native deployment rollbacks can be triggered instantly from the **Deployments** tab.
