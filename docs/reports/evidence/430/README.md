# Lane B: pending artifacts and edit outcomes

Implementation base: `3738fbec0bd4f96c0248abc52e6b2e2287a8c69c`, which includes
the requested `6fa3f55a`. This evidence uses controlled model output through the
real planner, materialization, interpretation, confirmation and API card builder.
It does not measure model accuracy or run a live evaluation or simulation.

## What changed

`domain.pending_artifacts` owns liveness, state stamping, guarded edits,
consumption and restoration. A metadata layout and callbacks supply content and
storage. Backtest adapters retain launch-hash checks and checkpoint projection.
The new core is exercised with a second artifact layout and a fresh-process import
guard that rejects API, runtime and backtest-catalog imports. Checkpoint classes
and public backtest imports retain their identities.

`domain.edit_contract` owns applied-or-disclosed accounting. Main and recovery
adapters report requested targets, materialized targets, actual change status,
existing refusals and planner notes. No-change results always carry a typed
receipt. Timeframe applicability derives from the existing capability declaration
and normalization helper. There is no second list of supported timeframes.

New cards carry `kind: "backtest"`. One web intake helper normalizes legacy cards
whose kind is absent and rejects explicit unknown kinds. Rendering and copying
dispatch on the normalized kind. The generic no-change receipt has English and
es-419 copy; backtest target labels stay in the backtest presentation adapter.

## Reachability inventory

The audit found seven classes. The original Spanish misread and main typed
absent-asset refusal were already repaired; this change preserves them.

| Reissuing path | Evidence before extraction | Outcome after extraction |
| --- | --- | --- |
| Clarification plan with no operation | A note and non-contract missing field `assumption` are admitted; interpretation removes that missing field and reconfirms the complete draft. Card transport drops assistant prose. | Typed no-change receipt survives interpretation and the resulting card. |
| No operations, copied flat state | Copied capital or timeframe passes planner admission and reissues an unchanged card. | One shared canonical target comparison produces a no-change receipt; reordered equal-weight assets and unchanged RSI parameters cannot count as changes merely because their stored shapes differ. |
| Flat fields rejected or ignored | Invalid costs/cadence, blank benchmark, empty replacement; mixed valid capital and invalid fee proves a wholly-empty-output guard alone is insufficient. | Unmaterialized targets are disclosed; an entirely empty application has the generic receipt. |
| Typed operation falsely considered applied | Empty asset addition and same-value edits produce provenance without a changed artifact. | One shared canonical target comparison produces a no-change receipt; reordered equal-weight assets and unchanged RSI parameters cannot count as changes merely because their stored shapes differ. |
| Recovery adapter loses accounting | Applied capital plus refused asset/unsupported note, ignored flat costs/contributions, copied values, and mixed typed/flat carriers reissue silently. | Recovery derives its disclosure from the same shared owner, preserving refusals and notes and naming ignored fields. |
| Conflicting typed and flat carriers for one target | Typed capital 9000 plus flat capital 8000 chooses opposite winners in main/recovery and neither discloses the lost value. | Both adapters use shared typed-carrier precedence and disclose the conflicting flat value; equal redundant carriers remain silent. Existing refusal aliases are canonicalized once. |
| Downstream normalization discards timeframe | Invalid/blank flat timeframe and invalid typed timeframe look applied until interpretation clears them. Case/whitespace variants can also represent no actual change. | Canonical supported-timeframe normalization decides applicability and equality before accounting. |

Recovery has four entry points: active confirmation, pending chip reply, pending
refinement and latest result. All derive from the same recovery materializer and
now the shared outcome owner. Recovery continues its existing application rules;
an unsupported or omitted application is surfaced instead of silently omitted.

Controls that needed no new fix:

- A truly empty `ready_to_confirm` plan with no flat carrier is rejected before
  the callee. The full interpreter probe returned no response, not a clean card;
  the protected caller bypass was **not reproduced**.
- Main typed removal of an absent asset already carries its refusal.
- Unsupported plans, all-lost indicator edits on a non-RSI card and clear
  benchmark requests remain blocked into clarification.
- Partially materialized typed date/indicator operations are rejected by existing
  planner coverage guards. Negative/zero money fails confirmation validation.
- Direct drawer edits reject empty/unsupported operations and return validation
  errors. Edit chips open clarification without claiming application.

Raw controlled baseline observations: [pre-fix paths](pre-fix-paths.jsonl).
The followup [timeframe probe](timeframe-boundary.jsonl) caught the additional
normalization hole in the initial implementation. These are synthetic fixtures,
not user data. Prior DCA probe card money was not acceptance evidence: the probe
omitted the interpretation stage's optional-parameter state patch. Final tests
and the browser card generator apply that patch, preserving the $10,000 seed and
$500 monthly contribution separately.

## Verification

