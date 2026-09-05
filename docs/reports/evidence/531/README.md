# Persisted artifact language: #531, #530, #528

## Scope and identity

- PR: https://github.com/lagarcess/argus/pull/551, targeting `codex/private-alpha-next`.
- Original requested base: `5d408acf`.
- Founder-authorized rebase base: `5761dd417429895a24037df8231528c759af4179`.
- Latest refetched integration: `8315503022972b8d513b75ba126bfd212321eb35`.
- Implementation: `c62cde0b`.
- First one-way integration merge / live measurement candidate:
  `79c8d78eee3af878b9cc52247bb1da28e7dc90a5`.
- Second one-way integration merge / browser revalidation candidate:
  `5b3f020be8b2a42621c1d8bf0d26f5f3306d2d4f`.
- Third one-way integration merge / final deterministic revalidation candidate:
  `d47fe9257161ae8138f2966841a074ca4a79e8fd`.
- Through `77be94d6`, intervening changes were receipt-sharing documentation/evidence only:
  no shared runtime owner, API/data contract, UI state, migration, environment
  variable, or directly affected test changed. Existing baseline evidence retained.
- `77be94d6..dcbc7af5` adds #550's value-free repair annotations and separates
  preflight receipt/accounting labels. Independent overlap review found no
  reader, typed-fact, UI-state, model-input, prompt, schema, migration, or
  environment-variable overlap. Limited operational overlap is in route-receipt
  and cost-ledger evidence taxonomy. Browser and fingerprint evidence remain
  applicable; exact reconciled-tree checks are recorded below. The live scorecard
  stays bound to `79c8d78e` and does not prove the new telemetry taxonomy.
- `dcbc7af5..83155030` lands #549's evaluation-integrity changes, entirely under
  `tests/evals/`. There is no application, reader, UI, or prompt change. The
  harness and fixtures now distinguish unavailable prose judgments and require
  delivered outcomes, so the old live scorecard is historical evidence only,
  not acceptance under the new harness. No paid rerun was authorized or attempted.
- #533 remains excluded. No engine/comparison arithmetic was changed.
- No lane-authored production edits in the prohibited LLM/interpreter directories,
  the three reserved frontend files, or receipt/share surfaces. Incoming #550
  telemetry and receipt-sharing files are integration-owned, not this lane's diff
  against `83155030`.
- No merge of the PR, deploy, hosted migration, or historical rewrite performed.

## Settled persistence contract

Original result-body prose stays private, immutable audit/model context. Typed
facts alone drive affected reader-facing bodies, copy, assumptions, previews,
and dossier outcome readouts. Reading or changing language performs no model
call and creates no per-language prose store.

Existing complete result fact banks remain usable. Incomplete legacy banks are
repaired in one owner/conversation-scoped batch from their canonical completed
run; conflicting or missing identities fail closed to a localized unavailable
result. Empty unavailable results are terminal, never an endless working bubble.

Ordinary user text, unrelated answers, and artifact identity titles retain their
transcript behavior. Old freeform assumptions replies with no typed artifact
marker cannot be classified safely without interpreting old prose; this lane
does not pretend to repair those by phrase matching.

## Reachability and regression guards

Hydration bypasses the five prose-builder modules listed in #531. The fix sits
at the persistence/reader boundary, with the requested ignored-language cleanup
also applied. Reachable private composition remains private; the dead cadence
helper was deleted, and transitive ignored parameters were removed.

The existing AST language tripwire now covers confirm plus all five issue
modules. A separate AST guard prohibits new readers of retained card fields.
The shared root-prose registry (`content`, `assistant_response`,
`assistant_prompt`, `prompt`) also drives the actual scrubber. Exact reviewed
generic transcript owners are pinned by function/expression/count. Negative
mutations in real artifact sources demonstrate that a new template/fallback
read fails. Runtime source aliases must belong to that same scrub registry.

## Fingerprint

