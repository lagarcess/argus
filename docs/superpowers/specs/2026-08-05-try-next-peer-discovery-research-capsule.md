# Try Next Peer and Discovery Research Capsule

Preserve the useful peer-recommendation decision and evidence without merging
the stale experimental branch into the current Argus product.

Founder-locked 2026-08-05 after the offline recommender investigation on
`codex/offline-direct-competitor-recommender` and the product decision to prefer
a trusted peer fast path with an on-tap discovery fallback.

**Status:** research-only Draft PR. This specification does not restore or
change any production surface.

**Current integration base:** `54a18b733f10fbecbf750bafc7421fa36de90264`.

**Donor evidence head:** `f464c0478e9d4fb5fe387ad3f37cab94d06df0c6`.

## 1. Why

Argus should help a normal person continue exploring after a backtest, but a
bad peer suggestion damages trust. The useful product is therefore not an
always-on recommender. It is a two-level continuation path:

1. offer a known-good, runnable peer immediately when Argus has one;
2. otherwise offer to research similar assets when the user asks for it.

This follows `docs/PRODUCT.md` sections 20-21: complete the Golden Path by
suggesting what to test next, when doing so makes curiosity easier to turn into
a grounded experiment.

## 2. Current product truth

1. `argus_next_experiments/v1` remains the typed result-sidecar contract. Its
   stacked rows are the existing Try next surface.
2. The separate deterministic next-experiment prose block was retired at
   `72d2fe3a`; this lane must not restore it.
3. Grounded asset discovery already supports typed routing, source-backed
   Search, provider-resolved candidates, Guest users, registered users,
   English, and `es-419`.
4. The old research branch is 79 integration commits behind this capsule's
   starting point and adds roughly 17,700 experimental lines. It is evidence,
   not a merge source.

## 3. Locked product decisions

1. **Peer means useful comparable.** A direct operating competitor ranks
   first. A broader company with meaningful product, customer, market, or
   business-model overlap is acceptable. A merely related or weak match is not.
2. **Trusted peer fast path.** When a frozen recommendation exists, the current
   peer row may show `Company Name (TICKER)` and carry the source run's setup
   into the ordinary confirmation flow.
3. **Discovery fallback.** When no trusted peer exists, Argus may offer
   `Explore assets like TICKER` on the same conversational next-move surface.
   Tapping it starts an explicit peer-discovery turn through the existing
   discovery path. It does not run Search while the result paints.
4. **Search is not execution truth.** Every discovered asset must pass the
   existing resolver, same-asset-class, exclusion, data-coverage, and
   confirmation gates before it can become a backtest.
5. **Executable text remains deterministic.** A model or the frontend may not
   invent the ticker or executable `send_text`. The backend owns the typed
   action and canonical source-run context.
6. **Fail closed.** Missing, weak, stale, malformed, or unrunnable frozen peers
   do not render as peers. The ordinary generic behavior remains available.
7. **Parity is required.** Any later runtime slice must work for Guest and
   registered users in English and `es-419`; it cannot quietly become an
   account-only feature.
8. **Runtime remains cheap.** A frozen peer lookup adds no SEC, embedding,
   reranker, LLM, vector-database, or Search call to result rendering.
9. **Catalog storage stays simple first.** A future approved catalog starts as
   a versioned code artifact. Alpaca/provider gates handle tradability drift at
   runtime. Supabase storage, Edge Functions, or scheduled 90-day rebuilds are
   not required until evidence shows the code artifact is insufficient.
10. **A later runtime integration uses an explicit default-off flag.** The flag
    must govern peer enrichment and the discovery fallback together, preserve
    the current behavior byte-for-byte when off, and ship with an owner and
    retirement condition. This research capsule adds no flag.

## 4. Evidence preserved

The frozen development baseline contains 120 operating-equity source cases.
Source evidence was available and the pipeline completed for 110 cases; the
remaining ten are recorded as missing-source-evidence abstentions. Of the 110
completed cases, 16 suggestions displayed and 94 abstained:

- 16 suggestions displayed: **13.3% coverage**;
- 16/16 displayed suggestions graded credible-peer-or-better;
- 14/16 graded direct competitors;
- 2/16 graded broader credible peers;
- zero obvious mismatches.

This proves that the strict pipeline could sometimes recommend well. It does
not prove production coverage or end-to-end product readiness. Its main failure
was abstention: 43 conflicting assessments, 38 ambiguous candidates, seven
shortlist abstentions, five cases with no eligible candidate, one insufficient
evidence case, and ten missing source documents.

The later candidate-isolated contender was implemented and unit-tested on the
donor branch, but its paid 120-case quality benchmark and runtime integration
were not completed. It is therefore not preserved as a proven model adapter.

The compact receipt at
`docs/ops/try-next-peer-research-capsule-v1.json` is the authoritative evidence
summary for this PR. It retains the grade rubric and every source case's
displayed grade or abstention disposition, so future probes can reproduce this
benchmark without depending on the donor branch.

## 5. Reusable code preserved

This PR may preserve one provider-neutral, offline-only selection policy:

- reject malformed or weak assessments;
- exclude corporate-family collisions;
- prefer a direct competitor over a broader credible peer;
- break equal-class ties by the frozen retrieval rank;
- otherwise abstain deterministically.

