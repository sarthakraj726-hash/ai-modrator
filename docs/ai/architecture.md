# Goddess AI / AI-Modrator — Intelligence & AI Provider Architecture

## Overview

The Goddess AI intelligence subsystem powers **Honney**, the real-time AI co-host and multilingual moderation assistant. It operates under a strict, non-negotiable architectural invariant:

> **Core Invariant**: The LLM is **NEVER** the authority over state mutations or destructive operations. The application remains the authority. The model classifies, reasons, and proposes; the application Policy Engine authorizes; and application-controlled tools execute with cryptographic idempotency.

---

## Model Routing & Tiering

Model calls are decoupled through `ModelRouter` into 5 distinct operational tiers:

| Tier | Default Model | Primary Use Case |
| :--- | :--- | :--- |
| `FAST` | `google/gemini-2.5-flash` | High-frequency message classification, banter detection, fast replies |
| `BALANCED` | `google/gemini-2.5-flash` | Co-host commentary, contextual chat summaries |
| `HIGH_ACCURACY`| `anthropic/claude-3.5-sonnet` | Complex multi-turn context analysis, escalated appeals |
| `REASONING` | `openai/gpt-4o` | Nuanced slang resolution, policy arbitration |
| `FALLBACK` | `meta-llama/llama-3.3-70b-instruct`| Resilient failover on provider degradation or rate exhaustion |

---

## Single-Flight Coalescing & Deduplication

In high-velocity YouTube streams, burst messages and identical troll spam flood the chat simultaneously. `AIRequestCoalescer` guarantees single-flight request deduplication:
- Computes deterministic keys: `hash(creator_id:stream_session_id:message_hash:task_type)`.
- Re-uses in-flight `asyncio.Future` promises for identical pending requests.
- Eliminates duplicate LLM token consumption and API costs.

---

## Budget & Rate-Limit Management

`AIBudgetManager` protects the system from runaway cloud API spend and malicious burst attacks across multiple dimensions:

1. **Daily Creator Limit**: Enforced per-creator daily token and request ceilings (`HONNEY_DAILY_REQUEST_BUDGET=2500`).
2. **Per-Stream Ceiling**: Max AI invocations permitted for a single broadcast.
3. **Per-User Rate Limit**: Caps individual viewer interactions to prevent single users from monopolizing Honney.
4. **Per-Minute Burst Window**: Token bucket algorithm preventing instantaneous traffic spikes from overwhelming OpenRouter quotas.
5. **Graceful Degradation**: When budgets are exhausted, moderation falls back completely to local Layer 0-2 deterministic rules, ensuring stream moderation is never interrupted.

---

## Application Tool Registry

Honney's capabilities are exposed as sandboxed, application-controlled tools (`ApplicationToolRegistry`):
- `get_stream_status`: Query current viewers, uptime, and game/topic metadata.
- `lookup_viewer_trust`: Query viewer interaction history and trust tier.
- `propose_moderation_action`: Non-destructive proposal forwarded to Policy Engine.

The LLM cannot directly call external APIs, delete messages, or execute bans.
