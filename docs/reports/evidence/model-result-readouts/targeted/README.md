# Completed targeted readout comparison

**Quality failed; stop requested.** All 48 logical tasks were attempted and
reviewed. The candidate passed 1/24 qualitative assessments, with 15 complete
fallbacks and substantive factual errors in the other 8 accepted drafts.
Baseline passed 0/24. No full measurement, fingerprint update or additional
paid run follows automatically.

## Sources and schedule

- Clean baseline: `d0884c3de81f8c53d454ac4f68f461d3b5dd77e3`.
- Clean candidate: `847cdd5e54e9e6256483ee2987a3f59bb79b8ebb`.
- [Three genuine stored runs](../recorded-fixtures.json), SHA-256
  `b255b3b18050a6c7ca7b39fd99645ca3297a4b50a373bf109895ea4fe9793851`.
  DOCN buy-and-hold, DOCN DCA with costs, and SPY RSI preserve the full metrics,
  chart and canonical configuration. DCA came from the direct typed engine
  after chat setup failed, not a successful browser journey.
- Each run in English and Spanish: baseline, candidate, candidate, baseline.
  Each visit composes Quick take then Breakdown, giving 24 visits / 48 tasks.
  Candidate Breakdown receives only its paired accepted Quick take.
- Real production composer entry points and validation, with existing chat and
  context tiers. The comparison uses saved runs; it does not fetch prices,
  simulate, run the interpreter or write product history.

The baseline composer output was private. Comparing its text is a comparison
of generator behavior, not a claim about its browser. Failed candidate draft
text is diagnostic only; the browser renders today's localized template.

## Results

| Variant / surface | Model text accepted | Fallback | Quality pass | Median composer latency |
| --- | ---: | ---: | ---: | ---: |
| Baseline Quick take | 12/12 | 0/12 | 0/12 | 5.25 s |
| Baseline Breakdown | 8/12 | 4/12 | 0/12 | 20.28 s |
| Candidate Quick take | 6/12 | 6/12 | 1/12 | 6.58 s |
| Candidate Breakdown | 3/12 | 9/12 | 0/12 | 15.68 s |

Latency ends when the composer returns accepted text or complete fallback;
subsequent receipt settlement is separate. A faster fallback is not a quality
or performance win. This small comparison does not establish tier necessity.

The [combined review](quality-review.json) contains all 48 unique task keys.
The [English](english-review.json) and [Spanish](spanish-review.json) original
assessments remain intact. Codex reviewed every complete text against its run,
paired Quick take and the founder's writing requirements. These are qualitative
judgments, not founder signoff or a paid judge. No fixed word cap was used;
complete fallback counts as failure of model-writing quality, even when safe.

The single pass was candidate DCA English Quick take, replicate 1. It separates
seed capital from monthly contributions, states actual ending value, adds risk
meaning and labels its capital-scaled drawdown an illustration. Its length and
promotional wording remain noted. Every candidate Breakdown failed.

Observed failures worth carrying forward:

- DOCN English candidate Quick take, replicate 2, attaches the real 45% worst
  drawdown to the real $6,784 global peak. The worst drawdown occurred earlier,
  from $1,747.10 on February 18, 2025 to $963.34 on August 1, 2025. Numeric
  membership permits a false relationship between individually valid facts.
- Candidate RSI accepted drafts in both languages confuse four executed fills
  with four winning completed trades. The saved four fills form two round trips.
- Candidate Spanish DCA Breakdown, replicate 1, calls the $8,648.60 peak the
  ending value instead of $6,644.07, and calls annualized volatility daily.
- DOCN English candidate Quick take, replicate 1, is rejected solely because
  “500” in “S&P 500” is classified as an unsupported scalar. The independent
  [diagnosis](guard-diagnosis.json) reconstructs the exact 49,826-byte measured
  request and records every numeric rejection. Other rejected drafts include
  real rounding errors and false relationships; not every fallback is spurious.
- Baseline texts mainly repeat the card or paired Quick take. Other baseline
  failures include em dashes and treating DCA return as a return on seed capital.

## Bounded execution and cost

The [original stopped report](stopped-original.json) preserves the first 21
visits / 42 task outcomes byte for byte. On the final original baseline RSI
Spanish visit, Breakdown returned fallback at its 28-second outer deadline;
a provider request still had not settled after another 105 seconds. The probe
closed its HTTP client and exited. The parent stopped fail-closed, with the
pending request charged its full reservation.

After verifying no probe remained, [continuation](resume-remaining.py) ran
only the three never-attempted visits / six tasks in the original schedule.
It checked unchanged code, source hashes, original prefix and remaining budget,
then used the same production configuration and probe. No attempted case was
retried. The completed raw report preserves the original stop and all first
21 results, followed by the original schedule tail.

| Cost item | USD |
| --- | ---: |
| Comparison cap | 3.50 |
| Initial 48-task worst-case reservation | 3.482112 |
| Reported cost, 80 HTTP attempts | 0.0392605438 |
| Full reservations retained for 33 unreported attempts | 0.685936 |
| Accounted comparison upper bound | 0.7251965438 |
| Browser accounted upper bound, 43 attempts | 0.6286376422 |
| Combined accounted upper bound | **1.353834186** |
| Founder combined allowance | **5.00** |

The known reported combined cost is $0.196571626. An exact invoice is unavailable;
unknown attempts are never called free. The browser's $1 guard was not raised.
The four allowed simulations were used, as three UI runs plus one direct DCA
fixture. The comparison created zero further runs.

## Artifacts and limits

- [Reviewed scorecard](scorecard.json): totals, per-surface results, provenance,
  costs, limitations and explicit lack of fingerprint authority.
- [Completed raw report](raw-completed.json): all actual attempts, raw drafts,
  accepted/fallback text, request hashes, receipts, configuration and costs.
  Its original totals remain pending review by design; use the separate reviewed
  scorecard for final quality judgments, rather than editing raw observations.
- [Preflight](preflight.json) and [price snapshot](prices.json): free request
  sizing and the rates used to reserve every actual HTTP attempt.
- [Artifact manifest](artifact-manifest.json): content hashes, prefix equality,
  48-task review coverage and diagnosis-to-request binding.

The prior full scorecard named by the baseline fingerprint is retained in raw
metadata by hash and case disposition as historical evidence only. None of its
cases is counted as newly passed. This targeted composer report cannot become
`last_measured` and cannot authorize fingerprint regeneration. Browser evidence
has its own source SHAs and limits in [its report](../live-browser/README.md).
