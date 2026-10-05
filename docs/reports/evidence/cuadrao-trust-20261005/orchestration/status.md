# Orchestrate status

Generated: 2026-10-05T20:38:20.358Z

## Units

States: landed=5, needs-verify=10

| ID | Track | State | Branch | PR | SHA | Brief |
| --- | --- | --- | --- | --- | --- | --- |
| identity-safety | identity | landed | codex/cuadrao-social-release-safety | 844 | 36c70b91ef03ffcfcc7482a7714a0f244fe5fe4e | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| deletion-recovery | deletion | landed | codex/cuadrao-deletion-recovery-proof | 846 | cea9f6e18c582615dee44cf1a7d3a05b936b660a | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| analytics-deletion | deletion | needs-verify | codex/cuadrao-personless-deletion | 847 | 0334808e08e41baa0305fe28a8c167dbb89ebbbc | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| privacy-evidence | privacy | needs-verify | codex/cuadrao-privacy-evidence | 845 | bdb276c656e160ca39c419d9d61a2dc1ec1fcebc | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| primary-currency | foundations | needs-verify | codex/cuadrao-primary-currency | 853 | 82a5f39c017a8ee1ecb2f4f89a90f9f11f7ca3eb | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| paired-transfers | foundations | needs-verify | codex/cuadrao-paired-transfers | 854 | 95c01e8c08d8315f5cb2e5439c70e0b467d223e8 | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| privacy-manifest | privacy | needs-verify | codex/cuadrao-app-privacy-manifest | 849 | 20c2252d0e97197ef1e200b3063750191432f371 | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| native-buttons | identity | landed | codex/cuadrao-native-provider-appearance | 857 | fb847fc340a7c7acac55922691fa0f99c50e33a6 | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| apple-binding | identity | landed | codex/apple-identity-binding-800 | 858 | ad2e7d84236bc2bc0f0ffb82d3e0c9e6b9f6f04d | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| apple-deletion | deletion | needs-verify | codex/apple-deletion-admission-20261005 | 862 | d11390cd816688463f4669ad90471685d427c24d | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| apple-session | identity | needs-verify | codex/cuadrao-apple-session-20261005 | 864 | 9419001712dc9f070741909312982f19d1e08e72 | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| recovery-address | operations | needs-verify | codex/recovery-trusted-client-ip | 865 | 45939369dcf915660c43a83d3cf54d1348ee4dc3 | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| ci-release-resolution | operations | landed | codex/cuadrao-ci-release-resolution | 851 | c4f9a08b6fc9cf429b47c4cd024183db02fcd959 | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| canary-fixture | operations | needs-verify | codex/issue-861-canary-fixture-close | 863 | d2347166f78df1a1e67f52ab194936ee14ab210b | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |
| apple-lock-observer | operations | needs-verify | codex/867-apple-lock-observer | 868 | 511660c642b6208de46bf1bd3990f9c70b756517 | docs/reports/evidence/cuadrao-trust-20261005/preflight.md |

## Verification ledger

Verdicts: live-ui-verified=2, unit-test-verified=17

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
| 864 | 9419001712dc9f070741909312982f19d1e08e72 | live-ui-verified | https://github.com/lagarcess/argus/pull/864#pullrequestreview-5419906859 | gpt-6-astra | 2026-10-05T20:12:31.972Z |
| 847 | 0334808e08e41baa0305fe28a8c167dbb89ebbbc | unit-test-verified | https://github.com/lagarcess/argus/pull/847#issuecomment-6001886300 | gpt-6-astra | 2026-10-05T20:16:34.482Z |
| 849 | 20c2252d0e97197ef1e200b3063750191432f371 | unit-test-verified | https://github.com/lagarcess/argus/pull/849#issuecomment-6001853802 | gpt-6-astra | 2026-10-05T20:16:34.565Z |
| 854 | 95c01e8c08d8315f5cb2e5439c70e0b467d223e8 | unit-test-verified | https://github.com/lagarcess/argus/pull/854#issuecomment-6001859083 | gpt-6-astra | 2026-10-05T20:16:34.648Z |
| 845 | bdb276c656e160ca39c419d9d61a2dc1ec1fcebc | unit-test-verified | https://github.com/lagarcess/argus/pull/845#issuecomment-6001966060 | gpt-6-astra | 2026-10-05T20:16:34.729Z |
| 862 | d11390cd816688463f4669ad90471685d427c24d | unit-test-verified | https://github.com/lagarcess/argus/pull/862#pullrequestreview-5419720370 | gpt-6-astra | 2026-10-05T20:16:34.820Z |
| 863 | d2347166f78df1a1e67f52ab194936ee14ab210b | unit-test-verified | https://github.com/lagarcess/argus/pull/863#issuecomment-6001780582 | gpt-6-astra | 2026-10-05T20:27:06.578Z |
| 865 | 45939369dcf915660c43a83d3cf54d1348ee4dc3 | unit-test-verified | https://github.com/lagarcess/argus/pull/865#issuecomment-6002222420 | gpt-6-astra | 2026-10-05T20:27:06.670Z |
| 851 | c4f9a08b6fc9cf429b47c4cd024183db02fcd959 | unit-test-verified | https://github.com/lagarcess/argus/pull/851#issuecomment-5998839785 | gpt-6-astra | 2026-10-05T20:38:19.893Z |
| 868 | 511660c642b6208de46bf1bd3990f9c70b756517 | unit-test-verified | https://github.com/lagarcess/argus/pull/868#issuecomment-6002426471 | gpt-6.1-sol | 2026-10-05T20:38:20.238Z |

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

<!-- orch-summary {"unitStates":{"landed":5,"needs-verify":10},"ledgerVerdicts":{"live-ui-verified":2,"unit-test-verified":17},"frontierGeneration":0,"openGateIds":["apple-late-cleanup","balance-source","consent-policy","identity-policy","release-jobs","space-model"]} -->
