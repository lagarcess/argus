# Currency provenance delta review — frozen

Verdict: **clean; no actionable finding in the scoped currency-source delta.** Compared the frozen package to `chat-default-currency`, `command-capabilities-final`, and prior `ui-fixes-final` UI files. Unchanged domains were not reopened.

- The resolver distinguishes UI fallback from explicit/account/record currency instead of promoting an inferred code to explicit provenance.
- Proposal inspection and preparation use `ui_default` for the fallback; explicit command arguments continue to win. Default provenance has no stated-request ID.
- Revisions retain the original currency source when currency is unchanged. An explicit currency edit deliberately stops inheritance and produces explicit provenance.
- Calculations mark the fallback `assumption`, the existing copied contract's available source; recomputation preserves it when unrelated inputs change.
- Canonical persisted cards retain these sources on reload. The frontend schema accepts `ui_default`, and both catalogs label it as app currency preference under a neutral source heading.

All seven frozen files match manifest SHA-256 `75f7b196a63a5b9a4db236966b8c6866261eba13b68919deed245bf0488b2304`:

- `money-view/server/platform/chat.py`: `5b65c16638d15f7b7e5853a20ac1b1a188ae59e5bdd133d15fbe119393372e38`
- `money-view/server/platform/command_contracts.py`: `47dd6ca71ba49f757568b495fc4af5a2565a19fa0621ff84c77b8f077c3e00b2`
- `money-view/server/platform/commands.py`: `612dc0446e66e8b1d210ab5efd363f9099d4e0593888561c2ab468f2a751843b`
- `money-view/tests/test_platform_chat.py`: `9967badc5de84f99d53f55812d601191362cedbb0a092b672427c8d157a92533`
- `money-view/web/src/features/chat/contracts.ts`: `71d16b15a7b9fd386e57087938ac21ff49fcc9e8cb9cbaac1ef3348580a0cb0c`
- `money-view/web/src/features/chat/copy.ts`: `fee8ee6b9c46da9c30bbf8708cc117f3e928380ef3e19ec482b12ea9af7f1bbe`
- `money-view/web/src/features/chat/cards.tsx`: `ff57aea1de550b3657b4897645b936535ddd58e4d62eec3d1b9e3806ba573a4d`

Verification limits: inspected the added prepare, revision, recompute, and transcript-reload regressions; did not rerun the worker's reported 104 passing backend tests or launch browser/network/provider processes. Root owns final build/browser acceptance. Only this review report was written.
