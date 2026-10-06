# Active integration queue

Original integration: `875de09ac2115acec42e09060b92878aa5f18eff`. Current fetched integration: `5d46a73d4d97b0412dccff517eb43c73e4316977`. Canonical checkout fast-forwarded cleanly. Seventeen implementation slices and housekeeping #860 landed; [per-PR records](README.md) own exact lineage and limits. Current protected-branch housekeeping is #873.

#864 landed after final independent review, 17 successful and three expected-skip exact-head checks, zero unresolved threads and guarded merge. Required PostgreSQL matrices passed 731 each with zero skips; backend passed 10,398 with 1,248 explicit non-required skips. The committed record preserves the intermediate introduced failures and repairs. Integration CI37405778022 and smoke37405778015 are running. #860 integration CI passed attempt2 and smoke passed; narrow cancellation issue #872 is closed with original evidence retained.

## Remaining queue and accepted local proof

| Unit | Source and dependency | Local proof and remaining gate |
| --- | --- | --- |
| Apple first-name journal | Tested `a6efe6e3360f1c4e58c97807b91547de527b0b04`; evidence publication `0f4b8b59c1006b2c92454403dad4cbc21a57854d`; PR #874 final `6ec654919775f0f5001c2c7732e18c9507618762` reconciles landed864 | 150 package passes/four optional local skips, 16 focused, three independent, one signed local API/Auth/PG, 22 configuration, one actual model UI/four screenshots. Publication review clean. Final reconciliation review clean with all401 native hashes unchanged; PR CI remains. |
| Native deletion command | Tested `cc58b16f7f8ee4f520ffa4658f1396ba7a0cc4d7`; evidence-only publication `21bb4c65c70a472f90b6c92c56c1255e5b0d1017`; follows name/session | 164 package passes/four existing optional local skips, 19 focused, one actual Swift SDK/API/Auth/PG journey, generic app build. Introduced notification regression reproduced against baseline and fixed. Publication review, dependency landing, final review and CI remain. |
| Home primary currency C1 | `87a616ef09ef2e8f746f7a5db29b03bd6d40a31e`; recovered UI parent | Independent source review clean. Native execution and EN/ES connected persistence/permission proof remain; recovered UI PR creation approval pending. |
| Plan currency C3 | `27dc03711ab93b5a6273da6ab1394ab4d97f6f78`; follows C1 | Source review clean; actual native execution pending. Future forecast does not supply historical Home balances. |

The final deletion UI and confirmed-only draft filesystem cleanup are separate unfinished work. Deletion202 retires the session and preserves token-free acknowledgement/drafts.503 uncertainty quarantines ordinary dispatch and resolves only with valid proof. Expired proof uses existing operator/support fallback. Local deletion's recording analytics fake proves command behavior only, not provider deletion. No new cron or operator assignment.

## Contracts and ownership

Founder approved Apple-session-only validation and explicit reauthentication for unknown mixed-provider sessions. Known email/Google sessions retain access. The existing successful grant journal owns provenance. Root owns one integration queue and serial shared-contract changes. Counsel owns recovered UI presentation; root owns #820 contract coordination. [History handoff](shared-home-history-contract-audit.md) proposes the smallest traceable read payload and next unit; its product meaning remains pending, separate from C1/C3.

[Resource record](orchestration/resources.json) owns active leases. Name and deletion-core QA leases are released and own temporary services/fixtures cleaned. Root stack stays running. No foreign stack, simulator, phone or checkout cleanup is authorized.

Seven open product gates are recorded in [gates](orchestration/gates.md): #798 orphan/link policy; #819 shared roots; decision17 balance provenance and settlement owner; #828 transmission scope/version/other-person data; #818/#826 retained jobs and memory/voice; late provider revoke recovery; first Home history meaning. Do not invent an answer or repeat unanswered questions.

## External acceptance

Physical Apple/Google authorization, hosted application/readback, provider deletion completion, legal approval and feature activation remain open. Release social/deletion/analytics/paired-transfer flags remain off. No main promotion, deployment, hosted mutation, legal publication or tester exposure occurred.

Known limits: #852 old SciPy, #855 earlier CI port binding, #856 Google XXXL, #859 Unicode parity, #866 baseline TypeScript. Narrow #850/#848/#861/#867 defects are resolved. CI infrastructure failures #870/#872 retain original evidence and successful unchanged-SHA retries. No whole trust-pillar completion or full device acceptance claim.
