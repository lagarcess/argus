# Issue 453 RED baseline

Base SHA: `8025672924d1c74eb80cc926c72b5d8574b613d7`

The following regression tests were added before any runtime change. They are
expected to fail on the untouched base because each asserts the locked recovery
contract rather than the current behavior.

## Backend command

```bash
poetry run pytest --no-cov tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py tests/agent_runtime/test_options_semantic_admission.py tests/agent_runtime/test_validation_failure_copy.py tests/agent_runtime/test_conversation_stages.py -q -k 'issue_453 or unsupported_request_turn_act_contradiction or raw_value'
```

Result: `10 failed, 197 deselected in 1.26s`.

- The Spanish Coca-Cola monthly-purchase turn never invoked
  `FocusedStrategyExtraction`. A bare unsupported verdict therefore cannot be
  repaired into a DCA amount clarification.
- The pending NFLX `$500` answer ran an unrelated capability audit but never
  invoked focused extraction, so it cannot become the typed pending capital
  update.
- Unsupported admission preserved `Options strategies are not executable yet.`
  in `stage_patch.assistant_response` instead of leaving visible recovery to
  the typed clarification stage.
- All English and es-419 generic raw-value variants rendered `User wants to
  invest $500`, `MACD golden cross`, or `BTC_USDT` as the sentence subject.
- Confirming NFLX with `$500` returned
  `unsupported_starting_capital`, but its constraint lacked the canonical
  `minimum` and `maximum` facts. The degraded fallback therefore cannot render
  a typed `$1,000` floor without treating the strategy as unsupported.

Classification: deterministic product regressions. The only irrelevant
external seam, the equity market-clock adjustment, is bypassed in the bounds
test so the assertion exercises the confirm-stage validation envelope directly.

## Web command

```bash
bun test web/__tests__/chat-recovery-display.test.ts
```

Result: `3 tests failed, 28 passed`.

For each generic raw value, the web display selected the raw-value locale
variant. It rendered the model value as the unsupported-recovery subject instead
of the typed, per-asset capability copy. Time-granularity recovery remains
separately covered and unchanged.
