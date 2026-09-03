# Issue #535: deliver research while preserving unpriced-spend evidence

The provider already incurred the cost before Argus checked the invoice.
Discarding a usable answer cannot recover that money. Pricing reconciliation
must therefore control whether Argus can claim a known charge, independently
of whether the answer passes grounding and reaches the user.

This change preserves the original #409/#425 money constraint: disputed spend
has a null charge, an explicit unpriced marker, the reported invoice and failed
comparison, and an ERROR signal. It cannot silently become $0.00 or a reconciled
provider-reported charge. Transport, HTTP, malformed/empty answer, and required
source failures retain their existing availability behavior.

## Independent evidence and reproduction

- Integration base: `c7802b37f39772a1216514e37fb6ff2b63142181`.
- Implementation and recorded replay head:
  `91f23365a95123f404efab002e5ce8c351bb211e`.
- [Real Perplexity response](../../../../tests/research/fixtures/perplexity_netflix_2026-09-03.json):
  one balanced call for a public Netflix earnings question, captured at
  `2026-09-03T00:07:15.383106+00:00`. No customer data or credentials.
- The response reports 708 output tokens, output cost **$0.01416**, and a total
  invoice of **$0.08591**. The existing rate table expects **$0.02124** for that
  output component. Replaying this response unchanged reproduced the production
  `usage.cost.output_cost is outside the served-model rate table` failure.
- [Before-change test output](before-change.txt): three delivery regressions
  failed, including the unchanged fresh response; an independently recorded
  historical invoice passed. The test received the user-facing lookup failure
  instead of the provider answer.
- [After-change replay](recorded-replay.json): the real research answer stage,
  grounding, provider parser, API lifespan writer, and SupabaseGateway normalizer
  produce a Netflix answer with publisher sources, a null public cost, a private
  null-cost ledger insert with both numbers, and `research_cost_unpriced` at ERROR.
  Classification, provider HTTP, and database table transport are mocked.
  This is recorded-response acceptance, not hosted or browser acceptance.

## Pricing and fixture decision

