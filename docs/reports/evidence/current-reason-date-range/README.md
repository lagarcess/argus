# Current reply reason and stated date range

Status: **live acceptance blocked; PR #626 remains draft**. The authorized
measurement stopped within its $5 cap. It recorded all 73 case dispositions,
but six cases could not complete within a provable spend bound. The prompt
fingerprint remains unchanged. No merge or deployment.

## Measured result

The [raw scorecard](measurement/live-measurement.json) records **64 passed,
3 failed, 6 unmeasured** (represented as `infrastructure_error`, with component
`measurement_cost_guard`). The [case-by-case comparison](measurement/comparison.md)
and [machine-readable comparison](measurement/comparison.json) use the scorecard
named in `.agent/interpreter_prompt_fingerprint.json`:
`docs/reports/evidence/grounded-math/measurement/live-measurement.json`, measured
at `dc8608c8a09252ff8c51ef077f32d449bb0b6e8b` (69 passed, 2 failed).

All 71 existing fixture definitions are semantically unchanged. Of the
baseline's 69 passing cases, 64 passed again and five are unmeasured. Of its
two failing cases, one failed different checks and one is unmeasured. The two
new date cases failed their full-turn expectations. This historical comparison
cannot establish a complete no-regression result or attribute changes to this
patch alone. The old scorecard has schema-v2 provenance; this one includes
schema-v3 release configuration.

- Both new English and Spanish cases stored August 16–19, 2026, preserving the
  explicit end date. The English case then asked for an asset despite resolved
  `MRNA`. The sole [diagnostic retry](measurement/diagnostic.json) reproduced it.
  Its capture immediately before runtime conversion already has both `MRNA`
  and `missing_required_fields: [asset_universe]`, with
  `provider_context_incomplete_asset_mentions`. This capture is after
  interpreter audits, not a raw provider response. No further fix was applied.
- The Spanish case reached confirmation with the correct requested range and
  an effective trading range of August 17–19. August 16 was Sunday. The new
  fixture incorrectly requires the launch start to remain Sunday and requires
  assistant prose on a confirmation turn. These are fixture defects, not
  evidence that the end-date repair failed. Its raw failures are retained;
  expectations were not rewritten after observing the result.
- Existing `messy_spanish_future_performance_nvda_cruce_dorado` failed intent,
  capability, stage, offered outcome, and research checks. It previously failed
  research publication and scenario-framing checks. The changed failure remains
  visible per check in the comparison.
- Six Agent-dependent cases stopped before Perplexity Agent dispatch. Their
  assertions did not complete. The ledger retains costs of any earlier calls;
  their empty typed outcomes are not fabricated from the baseline.

All 18 DCA cases, all 15 action cases, and all 12 discovery cases passed. These
observations do not replace the missing cases or the targeted reply failures.

## Targeted replies and their limits

[Six live writer-boundary turns](measurement/targeted-replies.json) carried
three messages through English and Spanish histories. English turn 2 was exactly
“That this year check again”. The current date blocker was supplied on turns
1–2 and the capital blocker on turn 3. Both turn-3 replies changed to capital
instead of repeating the earlier date complaint.

The [manual assessment](measurement/targeted-assessment.json) is not a pass:
Spanish turn 1 fell through a contract-invalid primary response and an invalid
fallback-model response to an English degraded fallback describing an
unsupported rule, despite the stored date-window reason. Generated date replies
used MRNA's 2020 history start to wrongly explain an August 2026 limitation.
Both capital replies invented numeric bounds absent from these probe inputs.

These were authored boundary probes, not browser sessions or complete
production replays. Current validation accepts $100. Unlike the deterministic
replay, these thin live constraints omitted canonical min/max fields and
precise date-limit facts. That limits the claim: they expose ungrounded wording
with these inputs, but do not show that production drops bounds it actually
supplies. No additional paid judge or retry was run.

## Cost and method

The [shared budget ledger](measurement/budget.json) covers the initial attempt,
continuation, six targeted replies, and one diagnostic retry. It records 397
HTTP generation/search attempts: 392 OpenRouter and five Perplexity Search.
Reported usage charges total **$1.672551**. Retained reservations for 23 attempts
without reported cost total **$1.066572**, including Search's priced requests.
Reported charges plus a 10% pricing allowance and those reservations give an
accounted upper bound of **$2.906379**, below the approved **$5** cap. This is
conservative accounting, not a reconciled provider invoice.

The initial run stopped before case 33's Agent request. Completed results were
preserved. Continuation skipped that already-stopped case and refused each
subsequent Agent dispatch while allowing independently bounded cases to finish.
The single diagnostic retry was spent on the English date case; its failure
never replaces the original scorecard result.

