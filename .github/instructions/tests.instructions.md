---
applyTo: "**/tests/**"
---

## Tesing Standards

1. **Framework**: Use `pytest` exclusively. Do not use `unittest`.
2. **Mocking**:
   - Mock all external calls (Alpaca, Firestore, Discord).
   - Use `unittest.mock.MagicMock` or `pytest-mock`.
   - NEVER make real network calls in tests (except integration tests with explicit flags).
3. **Coverage**: New features must include positive AND negative test cases (happy path + error handling).
4. **Async**: Use `@pytest.mark.asyncio` for async functions.
