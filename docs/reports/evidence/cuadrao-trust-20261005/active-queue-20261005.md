# Active queue update

Integration is `7018e0edebbc370b999005a857230bf3c3a1ad8b`. The original base remains `875de09ac2115acec42e09060b92878aa5f18eff`.

Landed PRs are 851, 844, 846, 858 and 857. Landing housekeeping is still in progress through the documentation PR. No feature activation or hosted mutation occurred.

The founder approved Apple-only revocation validation and explicit reauthentication for older mixed-provider sessions of unknown provenance. The session journal remains the single provenance owner. The session owner README carries the canonical implementation contract.

PR862 final retry-header delta is independently reviewed at `d11390cd816688463f4669ad90471685d427c24d`. Independent API/auth/OpenAPI selection passed 66 tests with zero skips or failures. Prior 219-check independent state and PostgreSQL proof remains applicable to unchanged domain code. Exact-head CI remains queued.

PR863 is independently reviewed at `d2347166f78df1a1e67f52ab194936ee14ab210b`. Independent verification passed 295 tests with no skips or failures. The integration baseline passed 22 tests; a controlled delayed socket close reproduced ECONNRESET. Historical CI causality remains inferred. Current GitHub jobs were cancelled without executing steps because a hosted runner was not acquired. No merge readiness claim is made.

PR847, PR849 and PR854 have separate reconciliation owners. The captain remains the only integration merge owner. The analytics owner holds the exclusive local PostgreSQL slot. The session owner holds the exclusive Mac/simulator slot to fix the reproduced notification admission interval.

Open product gates remain #798 orphan/linking policy, #819 shared roots, decision17 obligation amount/provenance/settlement ownership, transmission consent version/scope, #818 retained jobs and memory/voice inclusion, and late provider-side Apple revoke recovery. Phone, hosted readback, provider deletion proof and legal approval remain external gates.