- Focused backend acceptance: 202 tests passed across shared contracts, real
  planner-to-card paths, recovery, existing compound edits, lifecycle, direct
  edits, run consumption, checkpoint sync and card output.
- Mocked evaluation harness: 237 tests passed across the documented mocked tier.
- Full frontend suite: 1,589 tests passed. Backend Ruff and frontend lint pass
  (frontend has eight existing warnings). Prompt-freeze tests: three passed;
  protected files were also compared byte-for-byte with the integration base.
- Browser: 12 scenarios passed, including EN and es-419 no-change, existing typed
  refusal, successful capital edit, recurring no-change and contribution edit,
  Spanish mobile, and explicit unknown-kind rejection. Every edit scenario
  travels through the composer/SSE intake and repeats assertions after reload.
- Controlled DCA proof preserves starting capital $10,000 while the monthly
  contribution changes from $500 to $650. The fixture cards are generated by the
  production backend path, not manually authored card display values.

The first full local backend run had 6,325 passes, 562 skips and 18 failures.
Fourteen failures required loopback servers or process inspection denied by the
sandbox; all 28 tests in those affected files passed outside it. Three failures
came from local feature flags and passed with default settings. The remaining
unchanged test, `test_openrouter_failure_log_reports_raising_origin`, assumes its
checkout path contains `/argus/`; this worktree is named `private-alpha-next`.
CI's normal checkout supplies that path. These local limitations are not recorded
as a green full backend suite; hosted CI must complete independently. The first hosted run then exposed three new recovery tests relying on local model configuration. The shared recovery test helper now owns its controlled model candidate; the focused suite passes with model environment values explicitly empty.

Reproduce cards from the repository root:

```sh
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture PYTHONPATH=. poetry run python docs/reports/evidence/430/generate_cards.py
```

Run the browser spec against a local shell configured with mock auth, Spanish
enabled and API URL `http://127.0.0.1:4311/api/v1`; the spec intercepts transport:

```sh
cd web
PLAYWRIGHT_BASE_URL=http://127.0.0.1:4310 ./node_modules/.bin/playwright test e2e/lift-edit-contract.spec.ts --workers=1
```

The browser screenshots are committed under [browser](browser/). Exact final
head, revalidation, CI and Codex review are recorded in the PR's terminal audit
after review completes; this document does not assert those gates prematurely.

## Modularity and collision constraints

The current budget config **does watch** `artifact_assumption_edit.py`. At the
integration base its baseline is 1,489 plus 75 growth lines, actual 1,561, leaving
3. The board note was accurate. Extraction reduces it to 1,507, leaving 57.
`llm_interpreter.py` remains 5,335 against limit 5,354, leaving 19. Budgets are not
widened. The final budget must pass on the would-be merged tree, not only this
branch.

The interpreter fingerprint, edit planner (including all model-facing text and
`EditOperation.target`), `llm_interpreter.py`, all four #565 interpreter files,
`state/models.py` and `api/state.py` remain unchanged by this lane. There is no
universal input schema or model-facing text change, so no live eval is owed.

Reconciliation to `7de65e26510e98cd211cab3134a741ce82b31f3d` adds only the board's
overnight-lane status. It changes no runtime owner, API/data contract, UI state,
migration, environment variable or affected test. Existing behavioral evidence
is retained subject to final-head revalidation.


A later final refresh found founder-landed PR #567 at integration
`8f39c5ff99cb48501044bda5172dd772621fca4f`. Its lazy template-contract import
change overlaps the schema dependencies used by both edit adapters and lifecycle
checkpoint projection. The lane inherits that import change through a normal
integration merge; it does not edit the protected model classes. The sole textual
conflict is the board's adjacent Lane B/registry status rows, resolved by preserving
both current statuses. Eight generated JSON schemas, including `EditOperation`,
`ArtifactAssumptionEditPlan`, both LLM draft/response schemas, `StrategySummary`,
`ConfirmationPayload`, `RunState` and `BacktestRunRequest`, are byte-identical
before and after reconciliation. Focused lifecycle/edit/import-boundary tests,
mocked evals, browser replay and the merged-tree budget are rechecked on the new
candidate; there is no model-facing change or paid evaluation to repeat.


## Ready-review carrier-mode follow-up

The ready transition exposed a P1 in the new duplicate-carrier comparison. The
[pre-fix class sweep and red/green proof](carrier-mode-sweep.md) records both missed
conflicts and false conflicts. The shared owner now compares final baskets from
the same starting basket through the existing asset-edit function. The original
7-class inventory includes this carrier-conflict class, but the draft-era proof
had failed to cover operation mode and did not close it.

The PR stays non-draft for final CI, including the full agent-runtime sweep and
local-smoke workflow. A replacement terminal audit is owed after the final-head
Codex response and zero-unresolved-thread check; the earlier draft-era report is
explicitly superseded on the PR. New bilingual fixtures cover both conflicting
replacement/append carriers and equivalent add/append carriers.
