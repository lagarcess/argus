# Issue #600 verification handoff

**NOT MERGE-READY. Paid verification stopped at the spend guard.**

PR [#602](https://github.com/lagarcess/argus/pull/602) fixes focused strategy repair so a stated starting deposit stays separate from recurring contributions and the existing stated-field/cost audit runs before confirmation. Unresolved money or cost evidence asks for clarification. The reported card now retains the $1,000 starting deposit, $100 monthly contribution, 5 bps fee, and 10 bps slippage.

## Code and deterministic evidence

- Final code head: `c72fa0e94963c347c6eaeaf1bd846f8f29f58ce5`.
- Original integration base: `d53575a86641e3d37c9dfbf99bfa003e3eecc5f7`.
- Current integration: `3d379d3d9020027ccfd1f2a4c617626520af8a44`; reconciliation merge is the final code head above.
- Intervening integration changed only a six-line roadmap note. No runtime, API/data, UI-state, migration, environment, or affected-test overlap. Earlier successful reproduction evidence was retained and its output contract revalidated at the final head.
- 38 issue-specific English/Spanish replays pass through real validation and stages, including TimeoutError, ValidationError, audit outages, invalid cost evidence, preserved controls, and two-turn continuity.
- All 2,865 exact-head runtime, policy, and mocked-evaluation checks pass. Final-head CI and merged-tree modularity checks pass.
- Final Codex delta review is clean; both prior P1 threads were fixed, replied to, reacted to, and resolved. Zero unresolved threads.
- No model-facing fields, descriptions, or instructions changed. The interpret stage delegates its existing route fallback to one shared owner, reducing that file by four lines.

## Live evidence

Exactly one paid reproduction before and one after cost $0.011422 combined. The after reproduction ran at `74f07260`; final-head hermetic replay and the full live measurement retain its successful output contract.

The single full measurement ran on the clean final code head with both provider modes directly assigned `live_provider`. No commits were authored during either live run. All 71 fixtures and the model-facing source surface match the named baseline at `36086097c2608f5b51e14d9f7387be7738a75348`.

- Full run: **63 passed, 7 failed, 1 infrastructure error**.
- Named baseline: **64 passed, 7 failed**.
- Live modeled-cost fallback and English/Spanish DOCN deposit/contribution/cost continuity cases passed.
- Eight anomalous cases were scheduled for one rerun each. Discovery and BTC future performance passed. NVDA research recovered, retaining only the baseline scenario-framing failure.
- The English preset-chip DCA rerun was interrupted by the spend guard. Spanish preset-chip DCA, Spanish future performance, compound-interest composer availability, and the English indicator-capability question were not rerun.

See the [71-case comparison](case-comparison.md), [machine-readable check codes](case-comparison.json), and [verification summary](verification-summary.json). Raw prompts, model outputs, runtime artifacts, and provider responses are excluded from this published report; their detailed local files are fingerprinted in [the manifest](local-artifact-manifest.json).

## Spend stop and remaining work

Provider-reported spend, including reproductions, is **$1.857866291608**. Forty failed provider calls returned no price; $0.05 reserved per call adds **$2.00**, for **$3.857866291608 conservatively accounted**. No successful provider response was unpriced. The full-run guard was $3.50; the bounded rerun guard was $3.85, retaining $0.15 for an in-flight request below the user's $4 stop. Paid work stopped immediately at the guard.

The incomplete reruns and unresolved live failures remain verification blockers. This report does not waive them or claim readiness. The PR stays open, non-draft, labeled `bug` and `core`, and unmerged. No environment files, Render configuration, or release contracts were changed.
