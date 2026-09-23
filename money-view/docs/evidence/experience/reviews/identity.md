# Guest, currency and expiry review

Reviewed the immutable `identity-review.patch`, implementation report, experience plan and guest/currency API contract. All 20 package hunks matched the current files when checked; no drift was observed in the reviewed changes. Current code outside the package was read only to trace existing session authority, runtime admission and composition.

## Spec compliance: pass

No reachable P1/P2 findings in the scoped package.

- Guest entry assigns isolated server-owned identities and households. Active guest re-entry retains the same session, choices and fixed expiry. Creation and optional demo seeding share one transaction, including capacity admission.
- Claim checks current ownership, role and household generation, retains IDs and records, saves the explicit credentials, marks the guest claimed and revokes prior sessions before issuing a new local session.
- Expiry lives in the shared `active_context` query used by persistence checks. Unclaimed guests cannot pass that authority at or after expiry; claimed users retain ordinary local-account access.
- Guest-origin reset restores unknown country/currency and preserves the original expiry record. It does not seed again.
- Display currency derives from an owned active ledger account, a visible override or the existing household default. Foreign/deleted selections fail even with an override. Unknown stays null, and account/transaction money is never relabeled or converted.
- Guest creation uses the existing HTTP login-admission path and a transaction-protected lifetime capacity limit. The demo callback creates independent household-owned synthetic records; it does not copy fixture identities or another household's records.

## Code quality: pass

No additional actionable P1/P2 findings. Session issuance is shared by login, guest entry and claim; guest expiry extends the canonical authority rather than adding a separate writer-specific rule. Currency resolution is read-only and retains provenance. The new seed is bounded and participates in identity creation's transaction. The changes remain proportionate to the local guest scope.

The package tests cover isolation, claim/session rotation, stale role/generation, expiry during a real feedback write, reset, currency precedence/precision and seed rollback. The implementation report states identity plus guest suites passed 60 tests in 7.95 seconds, with scoped Ruff clean; the captain additionally reports the focused default-account check passed. These results were not rerun. This review makes no browser, live-provider, hosted-identity or deployment acceptance claim.

## Country-null and settings metadata delta: clean

Reviewed only the new country normalization, settings metadata pass-through, corresponding regression and contract text in the immutable `review-packages/identity-delta` package. All four packaged files match their manifest hashes.

Spec compliance and code quality both pass for this delta. Explicit `country:null` maps to the existing empty-string storage representation and serializes back as null; omitted country stays unchanged. The current owner/role/generation write checks remain in place. Clearing country preserves an explicit currency override and the canonical ledger account currency. Settings passes `guest` and `currency_context` directly from the identity snapshot, introducing no second derivation.

The parameterized regression covers both registered and guest entry, persistence, omission versus clearing, metadata parity, account-derived fallback, override preservation and rejection of null household names. The captain reports 62 tests plus two focused override cases passed; these checks were not rerun. No actionable P1/P2 findings, and the previous clean package review remains closed. Chat, commands and search integration are outside this delta.

## Canonical snapshot generation delta: clean

Compared the immutable `identity-generation` package with the previously reviewed `identity-delta` package. All three files match their manifest hashes. Spec compliance and code quality pass; no actionable P1/P2 findings.

The snapshot reads `data_generation` through the existing `common.active_context` authority inside the same read transaction as the profile, household, preferences and currency fields. It exposes that value without storing a second generation or changing tokens, sessions or lifecycle state. Documentation scopes private draft keys by user, household and generation. The added regression covers two resets, claim, household-switch snapshot and fresh login. The captain reports 63 tests passed; tests were not rerun. Earlier clean scopes remain closed.
