# Issue #541: retrieval evidence survives a lost invoice

Accepted Codex P2 from PR #540. A market-survey response can carry a valid
`finance_results` item while its `usage` block is missing or malformed. The
#535 nonfatal pricing path then left every invocation count at zero, so
`research_grounded._retrieval_happened()` read "no retrieval". That false zero
bought a second paid request, and when the retry lost its invoice the same
way, a usable answer was replaced with the survey-unavailable note.

Same principle as #535: accounting must not veto the product. Zero and unknown
are different facts, and the code spelled them the same way.

## What changed

- The provider's returned output is the retrieval record. The parser keeps
  every tool result item type in provider order on
  `ResearchPacket.tool_results`, and survey grounding reads it first.
- Invoice tool counts are `int | None`. The parser leaves a count `None` when
  the invoice did not establish it; a zero is reported only when the invoice
  reported zero. Argus-built packets that ran no provider call keep zero.
- `usage.invocations` in the public sidecar and the ledger's `usage_metadata`
  is therefore null when unknown, never zero. Contract and data-model text
  updated in the same change.
- The shared provider fixture now matches recorded zero-tool responses: no
  `finance_results` item and no `usage.tool_calls_details` when the finance
  tool never ran. Passing finance rows with `invocations=0` now raises, so the
  fiction that hid this defect cannot be reintroduced.

## Recorded evidence for the retrieval rule

Every captured Agent API response under `docs/reports/evidence/377/probes/`
and `tests/research/fixtures/` carries exactly one `finance_results` item per
`finance_search` invocation and one `search_results` item per web search. The
five zero-tool recordings carry neither item and omit `tool_calls_details`.

## Reproduction

[repro.py](repro.py) drives the real research answer stage with a recording
transport that can serve the same document twice: a finance-only movers
answer with one `finance_results` item and no `usage` block. Provider HTTP and
the classifier are mocked; no credentials, no live calls.

Untouched base `e3b98690` ([repro-before.txt](repro-before.txt)):

| paid requests | degraded | sidecar `usage.invocations` | answer |
| :--- | :--- | :--- | :--- |
| 2 | `survey_not_grounded` | 0 | "I couldn't retrieve today's market movers." |

After the fix ([repro-after.txt](repro-after.txt)):

| paid requests | degraded | sidecar `usage.invocations` | answer |
| :--- | :--- | :--- | :--- |
| 1 | none | null | "NVDA +2.3%, TSLA -1.1% as of 3:15pm ET." |

`cost_usd` is null in both runs: the invoice is still unpriced and still
records its anomaly row; only the retrieval read changed.

Run it from the repository root with provider credentials disabled:

```sh
PYTHONPATH=. OPENROUTER_API_KEY= PERPLEXITY_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run python docs/reports/evidence/541/repro.py
```

## Tests

New and updated tests were run against the untouched base first
([pytest-before.txt](pytest-before.txt)): **13 failed, 61 passed**. Every
pre-existing test still passed under the realistic fixture; only the new
assertions failed, including
`assert len(transport.requests) == 1` with two recorded provider requests.
After the fix ([pytest-after.txt](pytest-after.txt)): **74 passed**.

Coverage added:

- A grounded finance-only survey with a missing, non-object, or malformed
  invoice is delivered in one request, undegraded, with `invocations` null.
- A survey with no tool output and no invoice still retries once and stays
  honest: unknown counts are not evidence of retrieval either.
- Parser: a lost invoice keeps `tool_results` and leaves all three counts
  `None`; a recorded zero-tool shape reports a confirmed zero and reconciles.
- Tool result items are kept in provider order across finance and web items.

## Verification

- Hermetic research suite on the untouched base: **342 passed**.
- Wider hermetic gate after the fix (research suite, mocked eval harnesses,
  cost ledger, prompt freeze, agent runtime sweep, spine guardrails):
  **2434 passed**.
- Ruff check and format: clean on every changed file and on `repro.py`.
- Mypy: the research domain and API writers are clean; `research_grounded.py`
  reports the same 8 pre-existing errors on the untouched base and on the
  patched file, none in the changed hunk.
- Modularity budget: no violations.
- No interpreter-facing text, research prompt, provider selection, or
  simulation state changed. No paid eval, provider turn, or real backtest ran.

## Lane facts

- Integration base at lane start: `e3b98690b238bb292e161a9a25554cd9cfdbc19d`.
- Branch: `claude/issue-541-retrieval-billing-3b57ee`, opened against
  `codex/private-alpha-next`. A promotion measuring exactly `e3b98690` is in
  flight; this PR queues behind it and is not merged by the lane.
