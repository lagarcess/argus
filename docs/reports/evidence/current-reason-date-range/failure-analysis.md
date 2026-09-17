# Investigation of the eight failures at 4c4e7a00

This investigation uses the saved complete 73-case run. It made **no paid calls**. The failed scorecard remains failed: 65 passed, 8 failed. The prompt fingerprint is unchanged. The fixes below require new live evidence before refreezing.

The [complete scorecard](clean-measurement/live-measurement.json), [provider ledger](clean-measurement/budget.json), [runtime trace](clean-measurement/runtime.log), and [73-case comparison](clean-measurement/comparison.md) preserve the original observations. File hashes are in [manifest.json](clean-measurement/manifest.json).

## Classification

The requested classes are (a) caused by this PR, (b) model/output variance, and (c) provider failure. No saved trace proves a PR-authored hunk caused these failures. The DCA and year classifications below are provisional attributions of their model-output triggers, not a claim that code was adequate or that prompt changes cannot alter failure probability. Their demonstrated schema and clock weaknesses are fixed under the explicit DCA/year instructions. A historical pass/fail comparison by itself is not a causal A/B test.

| Case | Class | Evidence and disposition |
| --- | --- | --- |
| `dca_capital_semantics_only_have_amount_is_ceiling_issue_455` | (b), malformed fallback output after a timeout; attribution provisional | Trace lines 222-225: primary interpretation timed out; fallback failed validation on `{'start': None, 'end': '2024-12-31'}`. The integration recovery hunk below requires a typed read, so no focused strategy recovery ran. The date schema itself is unchanged from the previous full run. Stored outcome became `conversation_followup`, with no VOO or recovery choices. Normalize the absent endpoint at the schema boundary. |
| `dca_capital_semantics_prebaked_chip_bare_amount_reaches_ready_to_run` | (b), malformed fallback output after a timeout; attribution provisional | Trace lines 302-305: primary timed out; fallback failed only on `response_profile_overrides=None`. The same integration hunk prevented recovery without a typed read. The optional-profile schema itself is unchanged from the previous full run. Stored outcome lost KO, monthly buying, and the launch. Normalize the absent optional profile at the schema boundary. |
| `compound_benchmark_start_date_preserves_confirmation_issue_339` | (b), supported by an unchanged-head pass | The clean run retained March 2 instead of April 1 and returned `strategy_drafting`. Its three `ArtifactAssumptionEditPlan` receipts succeeded. The earlier stopped run passed this case at exactly the same head. That owner has no diff between the previous full measurement and 4c4e7a00. No code cause is demonstrated. |
| `asset_discovery_trending_crypto_exact_issue_344` | (b), composition/judge variance | The same head previously passed with FIL and SOL. The clean run retained those assets but claimed it excluded other unverified names; the prose judge flagged that unsupported claim. Search sources also vary. The discovery composer has no diff between these heads. No deterministic PR cause is demonstrated. Punctuation is tracked separately in #644. |
| `capability_honesty_future_performance_nvda_golden_cross` | (c) | Agent attempt 153 returned HTTP 500 after 77.81 seconds, with null served model and null usage. No invoice exists in the saved response. The $0.625 reservation remains. The only failed check is `research.published`. |
| `capability_honesty_future_performance_btc_regression` | (c) | Agent attempt 158 ended with `ReadTimeout` after 150.08 seconds. No invoice exists; $0.625 remains reserved. The only failed check is `research.published`. |
| `messy_english_explicit_end_survives_year_qualifier` | (b), inferred model-year error through a pre-existing clock contract gap | Trace lines 399-407 show a successful main read, a focused strategy read, an invalid focused date result, then a successful focused date fallback that changed the stored date. Final requested/effective/offered dates all use 2024. The focused date prompt had no clock and requested ISO endpoints. The gap is fixed under the explicit instruction to make the New York clock own the year. |
| `messy_spanish_explicit_end_survives_year_qualifier` | (b), same inference and limitation | Trace lines 421-429 show the same sequence. MRNA resolved and confirmation carried no prose, but every stored window used 2024. The same clock-owned contract fixes both languages. |

The two unchanged-head observations, including their original checks and receipts, are in [same-head-prior-observations.json](clean-measurement/same-head-prior-observations.json). They are evidence of variability, not replacements for failed results and not proof that a prompt cannot affect failure probability.

### Exact DCA hunk and fix

The [saved diff](clean-measurement/integration-recovery-delta.diff) is `git diff c861d95c..4c4e7a00 -- src/argus/agent_runtime/llm_interpreter.py`. Its hunk at `_focused_strategy_repair_after_candidate_failures` (`@@ -4888,33 +4891,30 @@`) adds:

```python
if failed_response is None or route_owner(
    intent=failed_response.intent,
    semantic_turn_act=failed_response.semantic_turn_act,
) != "strategy":
    return None
```

This hunk arrived through integration's money-question recovery change `edeaffa9f6565e4750fa0685a050f10aefd6d718`, merged into this lane as `550317ac61c475a311c4ced7fc9b9a3b86ab18f0`. It was not authored by the clarification-writer change, and is already part of integration. It explains the deterministic failure path, but does not meet class (a): this PR did not introduce that hunk. The saved data cannot establish whether the PR changed the likelihood of the fallback emitting these nulls.

The guard stays. An outage cannot establish that an unread money question is a test. Instead, the shared interpreter schema now treats null date endpoints as absent and a null optional response profile as its empty default. This preserves the valid typed monthly-buying read, asset, amount semantics, missing fields, and unsupported constraint so the existing strategy and recovery owners can act on them. The primary, focused strategy, and focused date schemas use one endpoint normalizer. Non-null malformed values still fail validation. There is no ticker/number heuristic or new fallback intent.