The [published model rates](https://docs.perplexity.ai/docs/agent-api/models)
and [tool prices](https://docs.perplexity.ai/docs/getting-started/pricing) were
rechecked on 2026-09-03. The published values remain unchanged. The fresh bill
disagrees in multiple components; one aggregate bill does not establish a new
rate schedule. Rates and tolerances were therefore not guessed or loosened.
The [fixture provenance](../../../../tests/research/fixtures/README.md) records
the rates checked and the component absent from the current pricing page.

The shared provider fixture now reads a committed real invoice from #377,
instead of computing costs from either production rate table. Two recorded
invoices cover served Sol and Opus models. A dedicated assertion still requires
those recorded invoices to reconcile, so changing the table can fail a test
even though the delivery regression correctly keeps returning the answer.
Synthetic arithmetic edge cases provide explicit bills and are labeled as such.

## Accounting and availability boundary

`ResearchPricingError` is independent of `ResearchUnavailableError`. All billing
metadata is parsed within the reconciliation boundary, so an unknown served
model, invalid invoice, or missing token metadata cannot masquerade as provider
unavailability. Valid parsed retrieval counts are retained for grounding.

Each unpriced provider response emits safe numeric invoice evidence in the ERROR
message itself. This remains visible with the deployed message-only log format.
An API lifespan adapter queues the anomaly for the existing cost ledger:

- `cost_amount = null`, `cost_source = unavailable`;
- `usage_metadata.pricing_status = unpriced`;
- provider response id, served model, usage, reported invoice, failed comparison,
  and expected range are private reconciliation evidence;
- no prompt, answer text, source text, or arbitrary provider metadata is copied;
- existing terminal turn accounting also receives null cost, never zero.

This adds only anomaly rows; existing priced-call and capability-class metering
remain owned by their current writer. Anomaly rows have no billable quantity.
Provider response ids correlate invoices; these rows do not invent a user/turn
join. Repeated completed polls on one client record that response once.

The writer has two dedicated threads and at most 16 pending inserts. A slow
database cannot block the answer. A missing, failed, closed, or full writer emits
`research_cost_unrecorded` with the same safe invoice evidence. Shutdown waits up
to two seconds and reports pending persistence. Database persistence is therefore
best effort under infrastructure failure; the synchronous ERROR evidence is the
recovery record. The tests capture the ERROR signal; external alert delivery is
not claimed by this local run.

## Verification and review

- Untouched-base research baseline: **261 passed**.
- Focused research, mocked session/trajectory harnesses, cost-ledger and prompt
  freeze checks: **393 passed**. [Output](focused-verification.txt).
- Full local gate: **5,706 passed, 532 skipped, 4 failed; 87% coverage**.
  All four failures reproduce on untouched `c7802b37`: default-off saved memory,
  two stream timing/terminal-state tests, and the path-sensitive OpenRouter
  raising-origin assertion. [Gate and baseline evidence](local-full-gate.txt).
- Ruff: passed across `src tests workflows scripts`; changed-file format check
  passed. Mypy passed for all 17 files in the research domain and new API writer.
  The broader `ruff check .` finds three pre-existing import-style errors in
  `docs/reports/evidence/2026-08-24-main-promotion/judge-replay.py`, also reproduced
  on the untouched base.
- Four `app_setup.py` mypy errors reproduce on the untouched integration base
  (checkpointer assignment, validation-error argument, two handler signatures).
- Three mocked trajectory failures with the linked local environment also
  reproduce on the untouched base. That environment enables the research rail;
  this harness does not mock the additional research classifier. Explicitly
  setting `ARGUS_RESEARCH_RAIL_ENABLED=false` restores its intended mocked
  environment. The research suite independently enables its own rail fixture.
- Regression coverage includes valid source delivery, null terminal accounting,
  real gateway insertion and ERROR contents, unknown model, invalid/missing
  billing data, background completion/empty answers, poll deduplication, lifespan
  registration, and deliberately blocked database writes that later succeed or
  fail. The blocked-write test failed before the asynchronous writer change.
- Final bounded code review returned **clean** after the slow-write defect was
  fixed. No further changes were requested. This report was written after that
  review returned.
- Integration advanced to `7e616a40841e018ef560c12f4367ac1808d9b350` while verifying:
  PR #536 changes message formatting for OpenRouter receipts and backtest
  coverage failures, plus logging tests and operational documentation. It changes
  no research runtime owner, API/data contract, UI state owner, migration, or
  environment variable. The receipt schema and recording behavior are unchanged.
  Research invoice evidence and provider recordings remain valid.
- One-way reconciliation merge:
  `181eaf85e35be3097487f55f869ab0ca3575bbba`. The source/test diff against current
  integration still excludes all three sibling-owned paths. The retained
  research checks and newly landed receipt/coverage tests passed after this
  merge: **447 passed**. [Output](reconciled-verification.txt).
  The modularity budget passed on the merged tree. This evidence commit changes
  no runtime or tests.

The untouched ownership boundaries are `src/argus/observability/`,
`src/argus/llm/openrouter.py`, and `src/argus/agent_runtime/knowledge_answer.py`.
No interpreter-facing text, provider selection, research prompt, or simulation
state was changed. No paid eval suite or real backtest was run.

Reproduction command for the focused checks (provider credentials disabled):

```sh
OPENROUTER_API_KEY= PERPLEXITY_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_RESEARCH_RAIL_ENABLED=false ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/research \
  tests/evals/test_measurement_eval_harness.py \
  tests/evals/test_measurement_eval_dca_semantics.py \
  tests/evals/test_measurement_eval_scorecard.py \
  tests/evals/test_measurement_eval_live_environment.py \
  tests/evals/test_chat_runtime_eval_manifest.py \
  tests/evals/test_chat_runtime_trajectory_harness.py \
  tests/test_cost_ledger.py tests/test_interpreter_prompt_freeze.py -q --no-cov
```

Production `grounded_result` success remains a post-deployment acceptance check.
This branch has not been merged or deployed. Rollback is a code revert with no
migration; it would restore the old answer-blocking behavior while the invoice
disagrees, so it is not a production recovery recommendation.
