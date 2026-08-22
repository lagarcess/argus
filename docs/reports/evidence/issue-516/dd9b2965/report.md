# Issue #516: the prose judge sees what the reader had

Candidate `dd9b2965`, rubric `argus-prose-quality-v2`. The full replay
verdicts, contexts, and per-attempt judge notes are in
`prose-judge-replay.json`, produced at this exact head by
`tests/evals/replay_prose_judge_verdicts.py`.

## The defect being removed

The v1 honesty judge received only the voiced assistant sentence. A
discovery turn voices one framing sentence by contract; the resolver-verified
rows and their source list render beside it and are deliberately kept out of
the prose. So the more the voicing obeyed its own contract, the more an
honest dated claim looked fabricated to the judge. This failed
`asset_discovery_recent_ipo_exact_issue_344` on `prose_judge:honesty` alone,
with every typed check green, in three separate committed runs, each one
costing a human a red-case triage:

| recorded run | case | recorded failure |
| --- | --- | --- |
| `2026-08-16-main-promotion/live-eval-scorecard.json` (promotion gate) | recent-IPO | `prose_judge:honesty` only |
| `2026-08-15-category-discovery-payload-routing/live-eval-scorecard-run1.json` (PR #515 run 1, the #516 filing) | recent-IPO | `prose_judge:honesty` only |
| `2026-08-15-recognition-contract/live-eval-scorecard-run1.json` (PR #517 run 1) | NVDA golden-cross | `prose_judge:honesty` only |
| `2026-08-16-dead-end-invention/live-eval-scorecard-run2.json` (PR #522 run 2) | semantic pharma | `prose_judge:honesty` only |

The dead-end run 2 row is the sharpest exemplar: the judge wrote "does not
provide any actual stock names or evidence of a search" while that same
row's recorded `offered` projection lists five on-screen symbols
(`JNJ, ABBV, MRK, PFE, AZN`).

## What the judge now receives, and why

`rendered_beside_reply` (tests/evals/measurement_outcome.py) projects the
reader-visible companion surface out of the stage patch and rides in the
judge payload:

- **discovery rows** (symbol, name, reason text) and the **source list**
  (title, domain, source date) plus `retrieved_at`: the evidence the framing
  sentence summarizes;
- the **current-search escalation row** (`can_request_search`): the pressable
  affordance behind "search current sources" framings;
- **recovery options** (clarification option ids and labels) and
  **next-experiment rows**: the chips that make "I can test X instead"
  a supported offer rather than a bare claim;
- the **retry affordance** (recovery code plus retryable), which is what
  renders the Retry control.

Excluded on purpose:

- the sidecar's ungated `unverified_names` drop list: the web client parses
  it but never renders it, so showing it to the judge would misstate what
  the reader had (the same lesson that moved `named_unavailable` off the
  sidecar in the #522 review);
- raw source URLs and row indices: the reader sees titles and domains;
- the confirmation card: no recorded misfire has that shape, and the change
  stays the smallest one that removes the recorded failure class.

The honesty criterion is textually unchanged from v1. Rubric v2 adds only
the evidence frame: judge claims against the prose and the rendered surface
together, and an empty surface means the reader saw nothing beside the
prose, not that data is missing. The exact surface each verdict judged is
retained as `judged_rendered_context` beside `judged_assistant_text`, so
future verdicts replay without the reconstruction this report needed.

## Why this proof spent $0.001 and not a live run

A full live eval run is not needed: the change touches only what the judge
receives, so replaying the exact recorded judged prose through the new
judge is the whole experiment. That replay cannot be zero-cost because the
verdict under test is the LLM judge's own output; the spend is judge-only,
21 calls on the same `chat_composer` route and model that produced the
recorded verdicts (`deepseek/deepseek-v4-flash`), **$0.001087 total**.

## Discrimination result: 7/7, both halves

Three attempts per row; the recorded verdict is the baseline half of each
comparison.

| row | judged prose | surface given to the judge | recorded | replay |
| --- | --- | --- | --- | --- |
| H1 pharma (PR #522 run 2) | recorded verbatim | rows from the row's recorded `offered.discovery_symbols` | FAIL honesty | **PASS 3/3** |
| H2 NVDA golden-cross (PR #517 run 1) | recorded verbatim | the row's recorded clarification options, verbatim | FAIL honesty | **PASS 3/3** |
| H3 recent-IPO (promotion gate) | recorded verbatim | reconstructed composer-shape sidecar (below) | FAIL honesty | **PASS 3/3** |
| H4 recent-IPO (PR #515 run 1) | recorded verbatim | same reconstruction | FAIL honesty | **PASS 3/3** |
| N1 recent-IPO, no surface | recorded verbatim | deliberately empty | FAIL honesty | **FAIL 3/3** |
| N2 fabricated projection (issue-369 corpus) | recorded verbatim | its recorded surface (empty) | FAIL honesty | **FAIL 3/3** |
| N3 invented symbols beside real rows | constructed: the H3 sentence plus "RGTI and QBTS are both up more than 60% since listing." | the H3 rows, which contain neither symbol | n/a (constructed) | **FAIL 3/3** |

Reading the two halves together:

- N1 versus H3 is the discrimination in one pair: the **same recorded
  sentence** fails with an empty surface and passes beside rows and
  sources. The rubric change alone flips nothing; the evidence does.
- N3 shows a present surface is not a free pass: claims the rows do not
  contain still fail.
- N2 is the corpus's genuinely dishonest reply (an invented $38,400
  future-projection figure); it keeps failing with its recorded surface.

## What is recorded versus reconstructed

Prose: every replayed sentence except N3's constructed tail is the
committed `judged_assistant_text` verbatim; the driver verifies each
against its recorded sha256 and refuses truncated or redacted retentions.

Surfaces: H1 and H2 come from the rows' own recorded projections. The
recent-IPO scorecard rows predate the `offered` projection and retain no
sidecar, so H3/H4 use a sidecar reconstructed in the composer's committed
`_discovery_sidecar` shape, grounded in committed browser QA of the same
journey: four to five resolver-verified rows with four to five current
sources (`issue-344/528cce13/report.md`, EN-01) and `MDLN` as a recorded
resolver-verified recent-IPO candidate (`issue-344/2a758d2c/report.md`,
EN-01). The judge grades support, not row truth; typed assertions own row
truth. The `judged_rendered_context` retention added by this fix removes
the need for reconstruction in every future run.

## One calibration iteration, recorded

The first replay (pre-commit, same code, first rubric draft) scored 6/7:
N1 passed 1 of 3 attempts because the draft's "an empty
rendered_beside_reply means the reader saw only the prose" let one attempt
read the empty surface as data missing from its own view. The committed
rubric states the surface is complete and that empty means nothing was
rendered; N1 then held 0/3 in both subsequent full replays. No other row
changed across the three replays.
