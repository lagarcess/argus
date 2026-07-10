# Private Alpha Release Manifest — Interpret-surface burn-down candidate

Status: DRAFT (readiness-evidence package). Deploy Proof, Environment Proof, and
Canary sections are the release captain's (Codex) to complete during the Render
promotion — they are the provider-integrated steps and are intentionally left
open here.

## Candidate

- Candidate SHA: `fc7bda6` (code freeze `08d92f9`; `fc7bda6` is a docs-only commit on top — no runtime change)
- Candidate branch: `codex/private-alpha-next`
- Promotion target: `main`
- Release captain: Codex (owns the Render/provider promotion ritual)
- Approver: founder
- Rollback target: current `main` tip prior to this promotion
- Decision record: the interpret-surface burn-down (roadmap "Main-promotion burn-down") — issues #160/#151/#171/#150/#187/#188 all fixed and merged

## What this candidate contains (scope)

The full interpret/edit-surface burn-down, in merge order:
- PR #182 — #171 Sig1/Sig2, #160(B), #150 behavior half
- PR #185 — #160(A) composer-declined edits re-enter the typed edit contract
- PR #186 — #151 post-result/confirmation-edit turns materialize the typed card
- PR #187 — benchmark-keep regression (demo-caught)
- PR #190 — #188 chip asset edits operation-agnostic, two P1 desync corners closed, bare-ticker hardened
- Off-spine: PR #169 (regression-sweep CI), PR #183 (typed degraded-fallback + es-419 parity)

Chips and natural language now converge on one typed edit contract on both the
post-result and confirmation surfaces.

## Gate Evidence (readiness — my part of the handoff)

- Mocked spine sweep at tip: **1035 passed, 0 failed, 0 xfailed** (`tests/agent_runtime` + `tests/test_spine_guardrails.py`, hermetic `synthetic_unit_fixture`). Modularity budgets green.
- #188 live proof (interpreter-facing live gate, real Grok, run independently pre-merge): chip `remove AAPL` → {MSFT,NVDA}; bare `TSLA` → {AAPL,MSFT,NVDA,TSLA} (preserve, code-guaranteed); `add TSLA` → append; `just TSLA` → {TSLA}; compound `drop AAPL and NVDA and add TSLA and AMD` → {MSFT,TSLA,AMD}.
- Full live eval suite on the exact SHA (`fc7bda6`), real Grok / render.yaml tiers, `live_provider`: **17 passed, 4 failed** (scorecard `argus-eval-scorecard-20260710T035708Z.json`). All 4 reds are the known model-tier set, none from the interpret surface:
  - `capability_honesty_options_straddle_tsla`, `graceful_recovery_weekly_options_aapl`, `graceful_recovery_spanish_weekly_options_aapl` — grok options-idea nondeterminism (#159 waiver).
  - `graceful_recovery_spanish_offline_clarifier_missing_period_aapl` — Spanish intent-label flip, A/B-proven pre-existing at base (tier drift, #159 territory), not a lane regression.
  - The #160/#151/#187/#188 cases and the new chip-clarify cases (remove/add/replace/compound) all passed live. Zero interpret-surface regressions.
- Clean-checkout suite gate (#134/#135), fresh detached worktree at `fc7bda6`, no `.env`, full `tests/`, hermetic flags: **1906 passed, 14 failed, 2 skipped**. The 14 are the pre-existing baseline, byte-identical to prior runs — 5 `test_alpha_api_supabase`, 4 `test_chat_runtime_cutover`, 2 `test_render_workflow_execution`, 1 each `test_alpha_orchestration_regression` / `test_canary_capture_replay` / `test_chat_stream_contract`. All outside `agent_runtime`; zero lane regressions from the interpret-surface work. PASS.

## Founder decisions required before promotion

- Options-idea waiver: the grok options-straddle / weekly-options cases (EN + ES) are expected model-tier reds (#159). Confirm they are waived per the issue-tagged expected-fail valve, not spine bugs.

## Deploy Proof / Environment Proof / Canary Evidence

Release captain (Codex) to complete during the Render promotion ritual — see
`TEMPLATE.md` sections. Not filled here by design (provider-integrated steps).
