# Issue #333 Retest Current-Data Delivery Plan

> **For Codex:** Execute this plan with the repository TDD and verification rules. The founder-locked design is `docs/superpowers/specs/2026-08-01-retest-current-data-window-semantics.md`; do not reopen its product decisions.

**Goal:** Make “Retest with current data” preserve the original start date, extend only to the latest available data, warn and acknowledgment-gate duplicate-period runs, and make an approved Retest confirmation execute or recover truthfully.

**Architecture:** Keep the client action identity-only and version the durable envelope instead of mutating v1 in place. Reconstruct all owned assumptions from the source run, resolve provider coverage before rendering the confirmation, attach the same validated coverage proof used by ordinary confirmations, and project a typed Retest period sidecar that both the receipt and card render. The normal stale-card guard remains unchanged; a current Retest Run reaches the canonical approval path because its payload is actually executable.

**Tech Stack:** Python 3.10, FastAPI/Pydantic, LangGraph runtime artifacts, React/TypeScript, i18next, pytest, Bun Testing Library, Playwright.

**Global constraints:**

- Start from and target `codex/private-alpha-next`; original integration base is `6533377c1a08539136a622a7d53eee20d0efd845`.
- Preserve v1 durable action admission for existing transcripts, but emit the new v2 extended-window contract.
- Do not change unrelated confirmation fields, add a modal/toast, remove the generic stale guard, add migrations, or touch the locked S-12 evidence report.
- Provider coverage determines the latest available bar; wall-clock dates alone must not declare “new data.”
- Keep EN and es-419 behavior equivalent and run provider-backed checks only at the documented live gate.

---

## Task 1: Lock the versioned action and extended-window domain contract

**Files:**

- Modify: `src/argus/domain/retest_setup.py`
- Modify: `src/argus/api/schemas.py`
- Modify: `src/argus/api/chat/retest.py`
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/api/openapi.yaml`
- Test: `tests/test_retest_setup.py`
- Test: `tests/test_retest_action.py`
- Test: `tests/test_search_api.py`

**Step 1: Write failing tests**

- Assert a reconstructed Retest keeps `original_start` as `start` and requests `today` only as the candidate end.
- Assert emitted actions use `argus_retest_run/v2` plus an extended-window policy.
- Assert exact legacy v1 envelopes remain admissible while unknown versions, policies, and extra authority are rejected.
- Assert the API/OpenAPI projection exposes the v2 literals.

**Step 2: Run the focused tests and confirm RED**

```bash
poetry run pytest tests/test_retest_setup.py tests/test_retest_action.py tests/test_search_api.py -q --no-cov
```

**Step 3: Implement the smallest contract change**

- Add explicit current and legacy contract constants.
- Preserve original start in `RetestSetup`; only the candidate end advances.
- Parse version-policy pairs as a closed set and always sanitize newly persisted actions to v2.
- Update the canonical API documentation and OpenAPI literals.

**Step 4: Re-run focused tests and confirm GREEN**

**Step 5: Commit**

```bash
git add src/argus/domain/retest_setup.py src/argus/api/schemas.py src/argus/api/chat/retest.py docs/API_CONTRACT.md docs/api/openapi.yaml tests/test_retest_setup.py tests/test_retest_action.py tests/test_search_api.py
git commit -m "fix(retest): preserve the original current-data window"
```

## Task 2: Give Retest confirmations canonical coverage truth

**Files:**

- Modify: `src/argus/agent_runtime/stages/confirm.py`
- Modify or add shared helper under: `src/argus/domain/backtesting/`
- Modify: `src/argus/agent_runtime/retest_confirmation.py`
- Modify: `src/argus/api/chat/retest.py`
- Test: `tests/test_retest_action.py`
- Test: `tests/test_chat_runtime_reload_guardrails.py`
- Test: `tests/agent_runtime/test_interpret_stage.py`

**Step 1: Write the failing regression tests**

- Complete a Retest turn, submit the exact current confirmation’s `run_backtest` action, and assert the action reaches approved execution rather than `confirmation_action_stale_card` or reconfirmation.
- Assert the Retest launch payload contains the canonical `coverage_preflight` proof required by `validated_approval_confirmation_payload`.
- Assert coverage/provider failures return their specific existing recovery code and never persist a false runnable confirmation.

**Step 2: Run the focused tests and confirm RED**

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/test_retest_action.py tests/test_chat_runtime_reload_guardrails.py tests/agent_runtime/test_interpret_stage.py -q --no-cov
```

**Step 3: Extract and reuse the canonical coverage boundary**

- Move only the reusable launch validation and coverage preparation needed by both ordinary and Retest confirmations into a shared typed helper.
- Resolve the Retest candidate range through that helper before persisting the card.
- Put requested range, effective range, and `coverage_preflight` into the launch payload; use the effective range for the visible strategy.
- Keep execution on the normal LangGraph approval path. Do not special-case execution in the router.

**Step 4: Re-run focused tests and confirm GREEN**

**Step 5: Commit**

```bash
git add src/argus/agent_runtime/stages/confirm.py src/argus/domain/backtesting src/argus/agent_runtime/retest_confirmation.py src/argus/api/chat/retest.py tests/test_retest_action.py tests/test_chat_runtime_reload_guardrails.py tests/agent_runtime/test_interpret_stage.py
git commit -m "fix(retest): validate current-data confirmation coverage"
```

