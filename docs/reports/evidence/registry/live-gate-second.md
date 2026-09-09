# Second registry live gate

**Blocked: 52 passed, 16 failed, zero infrastructure errors and zero skipped
cases.** The full 68-case run completed in **1,590.40 seconds** at clean candidate
`d5ad4b6e1c3e475820a33fa1d55f4f6f1658e467`. This result does not accept the
model-facing fingerprint or establish lane readiness. No failed case is waived
or regraded here.

The [preflight record](verification/d5ad4b6e/preflight.json) records integration
`743dfda3da9b467d32023ac32e900dad5a392500`, research enabled, and both asset and
market-data providers in `live_provider` mode. The scorecard records Python
3.10.20, `worktree_clean: true`, and fixture hash
`6f6c535a5e1ec0c073014506cff34dc79cb7afd8a670c897b8122057ad42290c`.

- [Raw second scorecard](live-measurement-second.json).
- [Raw comparison with earlier scorecards](baseline-comparison-second.json).
- [Retained live-run terminal summary](verification/d5ad4b6e/live-summary.txt).
- [Exact-copy hashes and source-log provenance](verification/d5ad4b6e/preservation-manifest.json).
- [Browser evidence at the measured head](browser/d5ad4b6e/README.md).

The scorecard and comparison were copied byte for byte. The initial scorecard,
its comparison, and Lane C's historical evidence remain unchanged. This run
measured the corrected observation harness; it does not retroactively change
the first run's results.

## What the remaining failures show

The effective runtime intents were 44 `calculate`, 10 `follow_up`, seven
`explain`, and seven `cannot`. The primary observations were 45 `calculate`, 14
`explain`, one `follow_up`, seven `cannot`, and one absent primary value. The
model selected zero calls in 38 cases and one call in 30. These are observed
values, not a requirement to select a tool for every question.

Nine research calls executed: eight `peer_expansion` calls succeeded and one
`balanced_lookup` call returned `bounded`. Successful invocation does not
establish that every requested fact was preserved or delivered.

Recorded call arguments have already passed Pydantic validation and include
defaults. They are not raw provider JSON: an absent value may reflect omission,
an explicit null, or a nested undeclared key discarded by the permissive input
model. The replay proves what reached preparation, not which of those happened
in the provider response.

| Surface | Recorded failure and diagnostic boundary |
| --- | --- |
| Backtest inputs and recovery | Golden-cross, stated-seed DCA, Spanish cadence, and the prebaked follow-up omit canonical dates in their selected calls. The SMA call also omits capital and rule facts. Execution asks for missing facts and the delivered clarifications retain those omissions. This is not a final-patch read hiding a valid launch. |
| DCA money roles | Known seed/contribution facts remain in clarification payloads where present. Launch-only money fields correctly stay null when no launch was delivered. The available-budget case still carries an amount as a contribution while requiring a supported budget alternative. Original financial assertions remain exact. |
| Modeled costs | The call contains both numerical costs but no bounded evidence spans. A free replay strips the ungrounded costs and raises an assumption clarification blocker; stage preparation then loses that blocker and offers confirmation without those costs. A bounded-span control preserves the rates and explicit-user provenance. The repair belongs in input grounding and blocker propagation, not in the evaluator reading unlaunched inputs as delivered facts. |
| Spanish BTC | The actual prepared and delivered strategy is classified as equity with SPY, then enters coverage recovery. Synthetic resolution resolves BTC as crypto, so the live provider-resolution difference remains part of the diagnosis; no universal conversion or harness relabel is assumed. |
| Discovery and result follow-up | The comparison call carries `peer` instead of `comparison`; three calls omit the required equity hint. The trending-crypto call is bounded because its figures were unverified and delivers no actionable candidates. The result-follow-up case still delivers no next-experiment rows. These original argument and delivery checks remain failures. |

The macro-curiosity fixture originally required an honest response and allowed
conversation, education, or unsupported intent; it did not require dispatch.
The earlier baseline actually passed a no-current-data redirection. Therefore,
the registry's added `tool_dispatch: true` is a strengthened acceptance condition,
not an equivalent observation of the original contract. However, this run's
backtest-only deflection does not answer the current-inflation request and
understates the enabled catalog. Removing the dispatch condition alone would
hide that delivery and capability failure. Stable explanations may use zero
calls; currentness, grounding, and factual requirements must remain intact.
No question-to-tool mapping or fixture waiver follows from this diagnosis.

The prose judge also sees legacy rendered sidecars but does not yet observe
the generic tool-result cards. That limits its view of the bounded research
card; it does not rescue the missing completed answer or candidate delivery.

## Spend

The announced estimate was **$2–$4** for the complete pass, not a cap.

- OpenRouter reports **$1.94838523952** across 283 priced route-receipt records
  out of 293. Ten records have unknown costs. Receipt records are not a count
  of distinct user turns or additional requests; these are not described as
  ten extra requests or treated as free.
- Four Search cache misses at the repository's $0.005 rate add **$0.020** in
  estimated Search charges.
- The research Agent provider separately reports **$0.07421**. Its components
  disagree with the pinned tariff, so this is a provider-reported amount,
  not an independently validated charge. The [sanitized invoice observation](verification/d5ad4b6e/research-billing.json)
  preserves the numbers without the response identifier. The pricing anomaly
  is separate from the unverified-figures refusal.

The accounted-for or estimated sum is **$2.04259523952**, about **$2.04**, plus
unknown receipt costs. The OpenRouter sum alone is not the full bill. Evidence
preservation and diagnosis made no additional provider calls.

## Free verification and review limits

- Backend: **6,742 passed, 571 skipped, one failure**. The remaining failure is
  the owed measured-fingerprint check; this failed live gate cannot satisfy it.
  The [terminal summary](verification/d5ad4b6e/backend-summary.txt) retains the
  exact failure name and counts without copying the full log.
- Frontend: **1,629 passed, zero failed**, with a successful production build.
  Retained evidence: [unit summary](verification/d5ad4b6e/frontend-summary.txt)
  and [build log](verification/d5ad4b6e/frontend-build.log).
- Import, Lane C probe, and checkpoint checks: **133 passed**. The small
  [complete log](verification/d5ad4b6e/import-probes-checkpoints.log) is retained.
  The [modularity report](verification/d5ad4b6e/modularity.log) has no violations.
- Fixture browser: **14 passed in 21.5 seconds**, with all 12 captured PNGs
  inspected by the capture owner. The exact [console log](browser/d5ad4b6e/browser.log),
  [scroll metadata](browser/d5ad4b6e/scroll-captures.jsonl), and helper accompany
  the images. This proves rendered fixture behavior and reload continuity;
  it does not claim live backend, provider, or backtest execution. Sharing was
  default-off in this browser battery.

The local review was clean. That is not an external Codex review or terminal CI
result. This is failed-gate evidence at the measured head, not a finishing-bar
audit, fingerprint acceptance, or a clear-lane report.
