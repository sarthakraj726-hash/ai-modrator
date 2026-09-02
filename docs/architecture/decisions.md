# Architecture Decision Records (ADRs)

## ADR-001: Separation of API and Background Worker Processes
- **Context**: Long-running YouTube stream workers and chat ingestion loops cannot run inside short-lived HTTP request-response cycles without risking memory leaks, request timeouts, and server instability.
- **Decision**: Architect the system so that FastAPI handles HTTP REST requests, while `WorkerManager` oversees asynchronous workers. The system supports running as a unified monolithic service on small deployments or separate API and Worker services on Railway.
- **Consequences**: Clear boundaries, predictable resource usage, and independent scaling.

## ADR-002: Hard Quota Budget Enforcement (4,000 Units/Day)
- **Context**: YouTube API requests consume varying quota units (e.g., search: 100 units, liveBroadcasts: 1 unit, liveChatMessages.insert: 50 units, liveChatMessages.list: 1 unit).
- **Decision**: Centralize all YouTube API interactions through `QuotaManager`. No service may call YouTube directly without first reserving quota. If quota exceeds 4,000 units/day, requests are cleanly rejected before contacting the network.
- **Consequences**: Zero risk of unexpected quota exhaustion or surprise billing.

## ADR-003: Strict Stream Isolation
- **Context**: Multiple YouTube creators will stream concurrently.
- **Decision**: Stream workers must never share mutable session state or global variables. Each stream has an isolated `StreamSession` instance with its own correlation ID, error boundary, and lifecycle state.
- **Consequences**: Guarantees that Stream A, B, C, D, E, F remain independent; failures are strictly localized.

## ADR-004: Modular Future Interfaces (OpenRouter, Discord, Moderation, Persona, Commands)
- **Context**: Phase 1 establishes the foundation while Phase 2 and beyond will introduce AI Co-Host, progressive moderation, persona engines, and Discord logging.
- **Decision**: Define clean abstract base classes and Pydantic schema contracts in Phase 1 without premature complex business logic.
- **Consequences**: Later phases can plug in implementations without refactoring the foundational architecture.
