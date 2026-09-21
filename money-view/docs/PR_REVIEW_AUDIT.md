# Clara prior PR review audit

Audited 2026-09-21 04:23 UTC. Read-only GitHub queries and local inspection; only this report was written. This audit concerns PRs merged during the Clara task and the relevance of their deferred scope to the current platform expansion. It is not acceptance of the uncommitted platform implementation.

## Conclusion

**The GitHub review loop for PR #657 did continue until an explicit clean acknowledgment on the latest fix delta.** Both reported P2 defects were fixed by consolidating ownership, rather than special-casing the reported example. No unresolved GitHub finding was carried into the private merge. No currently reachable leftover from those two defect classes was found in this bounded inspection.

Exactly one merged Clara PR was found by querying the private base and inspecting first-parent history from the original task base: [#657](https://github.com/lagarcess/argus/pull/657). The other task-local first-parent commits are the plan and private CI isolation. Older Argus PRs precede task base `708864ef76961df2767d7e09c2fbf5f9812179c7` and are excluded.

## Verified review sequence

All times below are UTC on September 21, 2026.

| Time | Record | Result |
| --- | --- | --- |
| 00:01:08 | [Initial scoped request](https://github.com/lagarcess/argus/pull/657#issuecomment-5753692900) | Standalone local app; concrete math/provenance, recovery, continuity and UI findings requested. |
| 00:06:53–54 | Review of `1f3d34d3a680edebe7286ea130873296574fe48b` | Two P2 inline findings: [confirmation amount](https://github.com/lagarcess/argus/pull/657#discussion_r4058533974), [country qualifier](https://github.com/lagarcess/argus/pull/657#discussion_r4058533978). |
| 00:16:55 | Fix `cb7402bb79f5229e0948f651a160ebed4a5be990` | Shared confirmation inputs and server-owned localized country names; related large-amount layout fix. |
| 00:17:51 | Evidence head `429f5dd17d297c5433d7bf653376bdb066bfaf16` | Confirmation and large-amount regression evidence recorded. |
| 00:18:35–37 | [Amount reply](https://github.com/lagarcess/argus/pull/657#discussion_r4058563887), [country reply](https://github.com/lagarcess/argus/pull/657#discussion_r4058563940) | Explained ownership changes and regression checks; both threads now resolved by the owner. |
| 00:20:31 | [Delta review request](https://github.com/lagarcess/argus/pull/657#issuecomment-5753827428) | Explicitly scoped `1f3d34d` → `429f5dd` to changed mechanisms and callers. |
| 00:22:50 | [Reviewer clean acknowledgment](https://github.com/lagarcess/argus/pull/657#issuecomment-5753840888) | Codex found no major issues and named reviewed commit `429f5dd17d`. This is a clean comment, not a formal APPROVED review. |
| 00:23:54 | Merge `d48249dc8f0fd955fa6ee16c11d99d4eb111aedb` | Merged only to `codex/money-placement-pilot`. |
| 00:25:28 | [Terminal audit](https://github.com/lagarcess/argus/pull/657#issuecomment-5753857260) | Written after clean acknowledgment and merge. |

Fresh GraphQL read: **2 total review threads, 2 resolved, 0 unresolved**, with no additional page. The clean acknowledgment followed the last PR commit; no subsequent fix delta was left unreviewed. Two `verify` checks are completed/success at the exact reviewed head: [PR run](https://github.com/lagarcess/argus/actions/runs/35547261632/job/106175290236), [push run](https://github.com/lagarcess/argus/actions/runs/35547259505/job/106175283870). Supabase Preview is completed/skipped. `git diff --exit-code 429f5dd… d48249dc…` returned zero: the merge tree equals the reviewed tree.

The committed [local verification record](evidence/LOCAL_VERIFICATION.md#independent-review) says three independent local reviewers also closed their scoped follow-ups. Their individual conversations and acknowledgment timestamps are not attached to the PR, so this audit independently verifies the GitHub loop; it does not promote that local summary into separately verified reviewer transcripts.

## Were the bugs fixed by class?

| Defect class | Implemented mechanism | Current expansion assessment |
| --- | --- | --- |
| P2: displayed money disagrees with edited confirmation | Removed the form's private input copy; `confirmation.inputs` owns form edits, summary and compute request. Not an NZ-only correction. | Retained in `web/src/components/Confirmation.tsx:22` and `web/src/useMoneyView.ts:144–160`. The new deposit page passes the same confirmation/edit/compute contract at `web/src/features/deposits/DepositsPage.tsx:72`. The old sample-money header is gone. Its direct draft editor is hidden once confirmation/result exists (`:61`), so it does not present competing active values. |
| P2: browser reconstruction strips synthetic provenance | Removed `Intl.DisplayNames`; locale-keyed server catalog names own country presentation. | Both direct editor (`DepositsPage.tsx:65`) and confirmation (`Confirmation.tsx:100–102`) render the supplied name. Synthetic qualifiers survive the new direct path. |
| Related long-amount overflow | Shared long-amount rendering handles formatted values across summary and result rows; regression covers maximum supported amount. | Comparison component and its layout rules remain. New platform layout still requires its own browser acceptance; old screenshots do not verify the new shell. |

Other pre-PR corrections are documented at `docs/evidence/LOCAL_VERIFICATION.md:61–64`: numeric bounds, sourced zero fees, strict provider wire types, interrupted-load recovery, CLI result attribution, immutable input dates, dated notices, stable saved inflation references, and failure visibility. Current tests exercise these mechanisms, including boundary values, stale/concurrent loads, failed rechecks, and original receipt preservation. The PR history records them within initial implementation commits, so exact local review-round timing cannot be reconstructed from Git commits alone.

## Deferred or unimplemented scope under the new architecture

| Prior limitation | Current relevance and disposition |
| --- | --- |
| Single-user identity and ownership | **Now required by the expansion**, with material privacy/durable-state impact if omitted. Current code adds authenticated context at `server/app.py:73–77`, confirmation/result ownership checks at `server/service.py:53–65`, household-scoped saved answers/notices at `:435–495`, and deposit export/reset at `server/platform/deposits.py:8–78`. Composition registers that lifecycle domain (`server/platform/composition.py:25–30`). Focused household tests verify cross-household denial, recheck ownership, reset/export isolation and restart persistence. This is an implemented expansion requirement, not an unresolved #657 defect. |
| Real SB/BCRD data, rate semantics, publication dates and reuse permission | **Still intentionally deferred.** SB refuses calculation readiness (`server/providers.py:310–318`); BCRD remains explicitly unavailable (`:321–329`). HTTP publication and CLI loading still instantiate fixtures (`server/app.py:141–150`, `server/jobs.py:14–34`). Expansion does not justify replacing missing financial evidence with guesses. No reachable unsourced live calculation was found. |
| Arbitrary-language live model quality | **Still unverified.** Explicit fixture interpretation and optional configured model remain separate (`server/interpreter.py:320–377`). Current platform plan retains typed keyless actions and requires semantic interpretation for free text. No live model was invoked in this audit. No claim that mocked tests establish language quality. |
| Installed cron, hosted operations and production identity | **Still outside the authorized local scope.** A local loader command exists; the platform plan continues to prohibit deployment and production changes. Do not treat their absence as defects in this local delivery. |
| Old shell browser evidence | **Needs new acceptance evidence.** The prior result/confirmation mechanisms remain, but the new navigation, household transitions and direct editor change their presentation. Validate the platform's own acceptance journeys and responsive matrix; do not reopen #657 or reuse its screenshots as proof of the new UI. |

## Verification and bounded follow-up

On the current working tree, without live providers:

- `cd money-view && .venv/bin/python -m pytest -c pytest.ini tests/test_domain.py tests/test_providers.py tests/test_service.py tests/test_placement_households.py -q`: **75 passed**.
- `cd money-view && .venv/bin/python -m pytest -c pytest.ini tests/test_api.py tests/test_platform_composition.py -q`: **15 passed**, one third-party Starlette deprecation warning.
- Inspected merged fix delta, present confirmation/country rendering, deposit ownership/lifecycle adaptation, provider fail-closed paths, GitHub threads/comments/reviews/checks and private first-parent history.

No new P1/P2 defect is asserted by this bounded audit. Complete the already planned expanded-platform review and browser acceptance, concentrating on household/session transitions, direct deposit edit → confirm → save → notice continuity, both localized synthetic labels, and long amounts. Keep real provider/model/hosted-operation limitations explicit until separately authorized and verified. No further review request on unchanged #657 is warranted.
