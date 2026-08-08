# Issue #369 judged-prose retention evidence

## Audit identity

- Branch: `claude/prose-text-eval-artifacts-cd7298`
- Original integration base: `37c7eb5213f6c7933a6a56f5e7316eb9943de5fe`
- Current integration SHA at capture: `37c7eb5213f6c7933a6a56f5e7316eb9943de5fe`
- Reconciliation merge: none required, the base is the current integration tip
- Date: 2026-08-08
- Runtime: mocked harness only. No provider call, no paid rerun, no product-runtime mutation.

No provider credential, password, bearer token, cookie, user id, conversation
id, raw transcript export, or database row is preserved here.

## What changed

`run_eval_case` now attaches the exact prose the judge scored to the judge
result, under `prose_judge.judged_assistant_text`, alongside
`prose_judge.requested_criteria`. Both are bound to the same local variable that
is handed to the judge, so a serialized verdict cannot be attributed to prose the
judge never saw.

Retention, redaction, and truncation live in `tests/evals/prose_evidence.py`.
The schema is documented in `tests/evals/README.md` under "Judged Prose
Retention".

## Decisions

**Retain on pass and on fail, not failure-only.** A false pass costs the same
trust as a false failure. Comparing a run's failing prose against its passing
prose in the same artifact is what separates a generator regression from judge
drift, and failure-only retention destroys exactly that comparison. It would also
make what is written depend on the verdict, which is the coupling this change is
meant to avoid.

**Bound at 4,000 characters, head and tail.** Prose over the budget keeps its
first 2,500 and last 1,500 characters around an explicit elision marker that
records how many characters were dropped. Both ends are kept because a judge
reacts to closing capability claims as often as to opening tone; first-N
truncation drops exactly the span an `honesty` failure lives in. The response
style contract asks for one or two short paragraphs, so conforming prose is
retained whole and only degenerate output is clipped. `sha256` and
`character_count` always describe the full judged string, so two runs stay
comparable even when both are excerpts.

**Redact credential-shaped and user-identifying spans.** Applied to the
serialized copy only, never to the string passed to the judge. Covers API keys,
bearer tokens, JWTs, URL userinfo, `key=value` credential assignments, email
addresses, and the verbatim values of secret-named environment variables.
`no_raw_runtime_error` is a graded criterion, so provider error strings do reach
the artifact by design and could otherwise carry a credential with them. Every
strip is counted in `redactions`, so a reader can tell the text is not verbatim.

## Verdicts are unchanged

`verdict-identity-proof.txt` records the run. The base harness at
`37c7eb52` and the candidate harness are loaded side by side and compared:

- 366 real serialized results across 20 committed live-eval scorecards, including
  177 prose-judged results and 3 prose failures, replayed through both versions
  of `scorecard_for_results`, `blocking_eval_results`, and
  `expected_fail_issue_for_result`. Byte-identical.
- 8 mocked `run_eval_case` scenarios covering prose fail, multi-criterion fail,
  prose pass, whitespace-only text, empty text, no prose criteria, credential-
  bearing text, and oversized text. The full result dict is byte-identical once
  the two additive keys are removed, and `status`, `failed_checks`,
  `typed_outcome`, `expected_fail`, and every judge verdict field are identical
  with no stripping at all.

The base harness also reads the new artifacts without drift, so retention is
backward compatible for existing scorecard tooling.

## Review round 1: redaction boundary

Codex comment `3740028402` (P2) reported that a quoted credential value
containing whitespace was cut at the first space, publishing its tail.

The macro pattern behind it: **a secret's end was guessed from a character
class instead of derived from whatever opened it.** It has two failure modes,
and the second is worse than the reported one. Cutting early publishes the
tail; the shortened head can also fall under a rule's minimum-length guard, so
the rule stops firing and publishes the *entire* value. The length guard, which
exists to suppress false positives, becomes a silencer.

Three rules carried it, found by auditing every rule against the invariant
rather than by patching the reported line:

| Instance | Input | Before |
| --- | --- | --- |
| Quoted value, reported | `{"password": "correct horse battery staple"}` | leaked `horse battery staple` |
| Quoted value, total miss | `{'api_key': 'live key with spaces here'}` | nothing redacted at all |
| Auth scheme, total miss | `authorization: Basic dXNlcjpwYXNzd29yZA==` | nothing redacted at all |
| Multi-segment token | 5-part JWE | leaked `.enckey.ciphertext` |

Fixes, all derived from the same invariant:

- A quoted value runs to its closing quote. An unterminated quote, as in a
  clipped log line, has no closing delimiter to trust, so the line end is the
  only safe boundary.
- An auth value is a scheme plus its credentials, so the space after the scheme
  name does not end it.
- A JWT covers every dot-separated segment: three for a JWS, five for a JWE.
- Idempotency is now enforced by a marker guard in `_apply_rule` rather than by
  excluding bracket characters from value classes. The old character exclusion
  was itself a workaround for the same boundary-guessing habit, and it made the
  value classes lie about what a delimiter is.

The rest of the repository was audited for the same pattern and does not have
it. `scripts/ops/canary_capture_sanitizer.py` and
`src/argus/observability/envelope.py` redact by *key name* on structured data
and replace the whole value, so they have no value boundary to guess. The only
other free-text span match is `UUID_PATTERN`, which is fixed-width. This file is
the only place that scans free text for credential values, which is exactly why
it was the only place with the defect. Nothing outside this lane needed changing
and nothing was spun out.

Proofs 4 and 5 in `verdict-identity-proof.txt` cover the result: 94 adversarial
secret shapes across every rule, opener, and awkward delimiter, with zero
surviving fragments; and 8 ordinary prose samples retained verbatim, confirming
the fix did not swing into over-redaction. The new tests assert that no fragment
of the secret survives, rather than that a marker appears, so the next rule with
a guessed boundary fails the suite instead of shipping.

## Inspectable fixture

`judged-prose-retention-fixture.json` is real harness output for the motivating
case shape, `messy_spanish_future_performance_nvda_cruce_dorado`. It pairs the
failing verdict with the Spanish prose that produced it, next to a passing
counterpart from the same case. This is the artifact #369 could not produce: the
failure is attributable to the generator without a rerun.

The prose in the fixture is authored, because the historical live text from
`e6e06917` was discarded by the defect and cannot be recovered. The fixture
proves the schema and the association, not the historical verdict.

## Test results

Baseline captured on a clean checkout of `37c7eb52` before any edit.

| Check | Baseline | Candidate |
| --- | --- | --- |
| Mocked eval suite | 72 passed | 86 passed (72 unchanged, 14 new) |
| Full backend suite | 4182 passed, 3 failed, 430 skipped | 4196 passed, 3 failed, 430 skipped |
| `ruff check src tests workflows scripts` | clean | clean |
| `scripts/check_modularity_budget.py` | no violations | no violations |

The 3 failures are identical in both runs and pre-existing:
`tests/test_frontend_search_casefold.py` requires the pinned Python 3.10
Unicode 13.0.0 contract and this local interpreter is Python 3.14 with Unicode
16.0.0. They are environmental and unrelated to this change.

`tests/evals/measurement_eval_harness.py` grows 1,175 to 1,180 lines against a
1,250 limit.

## Rollback

Independently revertible. Reverting restores the previous artifact schema; no
verdict, threshold, rubric, or scoring path is touched.
