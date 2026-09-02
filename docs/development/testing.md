# Testing Guide

## Running Tests

All automated tests use `pytest` and `pytest-asyncio`.

### Run Entire Test Suite with Coverage
```bash
pytest --cov=app --cov-report=term-missing tests/
```

### Run Specific Test Categories

1. **Unit Tests**:
   ```bash
   pytest tests/unit/
   ```

2. **Integration Tests**:
   ```bash
   pytest tests/integration/
   ```

3. **Mandatory Six-Stream Concurrency Simulation**:
   ```bash
   pytest tests/simulation/test_six_stream_isolation.py -v -s
   ```

4. **Chaos Fault-Injection Tests**:
   ```bash
   pytest tests/chaos/test_fault_injection.py -v -s
   ```

### Code Formatting & Linting
```bash
ruff check app tests
ruff format --check app tests
```
