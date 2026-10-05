# Orchestrate status

Generated: 2026-10-05T19:50:31.991Z

## Units

States: ci-blocked=1, landed=4, needs-verify=4

| ID | Track | State | Branch | PR | SHA | Brief |
| --- | --- | --- | --- | --- | --- | --- |
| identity-safety | identity | landed | codex/cuadrao-social-release-safety | 844 | 36c70b91ef03ffcfcc7482a7714a0f244fe5fe4e | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| deletion-recovery | deletion | landed | codex/cuadrao-deletion-recovery-proof | 846 | cea9f6e18c582615dee44cf1a7d3a05b936b660a | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| analytics-deletion | deletion | ci-blocked | codex/cuadrao-personless-deletion | 847 | 9cf4d9f9b3b45de257b68b5a49269703f7c995f0 | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| privacy-evidence | privacy | needs-verify | codex/cuadrao-privacy-evidence | 845 | ada3250e1626e8f8a465e8d756e2c1c91b4bc78e | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| primary-currency | foundations | needs-verify | codex/cuadrao-primary-currency | 853 | 82a5f39c017a8ee1ecb2f4f89a90f9f11f7ca3eb | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| paired-transfers | foundations | needs-verify | codex/cuadrao-paired-transfers | 854 | b482f575a4d0561c7426517348dc9522adcb0673 | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| privacy-manifest | privacy | needs-verify | codex/cuadrao-app-privacy-manifest | 849 | 5a20a16d0f4bad89c0190940cdf62b4c10f4901a | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| native-buttons | identity | landed | codex/cuadrao-native-provider-appearance | 857 | fb847fc340a7c7acac55922691fa0f99c50e33a6 | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| apple-binding | identity | landed | codex/apple-identity-binding-800 | 858 | ad2e7d84236bc2bc0f0ffb82d3e0c9e6b9f6f04d | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |

## Verification ledger

Verdicts: live-ui-verified=1, unit-test-verified=8

| PR | SHA | Verdict | Evidence | Verifier | Timestamp |
| --- | --- | --- | --- | --- | --- |
| 846 | 6669205de08deb64532950eeabdd1bbf2ab0bc2c | unit-test-verified | https://github.com/lagarcess/argus/pull/846#issuecomment-5998523337 | gpt-6-astra | 2026-10-05T16:22:54.640Z |
| 844 | 6ba39d12b997dcf43888e68d33340ce20c2922a4 | live-ui-verified | https://github.com/lagarcess/argus/pull/844#issuecomment-5998577353 | gpt-6-astra | 2026-10-05T16:27:28.951Z |
| 845 | ada3250e1626e8f8a465e8d756e2c1c91b4bc78e | unit-test-verified | https://github.com/lagarcess/argus/pull/845#issuecomment-5998587413 | gpt-6-astra | 2026-10-05T16:27:29.013Z |
| 847 | 8b83d96f24a3200251750246f6318e536d51f37a | unit-test-verified | https://github.com/lagarcess/argus/pull/847#issuecomment-5998608818 | gpt-6-astra | 2026-10-05T16:27:29.071Z |
| 844 | 36c70b91ef03ffcfcc7482a7714a0f244fe5fe4e | unit-test-verified | https://github.com/lagarcess/argus/pull/844#issuecomment-5999723189 | gpt-6-astra | 2026-10-05T18:11:38.625Z |
| 846 | cea9f6e18c582615dee44cf1a7d3a05b936b660a | unit-test-verified | https://github.com/lagarcess/argus/pull/846#issuecomment-5999811273 | gpt-6-astra | 2026-10-05T18:11:38.744Z |
| 847 | 9cf4d9f9b3b45de257b68b5a49269703f7c995f0 | unit-test-verified | https://github.com/lagarcess/argus/pull/847#issuecomment-5999893237 | gpt-6-astra | 2026-10-05T18:11:38.762Z |
| 849 | 5a20a16d0f4bad89c0190940cdf62b4c10f4901a | unit-test-verified | https://github.com/lagarcess/argus/pull/849#issuecomment-5999893593 | gpt-6-astra | 2026-10-05T18:11:38.780Z |
| 858 | ad2e7d84236bc2bc0f0ffb82d3e0c9e6b9f6f04d | unit-test-verified | https://github.com/lagarcess/argus/pull/858#pullrequestreview-5418732816 | gpt-6-astra | 2026-10-05T18:11:38.797Z |

## Frontier

Generation: 0
Lowest unmerged: none

(none)

## Gates

| ID | Status | Question | Options | Default | Answer |
| --- | --- | --- | --- | --- | --- |
| ownership | resolved | Confirm previous coordinator stopped writing shared integration. | Existing accepted decision or explicit founder answer | Keep dependent work blocked. | Final overnight transcript ends at 2026-10-05T16:05:22Z with all workers and resources cleaned; fetched integration matched its final SHA before new ownership. |
| identity-policy | open | Settle issue 798 orphan and Hide My Email linking policy. | Existing accepted decision or explicit founder answer | Keep dependent work blocked. |  |
| balance-source | open | Supply canonical decision 17 balance amount provenance and settlement owner. | Existing accepted decision or explicit founder answer | Keep dependent work blocked. |  |
| consent-policy | open | Settle consent scope and versioning plus memory and voice release inclusion. | Existing accepted decision or explicit founder answer | Keep dependent work blocked. |  |
| space-model | open | Select #819 consumer ownership migration: retain personal roots with existing household grants, or household-owned shared roots. Recommendation: preserve existing ownership/grants for the bounded first migration. | Founder product decision; no experiment can select product scope | Keep dependent implementation blocked; continue independent authorized work. |  |
| release-jobs | open | Settle #818 first-release retained chat jobs and connected memory/voice inclusion. Recommendation: bounded financial read and revision-confirmed proposed-write jobs; defer unassigned connected memory/voice activation. | Founder product decision; no experiment can select product scope | Keep dependent implementation blocked; continue independent authorized work. |  |
| apple-late-cleanup | open | Accept #803 rare provider-side late revocation recovery or require stronger coordination. Recommendation: documented forced-sign-out recovery with activation/phone gates; do not claim local CAS cancels an Apple request already received. | Founder product decision; no experiment can select product scope | Keep dependent implementation blocked; continue independent authorized work. |  |

<!-- orch-summary {"unitStates":{"ci-blocked":1,"landed":4,"needs-verify":4},"ledgerVerdicts":{"live-ui-verified":1,"unit-test-verified":8},"frontierGeneration":0,"openGateIds":["apple-late-cleanup","balance-source","consent-policy","identity-policy","release-jobs","space-model"]} -->