**Unchanged.** `surface_drift` returned `([], [], [])`: zero changed, added, or
removed entries, including after the `d47fe925` reconciliation. All three
prompt-freeze tests passed. The explain prompt
builders and model-facing schema descriptions were not edited; no fingerprint
reset was made. The separate sanctioned runtime live gate is recorded below.

## Deterministic verification

Original acceptance candidate `79c8d78e`:

- Full `tests/agent_runtime/` and `tests/research/`: **2,282 passed** using
  `ARGUS_RESEARCH_RAIL_ENABLED=false ARGUS_ENABLE_PERSONALIZATION_MEMORY=false`
  (the default-off deterministic test configuration).
- With local `.env` overrides retained: **2,280 passed, 2 failed**, the same
  discovery/knowledge tests already red at `5761dd41`. Both configurations are
  retained here; no case was removed or weakened to conceal the discrepancy.
- Full backend with default-off flags: **5,878 passed, 537 skipped, 1 failed**.
  The remaining `test_openrouter_failure_log_reports_raising_origin` also fails
  on the immutable baseline: its helper requires an `/argus/` checkout-path
  component, absent from this local `private-alpha-next` worktree. It passes in
  GitHub's Argus checkout. No forbidden LLM code was changed to address it.
- Frontend: **1,543 passed**. Production build passed. ESLint: zero errors,
  eight existing warnings. Ruff and diff whitespace checks passed.
- Required mocked evaluation harness: **100 passed**.
- Standalone TypeScript checking remains red on the inherited `bun:test` shim:
  6,159 diagnostics on baseline, 6,232 on candidate as the tests grow. Neither
  run had production `app/`, `components/`, or `lib/` diagnostics. This is not
  represented as a passing typecheck.
- Modularity passed on the reconciled tree; no budget was increased. The one
  expanded Supabase transport test was extracted while retaining its assertions.
- Real Postgres preview proof: see [preview-sql-proof.md](preview-sql-proof.md).
  The bounded production query uses the existing composite index; fixture rows
  are synthetic and explicitly labeled. The isolated container was cleaned up.

Reconciled candidate `5b3f020b`:

- Full requested `tests/agent_runtime/` and `tests/research/`: **2,286 passed**
  with both default-off flags set as above (31.39 seconds).
- Combined full runtime/research plus fingerprint, artifact-presentation,
  OpenRouter-policy, route-receipt, and cost-ledger tests: **2,409 passed,
  1 failed**. The sole failure is the same baseline checkout-path-sensitive
  logging test documented above; no new failure appeared.
- Mocked evaluation harness: **100 passed**.
- Merged-tree modularity: passed with no budget changes. Prompt surface drift:
  `([], [], [])`. The frontend and affected reader/model-input source files are
  byte-identical to `79c8d78e`; prior frontend build/test evidence is retained.
- Fresh headed-browser revalidation from an immutable `5b3f020b` archive passed:
  the same English-authored META result renders a Spanish Quick Take after the
  Settings switch and reload. No credentials were loaded and no provider or
  hosted database call occurred. Browser and replay services were cleaned up.

Final reconciled candidate `d47fe925`:

- Full runtime/research, all three fingerprint checks, and #549's complete
  canonical mocked harness: **2,526 passed** (37.95 seconds). The runtime/research
  portion is unchanged at 2,286 cases; the expanded mocked command has 237 cases.
- Merged-tree modularity passes and prompt drift remains `([], [], [])`.
- Application source and frontend configuration are byte-identical to the
  browser-tested `5b3f020b` tree. The Spanish reload screenshot and prior frontend
  evidence are explicitly revalidated and retained without another provider turn.
- Current fixture hash is
  `1680a195886c2461e5f8bbbe87f7c3b545a45da189dee8a1f25109409e90ece9`,
  distinct from the historical live scorecard's
  `65a7daab0da92302999bc4a9afa39430f76ba87a0b1d2d0ebecb956ce32b6e8d`.

