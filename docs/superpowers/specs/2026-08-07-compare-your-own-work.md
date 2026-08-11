# Compare Your Own Work

Founder-locked 2026-08-07. Spec only.

Replaces the board pillar previously called "product memory". That name was
wrong: none of this is a memory system. The records already exist in the
database and are already written. What is missing is reliable versioning and a
way to read them back.

## 1. What it is

You have run several tests. You want to know which worked, whether a change
helped, or how two ideas stack up.

Argus reads your locked records, asks which ones when it is genuinely unsure,
compares them, and grounds the answer in what actually happened in the market.

Three questions this serves, all of them real:

- **Which of my ideas did best?** Ranking across many.
- **Did my change help?** Consecutive versions of one idea.
- **Should I do A or B?** Two unrelated ideas.

A version-diff view would serve only the middle one. This serves all three
because they are different questions, not different screens.

## 2. Three pieces, three homes

This pillar spans two other lanes deliberately. Ownership is stated here so it
cannot blur.

| Piece | Home | What it does |
| --- | --- | --- |
| Versioning | the editing spec | mints an `IdeaVersion` when a run is confirmed |
| Comparison answers | the research rail | another question shape on the same router |
| The candidate picker | this spec | a confirmation card with multi-select |

**Versioning mints on run, never on edit.** Decision memo section 16.2 states
that material changes create a new version and that multiple edits before one
confirmed run collapse into a single version. Editing freely while a card is
pending produces no versions; confirming the run produces exactly one.
Getting this backwards would fill a user's history with phantom versions from
abandoned edits.

## 3. Relationships, so they cannot drift

The previous pillar produced two parallel Perplexity systems because the spec
never stated how the new work related to the old. These are stated explicitly.

**To the research rail.** Comparison is *in* the rail, not beside it. It adds a
question kind and an operation. It reuses the same classifier, router, provider
layer, cache, and meter. **No second router, no second Perplexity client, no
second cache, no second allowance.**

**To editing.** One edit contract produces one version record; comparison reads
it. No second versioning path, and no separate notion of what counts as a
material change.

**To memory.** Comparison reads your own tables: `ideas`, `idea_versions`,
`evidence_artifacts`, `decision_notes`. **It works with memory off**, because
reading your own runs is the product, not a memory feature, and requiring
consent for it would be absurd.

Memory is an optional sharpener, **pre-wired from the start and inert when
disabled**, for exactly two things: resolving conceptual phrasing like "my tech
bets" that structured filters cannot answer, and knowing what a given user
counts as success. Never the mechanism, never a second data source.

**To mobile.** The picker is a confirmation card, so it inherits the responsive
shell rather than defining its own.

**To the truth boundary.** A comparison answer mixes two sources and they must
never blur:

> **Numbers come from your evidence artifacts and are truth. Market context
> comes from Perplexity and only explains why.**

Perplexity may say Warner Bros had a weak quarter. It may never restate what
your backtest returned. Same standing as the rail's research-informs boundary
and the S10 memory lock.

## 4. Candidate relevance

**Structured filters are the rule.** They are free, exact, cannot drift, and the
candidate set is a bounded personal one, tens of runs rather than tens of
thousands. Semantic search solves a scale problem this does not have.

Signals, in priority order:

1. **Same idea lineage** — `idea_versions.idea_id`. An exact answer to "did my
   change help".
2. **Overlapping symbols.**
3. **Recency.**
4. **Same strategy family** — from `strategy_snapshot`.
5. **Comparable window.** Two runs over wildly different periods are not a fair
   comparison and should not be offered together without saying so.

**Semantic is the optional layer**, used only when phrasing is conceptual rather
than concrete. Pre-wire the seam now so it is not retrofitted later; it stays
inert when memory is off.

**No reranking.** It exists to order large result sets. Three to six cards sort
by lineage then recency.

## 5. The picker

A confirmation card with multi-select, inline in the conversation. Not a
carousel, not a centered modal, not a new surface vocabulary.

- **Appears only when intent is ambiguous.** "Compare my Netflix test to my
  Costco test" goes straight to work. The picker exists because comparison
  costs a provider call, the same reason the confirmation card exists before a
  backtest.
- **Allows N, not just two.** "Which of these did best" is a real question; two
  is merely the common case.
- Candidates render in the existing card pattern. A short row that scans, with
  a peek if it overflows. No horizontal looping.
- If only one artifact qualifies, say so honestly and offer something runnable.
  Never an empty picker.

## 6. The answer

**Lead with the plain conclusion.** "Your second version did better, mostly
because it avoided the March drawdown." A table of jargon is a failure, not a
result.

The table is supporting detail underneath, using the markdown table styling the
rail already needs, scrolling inside its own container on narrow screens.

Where market context genuinely explains a difference, include it with its
source. Where it does not, leave it out rather than padding.

## 7. Metering

Comparison is an ordinary turn, consistent with the rail. Instrument it as its
own capability class so its real cost is visible later.

## 8. Non-goals

No dedicated comparison page, no selection menu outside the conversation, no
second memory system, no diff view, no charts beyond what the result surface
already renders. Comparison does not create ideas, versions, or runs; it reads
what exists.

## 9. Acceptance

- Works with memory off, proven by test.
- Guests compare their own runs.
- The answer leads with a plain conclusion; the table is support.
- No Perplexity value is ever presented as a simulation result.
- A version mints on confirmed run, never on a pending-card edit.
- The picker appears only when intent is genuinely ambiguous.
- Conceptual phrasing degrades honestly when memory is off rather than failing.
- Both languages, no em dashes in user-facing copy.

## 10. Sources

- `docs/specs/private-alpha-next-decision-memo.md` sections 5.6, 16.1, 16.2, 21.
- `docs/superpowers/specs/2026-08-07-research-to-test-rail.md`, especially the
  section 11b amendment on one rail rather than two.
- `docs/superpowers/specs/2026-08-06-confirmation-edit-contract.md` for the edit
  contract that produces versions.
- `docs/superpowers/specs/2026-08-06-mobile-pwa-responsive-shell.md` for the
  shell the picker inherits.
- Existing schema, all present and written today: `ideas`, `idea_versions`
  (carrying `idea_id`, `version_number`, `canonical_spec`, `strategy_snapshot`,
  `lifecycle`, `source_run_id`), `evidence_artifacts`, `decision_notes`.
