# Issue #600 evidence

**All 22 founder-authorized reruns passed once each on `87462331901929711bfe5d689197e94f0f1693b5`.**

The batch ran from 2026-09-13T22:36:17.626509+00:00 through 2026-09-13T22:49:01.326347+00:00. All 18 cases that passed at `c72fa0e9` stayed passing. The English and Spanish preset-chip cases, compound-interest case, and indicator-capability case also passed. No case was retried, no stop condition fired, and no commit or tracked edit occurred during the run.

This documentation commit follows the measured runtime without changing code. Current documentation-head CI and the fresh Codex review are recorded on [PR #602](https://github.com/lagarcess/argus/pull/602). The PR remains unmerged.

## What was verified

- Eighteen DCA cases, both issue-271 modeled-costs cases, and the two specified English conversation cases: **22 passed**.
- Both provider modes were assigned `live_provider` directly. The live calendar probe passed. Python, fixture hash, runtime flags, and clean-head provenance are retained in [targeted-live-reruns.json](targeted-live-reruns.json).
- All **139 transport calls succeeded and returned prices**. Three post-response clarification `contract_violation` checks triggered fallback; all three cases recovered and passed. Those extra validation receipts are not additional billable calls. This batch cost **$0.70380389896**. Total accounted spend is **$4.842059844568**, including **$2.05** reserved for 41 earlier unpriced failed calls, below the **$5.75** stop. See [cost-summary.json](cost-summary.json).
- The exact runtime head passed **2,782 free checks**, including all ten focused measurement replays, plus Ruff, modularity, CI, and a [clean Codex delta review](https://github.com/lagarcess/argus/pull/602#issuecomment-5654755603). The 38 original issue replays cover forced primary timeout, fallback validation failure, stated deposits/costs, outages, and reply continuity.
- No model-facing fields, Field descriptions, or instructions changed. The contribution-preservation flag is recorded in both logs and structured repair receipts.

## Historical comparisons and limits

The single full measurement at `c72fa0e9` produced 63 passes, 7 failures, and 1 infrastructure error, against the fingerprint file's named baseline of 64 passes and 7 failures. The later batch at `2ff09be4` stopped after 7 passes and a zero-seed failure. These records remain separate from the latest 22-case rerun; this is not a new 71-case scorecard. See the [case-by-case comparison](case-comparison.md) and its [check codes](case-comparison.json).

The original before/after reproduction used one paid attempt each and cost $0.011422 combined. The after reproduction ran at `74f07260`; later real-stage deterministic replays retain that output contract.

The zero-seed scripted reconstruction fails on `c72fa0e9`, `8eb7cc75`, and `2ff09be4`. It first breaks at `74f07260`; its parent `d53575a8` passes. The corroborated-zero control passes on all those heads. The fix at `87462331901929711bfe5d689197e94f0f1693b5` restores canonical zero-seed behavior while positive unowned deposits and unowned contributions still require clarification. Scripted reply bodies are authored reconstructions, not recordings of the live response. See [deterministic-replays.json](deterministic-replays.json).

The Spanish NVDA golden-cross case reaches `unsupported_recovery` on the forced primary `TimeoutError` then fallback `ValidationError` path on both integration `3d379d3d` and `c72fa0e9`. That path predates this PR and was not rerun in the later paid batches.

**Money-role limit:** when the audit returns one amount equal to the draft's owned contribution, the guard keeps it as the contribution. Distinguishing an additional same-sized deposit would require reading the text. When both money roles are separately audited, an unowned deposit still requires clarification. A zero seed follows the canonical DCA default.

## Integration and evidence handling

The original integration base was `d53575a86641e3d37c9dfbf99bfa003e3eecc5f7`. `c72fa0e9` reconciled integration `3d379d3d`. Integration has since advanced to `6eb93d84c269b4e40a0ac935aac2fb933f10676f` through the receipt-tier constraint fix. The only shared surface is receipt persistence: its tier check widens to existing runtime tiers; this PR changes repair metadata without changing tiers. Interpreter, card, API, UI, environment, and pricing behavior do not overlap. The would-be merged tree passes modularity and all 36 focused receipt checks. The branch code remains identical to the measured head for this docs-only delivery.

Published artifacts contain check codes, counts, cost totals, and provenance. Prompts, model outputs, raw provider responses, and full route payloads are excluded. The [local artifact manifest](local-artifact-manifest.json) retains hashes of detailed source artifacts. The daily rerun automation was deleted.
