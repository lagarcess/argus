# Interleaved registry comparison at 262d670f

**Failed acceptance.** Integration passed 13 of 14 probes; the candidate passed
7 of 14. These are 28 partial probes, not a full-suite scorecard or acceptance
of the model-facing fingerprint. Prior measurements are unchanged.

The fixed [schedule](schedule.json) alternates A/B and B/A across seven cases
and two repetitions. Each probe ran in a fresh process. A used clean integration
`377190bd2911959e14ad9d92f2f4dba3edeb8453`; B used clean candidate
`262d670f6a595660b3f489535eb744201f81597b`. The candidate includes normal
integration merge `6cfe4d58e78f7c59ab7cef0aa2fcd824a3c9aa5f` from the original
base `9e8b59b23f29d432ec7603c42f7362137b1ee21f`.

All paired user/context inputs have identical hashes. The candidate harness
observes declared dispatch and generic cards; the baseline harness predates
those surfaces. Candidate macro acceptance additionally requires a completed
tool answer. Therefore the counts compare their recorded acceptance contracts,
not an assertion that every check is identical. Every original raw failure is
retained, including the candidate's tool-specific discovery assertion.

| Case | Integration passes | Candidate passes |
| --- | ---: | ---: |
| Explicit modeled costs | 2/2 | 2/2 |
| Golden cross | 2/2 | 2/2 |
| DCA with stated seed and contribution | 2/2 | 0/2 |
| Spanish BTC, first quarter of 2024 | 2/2 | 0/2 |
| Spanish unsupported-options recovery | 2/2 | 1/2 |
| Trending crypto discovery | 1/2 | 1/2 |
| Current inflation | 2/2 | 1/2 |

## What the evidence establishes

The candidate selected eight calls: five backtests and one each of
`peer_expansion`, `screening`, and `balanced_lookup`. Six probes selected no
calls. Effective runtime observations span exactly the four new intents:
seven `calculate`, three `follow_up`, two `explain`, and two `cannot`.
This sample does not establish multiple-call quality; deterministic repeated
and multiple-call proofs remain separate.

The declared-input guard still rejects equivalent representations of known
date or money facts. Its late conflict patch also sits outside the blocker
state that clarification reads. Separately, the measurement harness stops
after clarification where the real graph may continue to confirmation. A
launch-only null in these failed observations does not establish that the
original call omitted capital or contribution. Those defects require runtime
and observation repairs, not retrospective changes to these scores.

Current inflation demonstrates variance: repetition one underclaims enabled
research and makes no call; repetition two executes `balanced_lookup` and
delivers a cited answer. Neither result justifies a question-to-tool mapping.

The second trending-crypto candidate uses `screening` and returns a cited
answer, but its suggested test resolves a crypto ticker to a stock with the
same ticker. This remains a delivery defect regardless of the harness's
overly tool-specific discovery check. The original integration discovery
failure is separately retained; its voicing providers failed to deliver an
actionable result.

## Spend and provenance

The announced comparison estimate was **$0.75–$1.50**. OpenRouter reports
**$0.72215357174** across 120 priced route-receipt records out of 125; five
records remain unpriced. Receipt records are not a count of user turns.

The research provider reports another **$0.33007** for two calls. Its output
charges disagree with the pinned tariff, so this is a reported invoice amount,
not a verified charge. The [sanitized billing observations](research-billing.json)
exclude provider response identifiers. Candidate Search records $0.005; the
two baseline discovery Search calls add an estimated $0.010 at the repository
rate. The accounted-for or estimated sum is **$1.06722357174**, about **$1.07**,
plus unknown receipt costs. Unknown charges are not zero.

- [Machine-readable comparison and all raw probe links](comparison.json)
- [Preflight](preflight.json) and [execution log](driver.log)
- [Single-case helper](case-probe.py) and [interleaving driver](interleaved-probes.py)
- [Exact-copy hashes and source-log hashes](preservation-manifest.json)

All 28 raw JSON probe artifacts, the schedule, preflight, helpers, and driver
log were copied byte for byte. Preservation and diagnosis made no provider
calls. The planned full-suite run remains on hold pending repairs.