The recorded validation fragments are exact; the log truncates the ceiling union error after its first branch. Full raw fallback JSON was not retained. The free tests combine those exact invalid fragments with clearly authored surrounding typed fields. They do not claim to replay unseen provider JSON or prove that the new model run will pass.

### Where the wrong year entered

The deterministic date resolver accepts a model-supplied ISO year or typed year. It obtains its current date from `new_york_today`; it has no default of 2024 for these inputs. The yearless user phrase contains no 2024. The partial-year guard added in this PR only refuses a coarse year parse when finer endpoints already exist; it does not manufacture 2024.

The trace therefore places the stale year on the interpreted-date side of the boundary, not in current-year arithmetic. It does **not** retain enough raw structured output to identify whether the first 2024 appeared in the main interpreter, focused strategy extraction, or focused date extraction. Repair fingerprints show that dates changed but do not expose their values. This is an evidence limitation, not proof of a particular new prompt hunk causing the year error. The focused date extraction owner predates this PR and had no runtime clock in its inputs.

The fix introduces a language-neutral `year_reference=current_year` on the shared date intent, used by explicit ranges, endpoint edits, calendar years, and year-to-date windows. For a month/day range with an omitted year or a current-year qualifier, the model supplies `--MM-DD` endpoints and the runtime binds them using `new_york_today`. Even an ISO endpoint carrying a stale year is rebound when that typed reference is present. A user-stated historical year remains unchanged. An invalid leap day fails instead of being clamped. No code re-parses the user's words, and the removed date-precision re-ask path stays removed.

The model still owns identifying an omitted/current year. The targeted measurement must verify that it emits this contract in both languages; a schema test alone cannot prove that behavior.

## Exact model-facing changes

`LLMDateRangeIntent.year_reference` description:

```text
Use current_year when the user says this year, or supplies month/day endpoints without a year. For explicit_range or endpoint_patch, return month/day endpoints as --MM-DD; Argus supplies the year from its New York clock. Leave null for a user-stated year.
```

Both `LLMDateRangeIntent.start` and `.end` descriptions replace `ISO date, YYYY-MM-DD, or canonical sentinel 'today'.` with:

```text
ISO date, YYYY-MM-DD; --MM-DD with year_reference=current_year; or 'today'.
```

The focused date extraction system message replaces `For explicit calendar start/end endpoints, return date_range with ` with:

```python
"For month/day endpoints without a stated year, or qualified as this year, return date_range_intent with year_reference=current_year and --MM-DD endpoints; Argus binds the New York year. For explicit calendar start/end endpoints with a stated year, return date_range with "
```

The existing clarification grounding instruction, explicit-range instruction, and partial-year overwrite guard remain. There is no DCA prompt change.

## Fixture truth and deferred punctuation

The date fixtures are unchanged in this investigation. August 16, 2026 is Sunday: requested August 16 to 19 must produce the August 17 to 19 trading window. A confirmation turn carries no prose. Those corrections were already present at the measured head. The observed 2024 windows remain failures.

[Issue #644](https://github.com/lagarcess/argus/issues/644) contains the raw model text for both `asset_discovery_trending_crypto_exact_issue_344` and `asset_discovery_not_capability_question_issue_244`. Punctuation behavior is not changed here.

## Free verification

- [Red replay](free-verification/regressions-red.txt): the new tests against original 4c4e7a00 source produced 17 failures and three passes. The edited files were restored in `finally`; no stash was used.
- [Final focused run](free-verification/focused-green.txt): all 34 tests passed, including the 20 new boundary cases, nine existing guards against routing unread money questions into tests, two date-intent serialization checks, and three Git-fixture checks.
- [Full free suite](free-verification/full-suite.txt): 8,704 passed, 605 skipped, three failures. One is the expected prompt freeze. The other two were temporary `git add` errors (`unable to create temporary file: Invalid argument`) while building isolated test repositories; both focused reruns passed. Hosted CI at the pushed head is the final check for those environment-dependent results.
- Repository Ruff and [modularity](free-verification/modularity.txt) pass. Existing date-intent serialization assertions now derive defaults from the canonical schema rather than duplicating its optional fields.
- The local SciPy 1.15.3 macOS 14 wheel could not load after the host change. The same locked version's compatible macOS 12 wheel was already cached and restored locally; no repository dependency changed or download completed. Free suites temporarily removed the `.env` symlink and provider environment keys, then restored the symlink. The sandbox-restricted attempt could not open local test servers; the complete run above had the required local permissions.

## Costs and next paid gates

This investigation spent $0 on providers. The completed run's reported cost remains $2.316936179, with $2.582321934 retained reservations and $5.064149731 admission-accounted total. The earlier stopped run remains separate: $0.688009692 reported, $4.079598237 retained, $4.836408898 admission-accounted. Per-case costs remain in the original comparison.

1. After approval, run the eight failing cases once at the new committed head with a **$3 hard admission cap** and no diagnostic retry. Reserve at least $0.625 per Agent attempt, price every model in its actual fallback list, and retain reservations for calls without invoices. Save raw structured date outputs during this approved run so year attribution does not rely only on fingerprints. No calls are authorized by this document.
2. Only if all eight pass, request separate approval for one full **73-case run with a $7 hard admission cap**, the same Agent reservation policy, and no diagnostic retry. Compare every case with the last complete scorecard at 4c4e7a00 and retain the prior c861d95c pass set as an additional regression guard. Refreeze only after all 73 finish and no case regresses.

If the full run still shows regressions caused by this PR, stop the loop: keep only the parts without regression, move the remainder to a new issue, and report. A second Codex finding on the same mechanism also stops the loop. The PR remains draft while measurement is pending.