## Review and CI

Independent scoped Codex review returned clean at `79c8d78e`, with no P1/P2
findings. The reviewer verified the final privacy/AST, unavailable-result,
preview, and live-action classification deltas. Earlier allegations concerning
user-only search fragments, immutable complete fact banks, identity titles,
and excluded arithmetic were investigated and withdrawn with reasons. The final
bounded reconciliation review also returned clean: #550 changes operational
evidence labels, not reader behavior or model inputs. No review remained in flight
when this report was written.

The final #549 overlap review returned clean at `d47fe925`: browser/prompt
evidence is retained, while the old scorecard is historical only. Its three
typed failures remain observed failures with unknown cause, not infrastructure
errors or defects resolved by the harness change. No new production finding was
opened and no review remained in flight after this reconciliation.

[Candidate CI](https://github.com/lagarcess/argus/actions/runs/33938116152)
finished **success**: backend, frontend, ownership, guest-release, and aggregate
CI jobs all green. The backend CI suite reports **5,879 passed, 537 skipped**.
[Reconciled evidence-head CI](https://github.com/lagarcess/argus/actions/runs/33940373943)
also finished **success** at `e5a8c64b`, including the real-Postgres guest gate.
Final evidence-only-head CI and unresolved review-thread
readback are reported in the PR handoff.

## Browser and live gate

The same genuine recorded English-authored META result reproduces the defect
before the fix and renders a Spanish Quick Take after Settings language change
and full reload. See [browser evidence](browser/README.md).

The [historical sanctioned live scorecard](live-measurement.json) is schema v2, with
`worktree_clean=true`, both providers explicitly `live_provider`, Python
3.10.20, all 62 fixture cases exactly once, and a successful January 1 holiday
calendar-alignment probe. It records **59 passed, 3 failed**. No rerun or new
expected-failure masks were used.

The failed cases are:

- `action_chip_change_asset_bare_ticker_append_issue_190`: TSLA was not appended;
  the outcome remained a conversation follow-up.
- `dca_capital_semantics_explicit_cap_refused_by_name_issue_455`: a capped
  contribution request was accepted instead of receiving its named refusal.
- `dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455`: an explicit
  initial seed was treated as a contribution ceiling and refused.

All three passed in the fingerprint's earlier committed scorecard at `9fec4bf7`,
whose fixture hash matches this run. These are unresolved live regressions
relative to that measurement, not proven regressions caused by this lane. They
occur in structured interpretation/capability outcomes before the new reader
boundary. No paired live run on `5761dd41` was performed; the unchanged prompt
fingerprint alone does not establish causation or waive this failed gate.

After this measurement, integration #549 strengthened delivered-outcome
assertions and changed unavailable-measurement handling. The recorded fixture
hash and old harness are retained unchanged with the scorecard. Its 59/3 result
must not be relabeled or treated as a run of the current harness. Current live
acceptance remains unmeasured; a new paid run needs explicit founder direction.

DCA browser diversity acceptance is **blocked**. The first browser driver's
shell quoting damaged the dollar amounts, consuming one provider-backed UI turn;
the product correctly requested clarification, and no Run/backtest occurred.
The corrected prompt was staged and verified byte-for-byte, but auto-review
denied the additional paid submission. It remains unsent pending direct founder
approval. See the sanitized browser blocker provenance. Raw invalid-attempt
receipts stay private in temporary QA storage and are not committed.

**Disposition: draft, not READY.** The same-result English-to-Spanish defect is
visibly repaired, but the failed live gate and incomplete DCA browser gate are
not represented as accepted. Founder direction is required before additional
paid acceptance work or expansion into reserved interpretation/model owners.

## Rollback

Revert the lane implementation to restore the prior readers. There is no
database migration or historical-data rewrite to undo. Source prose remains
available privately throughout. Founder retains merge/deploy authority.
