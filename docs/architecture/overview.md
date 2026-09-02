# Goddess AI / AI-Modrator — Architecture Overview

## System Architecture Diagram

```
                    ┌─────────────────────────┐
                    │  Developer / Admin UI   │
                    └────────────┬────────────┘
                                 │ HTTP / REST
                                 ▼
                    ┌─────────────────────────┐
                    │       FastAPI API       │
                    │  - /health (live/ready) │
                    │  - /creators            │
                    │  - /streams             │
                    │  - /admin               │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │      Service Layer      │
                    │  - CreatorService       │
                    │  - StreamService        │
                    │  - HealthService        │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
      PostgreSQL (asyncpg)   Redis (Cache/Locks)  Event Bus (PubSub)
              │                  │                  │
              └──────────────────┼──────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │     Worker Manager      │
                    │  - start_session()      │
                    │  - stop_session()       │
                    │  - restart_session()    │
                    └────────────┬────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
   Stream Session A        Stream Session B        Stream Session C
   - Creator A             - Creator B             - Creator C
   - Chat Worker A         - Chat Worker B         - Chat Worker C
   - Isolated Task         - Isolated Task         - Isolated Task
```

## Core Subsystems

1. **API Layer (`app/api/`)**: RESTful FastAPI routes with Pydantic validation, dependency injection, and RBAC security.
2. **Database Layer (`app/db/`)**: Async SQLAlchemy 2.0 models, migrations (Alembic), and repository abstractions.
3. **Cache & Locks (`app/cache/`)**: Redis caching, distributed locks with TTL, and rate limiting.
4. **Event Bus (`app/events/`)**: Typed, asynchronous event distribution across workers and services.
5. **Worker Manager (`app/workers/`)**: Supervision tree for independent stream lifecycles.
6. **YouTube Integration (`app/youtube/`)**: Quota management, multi-key pool, circuit breakers, backoff, and chat polling.
7. **Future Subsystems (`app/ai/`, `app/moderation/`, `app/persona/`, `app/commands/`, `app/discord/`)**: Extensible interface abstractions for future phase capabilities.
