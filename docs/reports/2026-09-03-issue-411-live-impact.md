# Issue #411: live impact assessment before implementation

Assessed 2026-09-03 00:08 UTC, before runtime or test changes.

## Finding

The defect is live and warrants a fix. A retained explicit buy-and-hold turn
was sent to the secondary research classifier despite carrying an explicit
strategy evidence span. Its final route was correct, but the redundant model
call added 1,250 ms and $0.00156590 in provider-reported cost.

No explicit buy-and-hold request diverted into research was identified in the
retained records reviewed. This is an observation limit, not proof of zero
incidents or an estimate of affected customers.

## Production evidence

Read-only Render API readback using the existing repository credential:

| Service | Live deployment | Commit | Research flag |
| --- | --- | --- | --- |
| argus-api | `dep-dab4or942hec739roddg` | `c7802b37f39772a1216514e37fb6ff2b63142181` | `ARGUS_RESEARCH_RAIL_ENABLED=true` |
| argus-app | `dep-dab4pnn40ujc739qlc8g` | `c7802b37f39772a1216514e37fb6ff2b63142181` | `NEXT_PUBLIC_RESEARCH_RAIL_ENABLED=true` |

API deploy finished 2026-09-01 03:55:48 UTC; app deploy finished 03:57:35 UTC.
The checkout and fetched integration both match that commit. The public API
health endpoint returned healthy. Both flags are also true in the release
profile. The CLI's expired login was resolved for readback by using the
existing API credential, without changing authentication or deployment.

Read-only SQL against production Supabase project `lgdhvepyrzbnscqssgqq`:

- Since 2026-08-09, `route_receipts` contains **72** `knowledge_route` calls,
  all with schema `ResearchQueryExtraction`, source `api_turn`, and outcome
  `succeeded`. First retained call: August 11 18:35:05 UTC; latest:
  September 2 20:11:36 UTC. Mean classifier latency: **1,415 ms**.
- Those receipts reference **53 conversations** and **65 assistant messages**.
  Seven receipts have no message ID. One of the 65 retained messages has no
  preceding user message. All 65 linked turns were reviewed by joining each
  assistant to its preceding user message in the same conversation.
- **Explicit build request, August 24 21:25:49 UTC:** assistant message
  `6f9e7e00-4399-439c-b5af-d5435e3492e2`, request
  `77e8456f-8cf1-4b74-9bd6-696e5def6209`. The request was
  "Buy and hold de meta". Persisted strategy: `strategy_type=buy_and_hold`,
  `asset_universe=[META]`, no other execution fields, and
  `extra_parameters.evidence_spans.strategy_type="Buy and hold"`.
  A successful `ResearchQueryExtraction` receipt still exists. Its latency
  was **1,250 ms**; the linked cost-ledger row records **$0.00156590**,
  `cost_source=provider_reported`. The response asks for the META date window,
  has `await_user_reply`, and has no research sidecar. The final route was
  correct only after the extra classification step.
- **A separate visible routing problem, August 29:** message
  `ec45069e-905e-4946-b730-a04e705a162d` answers a five-year NVDA/AMD earnings
  comparison with unsupported-strategy recovery. Its saved strategy type is
  null. This is not evidence of the strategy-type-default diversion in #411;
  it must not inflate this issue's incident count.
- Two August 16 options-test requests received misleading underlying-stock
  statistics. These predate the currently deployed refusal guards and match
  the previously documented unsupported-recovery mechanism. They are not
  counted as current #411 incidents.
- Recent research-unavailable responses occur for actual research questions;
  their presence does not prove an intent-routing failure.

These are retained production-database records, which can include operator
and acceptance traffic. They are not a count of distinct organic customers.
Deleted guest records, unlinked receipts, and missing intermediate primary
interpretations prevent an exhaustive incident rate or causal census. The
1,415 ms mean covers all classifier calls, not just unnecessary calls.

## Contract assessment

[Issue #411](https://github.com/lagarcess/argus/issues/411) is open, with no
comments. Its opening explicitly says it must close before activation.
The active roadmap records that the flag was enabled with #411 outstanding;
activation did not retire the requirement.

`AGENTS.md` lines 417-422 require LLM-first interpretation, deterministic
post-interpretation guards, and one active intent taxonomy. This gate is
after the primary interpreter, so it is not literally a pre-interpreter
keyword shortcut. It still violates intent ownership: it discards every
`strategy_type` indiscriminately, then asks another model to decide whether
the raw message is research or a build request. The comment claiming it is
"not a second router" does not describe its behavior.

The issue's statement that there is no provenance anywhere is now too broad:
`LLMStrategyDraft` already has `field_provenance` and `evidence_spans`, and
the production META turn demonstrates the latter. What remains absent is a
typed default distinction enforced by this gate, and primary-interpreter
ownership of research question shape.

## Authorized implementation

Make research question shape part of the primary structured interpretation;
the research rail consumes that typed result and stops classifying raw
messages. Replace the field-name exception with explicit default provenance:
missing, unknown, or user-backed provenance must not erase execution intent.
Keep the existing refusal, pending-question, and execution boundaries.

Allowed: agent-runtime contracts, mapping/routing, focused tests/eval cases,
and documentation. Do not modify `src/argus/domain/research/`,
`src/argus/llm/`, or `src/argus/observability/`. Report the patch and evidence;
do not merge or deploy. A mocked-green patch cannot close this
interpreter-facing issue; live acceptance remains a required delivery gate.