The earlier $5 proposal used the baseline's OpenRouter headline and did not
include native Perplexity Agent costs. That estimate was incomplete. The active
Agent request has `max_steps=5` and `max_output_tokens=2048`, but those are not a
dollar ceiling: retrieved context and successive model/tool calls add cost.
No safe request-level dollar bound was established for that unchanged payload,
so those requests were not sent. Unmeasured cases are a cost-guard limitation,
not evidence of a provider outage or product failure.

The [run-local method attachments](measurement/method/) preserve the exact
initial/continuation guards and drivers, diagnostic capture, comparison script,
and fetched OpenRouter endpoint pricing. They are audit text, not added runtime
code. The guard reserved before dispatch using maximum published endpoint and
context-tier rates, request UTF-8 bytes plus overhead, output limits, and a 10%
margin. Known usage reduced the reservation; unknown/failed calls retained it.
Tool-using/unpriced writes were refused, and production request payloads were
unchanged. Pricing was checked against
[OpenRouter endpoint metadata](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4-flash/endpoints)
and [Perplexity pricing](https://docs.perplexity.ai/docs/getting-started/pricing).

The canonical `load_eval_cases`, `run_eval_case`, and `write_scorecard` functions
ran directly in an isolated process with live market and asset providers,
release-profile models/flags, and the required real SPY calendar probe. No
production database credentials were present. Paid inputs were public authored
fixtures and the supplied production message text. The private environment file
and runtime logs are not committed. No source, fixture, or commit changed while
calls ran; the local `.env` symlink was restored at completion.

## Exact identity and integration

- Original integration base: `039189128ea6ffcf59be73f3564fd936f191f662`.
- Earlier reconciliation merges: `948a085f0378aadcec064d75fa7bade07f670888` and
  `c91859d5f7a26d99445e2eecb6f55abe58fa994b`.
- Integration fetched before this measurement:
  `0893c27e878f8b55c39afb467cba15ed0ed3cfee`.
- One-way reconciliation and **measured clean head**:
  `c861d95cf0e69003e99d935ffe57c16269e9172b`.
- Fixture SHA-256:
  `84d4db6260e365fd1c1ea9dd3bfb62f06474d9ae5701ad6c34b6ef0065b73963`.
- Incoming PR #627 changed ranked-comparison cards and their shared fact and
  excerpt contracts. It did not touch the date/reply owners, model-facing text,
  lane environment variables, or migrations. Its calculation/eval acceptance
  surface was rechecked: 304 affected and mocked-harness checks passed, plus
  merged-tree modularity. Paid evidence was gathered after reconciliation.
- Evidence publication changes documentation only. Raw scorecard provenance
  remains tied to the measured head above; the artifact manifest records file
  hashes. This report makes no READY claim against a later integration head.

## Implementation and exact instruction strings

The clarification writer no longer receives transcript history. Every reply
kind uses the same current typed input boundary for its primary and fallback
model. The interpreter and durable conversation history retain the transcript.
The natural-time guard declines partial-year normalization when it would
replace the interpreter's fuller date range. The reviewed
`validate_date_range_precision` re-parser and its re-ask path were removed by
founder decision; no replacement re-parser was added.

Clarification writer instruction:

> Use the current response_intent and typed constraints as the authority for this reply's reason and next step.

Shared `LLMDateRangeIntent.kind` description:

> Use explicit_range when the user states both endpoints; a year phrase qualifies their year and must not replace either endpoint with a whole-year window.

## Deterministic checks and review

Before measurement, the full provider-free suite at reconciled runtime commit
`c91859d5` recorded **8636 passed, 604 skipped, one expected prompt-freeze failure**.
Repository lint, merged-tree modularity, and Python package builds passed.
The earlier original-source proof recorded 53 new regression failures against
integration `03918912`; focused lane checks passed after the fixes. The scripted
three-turn replay includes the corrected second message and takes numeric bounds
from canonical configuration. All reply kinds, both languages, and both model
writers have deterministic input-boundary coverage.

The removal-only Codex review at `518818403bcaa199aab263cdd394d09384468fd0`
[returned clean](https://github.com/lagarcess/argus/pull/626#issuecomment-5668534270),
and all P1 threads were replied to and resolved. That review predates the final
integration merge and this evidence publication; it is not presented as a new
review at the measured head. No new review or implementation loop was started.

The prompt-freeze gate requires a case-by-case no-regression finding before
refreezing (`tests/test_interpreter_prompt_freeze.py`), and missing live
measurements block acceptance (`tests/evals/README.md`). These results do not
meet that gate. The fingerprint and fixture assertions remain unchanged;
CI is expected to retain the prompt-freeze failure, and the PR stays draft.
