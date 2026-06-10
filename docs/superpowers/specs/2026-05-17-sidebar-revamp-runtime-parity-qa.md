# Sidebar Revamp Runtime Parity QA

NOTE: Historical context. This document is retained as implementation evidence and is not the current execution source of truth.

**Date:** 2026-05-17
**Branch:** `web/feat/sidebar-revamp`
**Runtime baseline:** `codex/artifact-runtime-rebuild`
**Checkpoint:** [2026-05-15 Artifact Runtime Milestone Checkpoint](./2026-05-15-artifact-runtime-milestone-checkpoint.md)

## Conclusion

Yes for the checkpoint-covered conversational behavior.

`web/feat/sidebar-revamp` preserves the artifact-runtime behavior marked fully proved in the checkpoint for the tested golden path:

- natural prompt -> validated confirmation card,
- typed approval does not run quota-bearing execution,
- visible card action runs the backtest,
- result card hydrates after reload,
- result follow-ups answer from canonical run facts,
- pending result refinement after reload still keeps the source result reference.

This does not claim broad final production readiness beyond the checkpoint's own scope. The checkpoint still says the full release-grade browser matrix and evaluator harness need continued expansion.

## Runtime Boundary Checks

Preserved:

- `stream_chat_message` consumer path is still in `web/lib/argus-api.ts`.
- `event.event === "final"` handling is still in `web/components/chat/ChatInterface.tsx`.
- `[DONE]` parsing remains in `web/lib/argus-api.ts`.
- `hydrateMessagesFromApi` remains the persistence/reload source in `ChatInterface`.

Safe search constraint:

- `web/components/sidebar/ChatCommandPalette.tsx` does not import or call `ChatMessage`, `hydrateMessagesFromApi`, `getConversationMessages`, `streamChatMessage`, `handleAction`, or `handleStreamEvent`.
- The command palette uses `listHistory` and `searchGlobal` only, then calls the existing conversation loader when a result is selected.

## Live Browser QA

URL: `http://localhost:3000/chat`

Golden prompt:

```text
could you check if holding Tesla for about a year would have beaten SPY?
```

Observed:

- Confirmation card rendered as `TSLA buy and hold`.
- Asset universe was `TSLA` only.
- Benchmark was `SPY`.
- Card state was `Ready to run`.
- Typing `yes run it` did not execute a backtest.
- Assistant replied: use the visible `Run backtest` button.
- Clicking `Run backtest` produced a `Simulation Complete` result card.
- Result facts showed TSLA vs SPY, including total return, max drawdown, benchmark gap, assumptions, and readout.
- Reload preserved the result card.
- Asking `what exactly did you test?` after reload answered from run facts, not from prose reconstruction.
- Clicking `Refine strategy`, reloading, then asking `Before changing anything, what exactly did you test?` still answered from the completed TSLA result instead of creating a new confirmation card or losing context.

Safe search smoke:

- `Ctrl+K` opened the command palette.
- Palette showed grouped chat results with snippets, dates, current badge, and hover actions.
- Selecting the current result closed the palette without disturbing the active chat.
- Static tests verified the palette has no chat-message hydration or stream/action coupling.

## Deterministic Verification

Passed:

```bash
poetry run pytest tests/test_chat_stream_contract.py -q --tb=short
poetry run pytest tests/test_chat_runtime_reload_guardrails.py::test_result_followup_after_reload_carries_latest_run_reference tests/test_chat_runtime_reload_guardrails.py::test_pending_refinement_fallback_carries_source_result_reference -q --tb=short
poetry run pytest tests/agent_runtime/test_llm_interpreter.py::test_llm_interpreter_prompt_separates_benchmarks_from_asset_universe tests/agent_runtime/test_llm_interpreter.py::test_llm_interpreter_preserves_result_followup_during_pending_refinement -q --tb=short
poetry run pytest tests/agent_runtime/test_runtime_semantic_boundaries.py -q --tb=short
cd web && bun test __tests__/alpha-frontend.test.ts __tests__/chat-artifact-history.test.ts
cd web && bunx tsc --noEmit --pretty false
git diff --check
```

## Fixes Added During QA

- `src/argus/agent_runtime/llm_interpreter.py`
  - Preserves a structured `result_followup` interpretation when a pending refinement and a completed result both exist.
  - Adds prompt guidance that benchmark language such as `against SPY` belongs to the benchmark/comparison baseline, not the asset universe.
  - Adds prompt guidance to preserve exact start/end dates instead of replacing them with default relative windows.

- `src/argus/api/chat/recovery.py`
  - Reconstructs the source completed result reference when persisted pending-refinement metadata includes `source_result.run_id`.
  - Carries that reference into fallback `TaskSnapshot` and artifact references after reload.

These changes keep the LLM-first boundary: natural language still reaches the structured interpreter first, and deterministic code only restores validated persisted artifact/run facts.