## Task 3: Project both periods and acknowledgment-gate same-period Run

**Files:**

- Modify: `src/argus/api/chat/confirmation.py`
- Modify: `src/argus/api/chat/retest.py`
- Modify: `web/components/chat/types.ts`
- Modify: `web/lib/chat-retest.ts`
- Modify: `web/components/chat/RetestReceipt.tsx` only if typed projection requires it
- Modify: `web/components/chat/StrategyConfirmationCard.tsx`
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`
- Test: `tests/test_runtime_confirmation_card.py`
- Test: `tests/test_retest_action.py`
- Test: `web/__tests__/chat-retest.test.ts`
- Test: add a focused confirmation Retest test under `web/__tests__/`

**Step 1: Write failing projection and rendering tests**

- Assert receipt metadata carries original and effective periods plus a natural duration descriptor.
- Assert the confirmation carries a typed Retest period sidecar.
- Assert an extended period uses the normal Run label and a same-period confirmation explicitly says no new data and uses an “Run anyway” acknowledgment label.
- Assert EN and es-419 render equivalent disclosures.
- Assert every unrelated row and launch assumption remains unchanged.

**Step 2: Run the focused tests and confirm RED**

```bash
poetry run pytest tests/test_runtime_confirmation_card.py tests/test_retest_action.py -q --no-cov
cd web && bun test __tests__/chat-retest.test.ts __tests__/strategy-confirmation-retest.test.tsx
```

**Step 3: Implement typed disclosure with the existing card action seam**

- Add backend-owned Retest period metadata containing original, requested, effective, duration, and `same_period`.
- Render the transformation in the existing receipt/card surfaces; keep the chip/card structure unchanged.
- Set the existing Run action’s `labelKey` conditionally for the same-period case. The click itself is the explicit acknowledgment; add no modal, toast, or extra state machine.
- Add concise EN/es-419 copy.

**Step 4: Re-run focused tests and confirm GREEN**

**Step 5: Commit**

```bash
git add src/argus/api/chat/confirmation.py src/argus/api/chat/retest.py web/components/chat/types.ts web/lib/chat-retest.ts web/components/chat/RetestReceipt.tsx web/components/chat/StrategyConfirmationCard.tsx web/public/locales/en/common.json web/public/locales/es-419/common.json tests/test_runtime_confirmation_card.py tests/test_retest_action.py web/__tests__/chat-retest.test.ts web/__tests__/strategy-confirmation-retest.test.tsx
git commit -m "feat(retest): disclose duplicate current-data periods"
```

## Task 4: Verify the full turn and capture browser evidence

**Files:**

- Add: `docs/reports/assets/issue-333-retest-current-data/` screenshots
- Modify tests only if verification exposes a confirmed in-scope defect.

**Step 1: Run deterministic backend and frontend gates**

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/agent_runtime tests/test_spine_guardrails.py -q --no-cov
poetry run pytest tests/ -q
cd web && bun test
cd web && bun run lint
cd web && bun run build
```

**Step 2: Run the interpreter-facing live gate if the final diff changes interpretation or approval routing**

- Follow `tests/evals/README.md` exactly.
- Skip the paid gate only if review confirms the change is wholly deterministic and does not alter interpreter behavior; document that disposition.

**Step 3: Run local browser QA**

- Capture normal extended-period and same-period confirmation cards in EN and es-419.
- Click the same-period acknowledgment Run once and verify exactly one simulation request.
- Verify the normal Retest Run reaches a result or a specific truthful recovery.
- Save stable screenshots under `docs/reports/assets/issue-333-retest-current-data/`.

**Step 4: Commit evidence**

```bash
git add docs/reports/assets/issue-333-retest-current-data
git commit -m "test(retest): add current-data browser evidence"
```

## Task 5: Review, reconcile, publish, and hand off

**Files:** No planned product changes; review fixes must be separately justified and focused.

**Step 1: Review the exact diff**

- Run an independent backend/runtime review and an independent UX/i18n review.
- Validate each finding for reachability and issue relevance before changing code.
- Re-run only affected gates after focused review fixes, then run final exact-head verification.

**Step 2: Reconcile current integration**

```bash
git fetch origin codex/private-alpha-next
git rev-parse origin/codex/private-alpha-next
git diff --stat 6533377c1a08539136a622a7d53eee20d0efd845..origin/codex/private-alpha-next
```

- If integration advanced, compare semantic overlap by runtime owner, API/data contract, UI state owner, environment, and tests; merge current integration one-way into the worker branch.
- Preserve accepted evidence unless the overlap invalidates its surface.

**Step 3: Push and open one PR targeting integration**

- Include original integration base, current integration SHA, overlap disposition, exact PR head, all test/browser evidence, risks, rollback, and `Closes #333`.
- Apply existing `bug`, `web`, `api`, and `confirmed` labels.
- Do not merge or deploy. Founder owns terminal merge authority.

**Step 4: Confirm exact-head CI and terminal handoff**

- Wait for required checks to reach terminal state.
- Report any hosted/live evidence separately from deterministic proof.
- Leave the PR ready for the founder only after mandatory review findings are resolved.
