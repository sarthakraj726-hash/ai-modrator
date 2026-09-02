# Phase 2 Test Harness & Simulation Guide

## 1. Overview of Test Suites

Phase 2 includes 92 automated tests across unit, integration, simulation, and chaos fault-injection suites:

```
tests/
├── unit/
│   ├── test_youtube_url_resolver.py       # SSRF protection, URL variants, channel handles
│   ├── test_quota_registry.py             # Cost lookup, environment overrides, usage metrics
│   ├── test_websub_parser.py              # Defused XML parsing, bomb protection, entity expansion
│   ├── test_chat_transports.py            # StreamList and List transports, disconnection
│   ├── test_resolvers_and_coalescer.py    # Request coalescing & checkpoint CRUD
│   └── test_discovery_and_transports_deep.py # Key pool balancing & discovery lifecycle
├── integration/
│   ├── test_api_youtube.py                # Status, keys, quota, and URL connect endpoints
│   ├── test_websub_lifecycle.py           # WebSub GET challenge verification & POST Atom ingestion
│   └── test_worker_manager.py             # WorkerManager async session lifecycle
├── simulation/
│   ├── test_six_stream_isolation.py       # 6 concurrent streams + Stream C crash recovery
│   └── test_seven_stream_capacity.py      # 7 concurrent streams (A-G) with 100% data isolation
└── chaos/
    ├── test_youtube_chaos.py              # Key pool cascading exhaustion & malformed feeds
    ├── test_quota_stress.py               # Concurrent atomic reservation race condition testing
    └── test_fault_injection.py            # Redis disconnect, 5xx storm & graceful shutdown
```

---

## 2. Running Test Suites

### 2.1 Run All Tests with Coverage Report
```bash
.\.venv\Scripts\pytest.exe -v --cov=app --cov-report=term-missing tests/
```

### 2.2 Run Concurrency Simulations
```bash
.\.venv\Scripts\pytest.exe -v tests/simulation/
```

### 2.3 Run Chaos & Fault Injection Tests
```bash
.\.venv\Scripts\pytest.exe -v tests/chaos/
```

---

## 3. Fake YouTube Server Fixture

The test harness uses `tests/fake_youtube_server.py` to simulate YouTube Data API v3 without external network dependencies:
- **`register_video`**: Pre-populates video metadata, live chat IDs, and streaming details.
- **`inject_5xx_rate`**: Injects transient HTTP 500/503 errors at specified failure probabilities.
- **`inject_exhaustion`**: Injects 403 `quotaExceeded` errors to test key pool state transitions.
- **`inject_latency`**: Simulates slow network connections and backpressure.