The policy is not a recommender by itself. It receives already-scored
candidates and makes the final deterministic choice. It deliberately contains
no SEC extraction, retrieval index, model client, prompt, credential, runtime
wiring, persistence, or UI code.

## 6. Reserved and excluded

- Full SEC filing downloads and the discarded multi-gigabyte local corpus.
- Exact-SIC and SHA-256 semantic selection.
- Failed Cohere, pairwise, binary, consensus, and joint-judge variants.
- The unbenchmarked candidate-isolated model adapter.
- Runtime recommender integration, catalog packaging, UI behavior, public API
  changes, database work, migrations, hosted configuration, and deployment.
- ETFs, crypto, and currency-pair semantic matching. Their useful-comparable
  signals differ from operating equities and require separate evidence.
- A new row, card, menu, badge, tooltip, or parallel conversational engine.

## 7. Follow-up workstreams

Each future probe must compare against the frozen 120-company evaluation set in
the capsule receipt and preserve the direct-first, broader-credible-second
product definition.

1. **Retrieval recall:** determine whether a credible peer appears in the top
   20/50 across a broad provider-resolved operating-equity universe.
2. **Second-stage judge:** compare candidate-isolated classification, a
   competitor-specific cross-encoder, calibrated feature models, and a small
   offline LLM judge.
3. **Abstention calibration:** optimize displayed quality first; weak cases use
   discovery instead of forcing a peer.
4. **Frozen catalog:** package only reviewed pairs with source, peer, canonical
   names, class, score, provenance, digest, expiry, and review status.
5. **Runtime slice:** extend the existing next-experiment sidecar and discovery
   action path behind the approved flag. Do not create another engine.
6. **Product proof:** verify Guest/account parity, English/Spanish behavior,
   deterministic replay, zero-question confirmation, provider drift fallback,
   and no added result-paint latency.

Promotion-quality evidence remains:

- at least 95% of displayed suggestions grade credible-peer-or-better;
- at least 80% grade direct competitor;
- zero obvious mismatches on the sealed 120-company set;
- useful coverage, with abstention allowed;
- complete runtime and parity proof for the exact candidate SHA.

## 8. Contract gates for a later implementation

- `docs/API_CONTRACT.md` — update only if the sidecar or typed-action shape
  changes.
- `docs/DATA_MODEL.md` — no change expected; a code-frozen catalog requires no
  table or migration.
- `.agent/designs/argus/DESIGN.md` — preserve existing stacked-row ownership.
- `src/argus/agent_runtime/next_experiments.py` — extend the current owner;
  never create a second recommendation engine.
- Existing discovery contracts and adapters — reuse them for the explicit
  on-tap fallback.

## 9. Execution contract for this capsule

- **PR shape:** one small Draft PR from current integration containing this
  spec, its compact receipt, and the provider-neutral selection policy with
  focused hermetic tests.
- **Proof:** focused tests, Ruff, `git diff --check`, an independent scope
  review, and a clean task-owned process/listener inventory.
- **No live proof:** no browser, provider, model, SEC, Supabase, or Docker run
  is needed because this PR changes no runtime or UI behavior.
- **Endpoint:** Draft PR only. The founder decides whether to retain, close, or
  later use it. This PR is not merge- or production-readiness evidence.

## 10. Stop conditions

- If preserving code requires the old corpus, credentials, model calls, or a
  runtime dependency, omit that code and preserve only the decision/evidence.
- If the current product requires a new visible surface, public API, database
  table, migration, or second conversational engine, stop rather than widen
  this capsule.
- If a future benchmark cannot separate strong suggestions from weak ones,
  keep the trusted catalog small and use the discovery fallback for the rest.

## Sources

### Argus authority

- `docs/PRODUCT.md` sections 1, 11, 20, and 21.
- `docs/ARCHITECTURE.md` sections 11 and 14.
- `docs/API_CONTRACT.md` Structured Action Semantics and Grounded Discovery
  Responses.
- `docs/DATA_MODEL.md` sections 8 and 12.
- `.agent/designs/argus/DESIGN.md` sections 11-12.
- `docs/specs/private-alpha-next-roadmap.md` current product board.

### Donor evidence

- Local donor head `f464c0478e9d4fb5fe387ad3f37cab94d06df0c6`.
- `docs/ops/offline-peer-joint-development-v2.json` on that donor head.

### Inference

- The current grounded discovery path is the lowest-friction long-tail fallback
  because it already owns explicit peer discovery, provider verification,
  Guest parity, localization, and source presentation.

## Addendum: 2026-08-05 founder lock — next pickup point

- **Next step is section 7, item 1 (retrieval recall), not runtime work.** The
  proven selector and the 120-company benchmark only establish that the final
  choice logic is sound; they say nothing about whether a credible peer is
  even retrievable at broader scale. Before any second-stage judge, abstention
  calibration, frozen catalog, or runtime slice work starts, determine whether
  a credible peer appears in the top 20/50 across a broad provider-resolved
  operating-equity universe.
- Items 2-6 in section 7 (second-stage judge, abstention calibration, frozen
  catalog, runtime slice, product proof) remain explicitly sequenced after
  item 1, in the order already written above — this addendum does not
  reorder them, it only confirms item 1 is the pickup point.
- This PR (#384) remains Draft and unmerged. It stays a research-only,
  no-runtime-change evidence record; this addendum records the next pickup
  point, not a scope or merge authorization.
