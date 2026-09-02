# Goddess AI / AI-Modrator (Phase 1)

[![CI](https://github.com/sarthakraj726-hash/ai-modrator/actions/workflows/ci.yml/badge.svg)](https://github.com/sarthakraj726-hash/ai-modrator/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Production-grade foundation for a multi-channel YouTube Live AI Co-Host + AI Moderator.**

---

## Overview

**GODDESS AI / AI-MODRATOR** is an enterprise-grade, asynchronous, fault-tolerant platform designed to simultaneously manage 6–7 concurrent YouTube live streams.

Phase 1 provides the solid architectural foundation:
- **Strict Stream Isolation**: Per-stream `asyncio` worker tasks with isolated lifecycle, cancellation tokens, state, and error handling.
- **Strict Quota Budgeting**: Hard 4,000 units/day cap on YouTube Data API consumption with two-phase reservation (`reserve()` -> execute -> `consume()`).
- **Multi-Key API Pool**: Resilient round-robin/least-used management across multiple YouTube API keys with health tracking and cooldown periods.
- **Distributed Resilience**: Circuit breakers (Closed/Open/Half-Open) and exponential backoff with full jitter.
- **FastAPI HTTP Service**: Liveness (`/health/live`), readiness (`/health/ready`), and system health (`/health`) endpoints.
- **PostgreSQL & Redis Infrastructure**: SQLAlchemy 2.0 async, Alembic migrations, Redis caching, distributed locks, rate limiting, and typed event bus.
- **Modular Future Interfaces**: OpenRouter AI Gateway, Discord Logger, 5-Layer Progressive Moderation Engine, Persona Strategy Engine, and Command Engine.
- **Railway-Ready**: Production Dockerfile (non-root `appuser`, dynamic `$PORT`), `railway.toml`, and deployment guides.

---

## Quickstart

```bash
# 1. Clone
git clone https://github.com/sarthakraj726-hash/ai-modrator.git
cd ai-modrator

# 2. Virtual environment
python -m venv .venv
.\.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

# 3. Dependencies
pip install -r requirements-dev.txt

# 4. Environment
cp .env.example .env

# 5. Run Migrations
alembic upgrade head

# 6. Start Server
uvicorn app.main:app --reload --port 8000
```

---

## Testing

```bash
# Run all unit, integration, simulation, and chaos tests
pytest --cov=app tests/

# Run the 6-stream isolation concurrency test
pytest tests/simulation/test_six_stream_isolation.py -v -s

# Run the chaos fault-injection test suite
pytest tests/chaos/test_fault_injection.py -v -s
```

---

## Documentation

- [Architecture Overview](docs/architecture/overview.md)
- [Research & Engineering Principles](docs/architecture/research.md)
- [Architecture Decision Records (ADRs)](docs/architecture/decisions.md)
- [Local Setup Guide](docs/development/setup.md)
- [Testing Guide](docs/development/testing.md)
- [Railway Production Deployment](docs/deployment/railway.md)
