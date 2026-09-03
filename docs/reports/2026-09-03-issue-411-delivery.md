# Issue #411: local fix and verification

Current handoff: [reconciled branch and fresh research browser evidence](2026-09-03-issue-411-reconciled.md).
It supersedes this document's original local-only status and focused-test summary.

The fix is committed locally for review. Production still runs the existing
code. No merge, deployment, flag change, or GitHub issue closure was performed.

## Production impact, assessed before code

See [the live impact assessment](2026-09-03-issue-411-live-impact.md) for
deployment readback, production message/receipt IDs, and sample limitations.
An explicit META buy-and-hold request incurred an unnecessary **1,250 ms**
classifier call costing **$0.00156590**. Its final builder route was correct.
No explicit buy-and-hold request diverted to research was identified among
the retained linked turns reviewed. This does not establish zero incidents.

The gate runs after the first interpreter, but violates the single intent
owner rule by discarding execution evidence and delegating intent again.
Activation while the issue remained a declared blocker was also a missed
release gate; this patch does not erase that history.

## Implementation

- The primary interpreter produces `research_query`; the runtime projection
  preserves it, and coherent questions bypass intent-repair classifiers.
- Both rail entries consume that payload. The raw-message research classifier
  and the field-name-based default exception are deleted.
- The canonical execution-evidence check discounts a populated field only
  with positive `default` provenance and no contradictory user evidence.
  Missing, unknown, inherited, and explicit provenance protect the builder.
- A shared ownership check protects execution, refusal, pending-answer,
  approval, edit, and result owners at both rail entries.
- `asset_discovery` owns find parameters and currentness. Missing payloads use
  missing-target recovery instead of synthesizing a false currentness value.

No changes were made to `src/argus/domain/research/`, `src/argus/llm/`, or
`src/argus/observability/`.

## Verification

- **315** focused research/routing tests passed.
- **492** interpreter, interpret-stage, and discovery tests passed.
- **100** mocked measurement/session-harness tests passed.
- Ruff, diff whitespace, and the prospective merged-tree modularity check passed.
- Final bounded review returned clean after the readiness/discovery fixes;
  the reviewer completed and has no active follow-up.
- **Six live routing cases passed** on clean commit
  `9fec4bf70c95383f4afa536674ceac4f38104787`: META buy-and-hold in English and
  Spanish stayed in the builder; monthly DCA retained the $100 contribution;
  dated/undated PLTR-LMT and Spanish NVDA-AMD comparisons reached research.
  No case called `knowledge_route`.
- The full live measurement run produced **61 passed / 1 failed**, with no
  skips or expected-failure masks. It took 28m49s. The single failed case
  passed its one documented retry, retaining KO, monthly cadence, and the
  13,000 contribution through confirmation. The original failed scorecard
  remains intact; this is not a claim of a clean 62/62 full run.

The initial failure was
`dca_capital_semantics_prebaked_chip_spanish_pesos_reaches_ready_to_run`.
Its primary `LLMInterpretationResponse` call timed out; the fallback returned
`response_profile_overrides=null`, rejected by the existing object schema.
No interpretation reached the routing guard. The resulting visible recovery
was `interpreter_unavailable`, not a research answer. The retry establishes
that the requested DCA flow works on the unchanged candidate, while the first
run remains evidence of provider/fallback reliability risk.

All 60 cases in the recorded baseline passed on this candidate, including all
49 previously passing cases. Since that baseline, nine discovery fixtures
gained stronger `offered` assertions and two DCA cases were added; existing
prompts and assertions were not weakened. Intervening integration changes
also contributed to these results, so improvements are not all attributed
to #411. The prompt fingerprint records the actual **61/1** full scorecard.

The six-case routing check used real model and asset-provider calls with
downstream research dispatch stubbed. It proves interpretation and handoff,
not research answer quality or production deployment. The separate full
measurement suite exercised its ordinary runtime/provider path.

Evidence:

- [Full live scorecard](evidence/411/live-measurement.json)
- [Single-case retry](evidence/411/live-measurement-retry.json)
- [Six-case live routing acceptance](evidence/411/live-routing.json)
- [Baseline and fixture comparison](evidence/411/baseline-comparison.json)
- [Prospective merged-tree modularity](evidence/411/merged-modularity.txt)

## Integration and handoff

Branch: `codex/issue-411-rail-routing`, local only.

- Original integration base:
  `c7802b37f39772a1216514e37fb6ff2b63142181`.
- Current fetched integration:
  `bf274c28953b8aa0f92da8ee18621e89b38c36ad`.
- Reconciliation merge: none. Prospective merge tree:
  `ca529cd6a7853ee3045ecff53ba19ac937483566`; no textual conflicts.
- Incoming #408/#484 changes touch the OpenRouter receipt logger, research
  settlement analytics, guest funnel dimensions, and documentation. The
  OpenRouter change formats the existing receipt; it does not change model
  selection, schema, or interpretation. Research analytics reads the same
  unchanged sidecar. No overlap changes this patch's question/default
  ownership, feature flags, migrations, or model-facing text. Live behavior
  evidence is retained for the tested candidate; logging/analytics acceptance
  belongs to those incoming lanes.
- All configured watched files from the prospective merge tree passed the
  modularity budget. This does not claim the combined runtime was live-tested.
- Hosted CI and a PR review cycle have not run because this is the requested
  local report. Before landing, reconcile with integration and run normal
  deterministic/CI gates. No terminal READY or deployment claim is made here.

Only evidence, documentation, and the measured-text fingerprint are added
after the tested candidate. Runtime and acceptance-test bytes remain those of
`9fec4bf70c95383f4afa536674ceac4f38104787`; no paid rerun is needed for those
recordkeeping changes.
