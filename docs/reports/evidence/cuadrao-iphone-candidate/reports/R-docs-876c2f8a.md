# R-docs delta review: `b098ded9c..876c2f8a6` (PR #808)

Read-only review pinned to head `876c2f8a6f7bedce6d8a61807ad65bc131315114`. Docs only, 4 files, +27 / -25. Scope: the delta alone, against the nine findings in `R-docs-b098ded9.md`.

**Verdict: CLEAN.** All nine findings are fixed, and the delta adds no wrong fact, no broken anchor, and no change to the locked copy or the acceptance line.

## Findings, one by one

| Finding | Status | Checked against |
| --- | --- | --- |
| P2-1 Apple "recording fake" copies (`mvee-five-lane-handoff.md:85`, `:188`, `:571`) | Fixed | `src/argus/domain/account_deletion/service.py:717-720`: no Apple service on the process records `apple_revoke: pending` and returns `apple_unconfigured`. `src/argus/api/apple_sign_in.py:85-88`: no service is built while capture is off. No Apple revocation fake exists; `InMemoryAppleCredentialRepository` is a credential store, not a revoke fake. The three lines now agree with step 2 at `:520`. |
| P2-2 "Still open" item 2 (`mvee-five-lane-handoff.md:175`) | Fixed | `web/lib/account-deletion-api.ts:66-93`: calls the command, files the `account_deletion_request` ticket only on 404. Agrees with `:559`. |
| P2-3 `auth.sessions` readers (`cuadrao-profile-hidden-rows-backend.md:38`) | Fixed | The only two `from auth.sessions` queries in `src/argus` are `src/argus/api/auth_sessions.py:45` and `:84`, both keyed on the caller's own session id and user id. `account_deletion_auth.py` reads through that module. Nothing lists sessions. |
| P2-4 memory availability (`cuadrao-profile-hidden-rows-backend.md:44`) | Fixed | `src/argus/api/routers/personalization_memory.py:108-127`: availability depends on `current_user` only and returns `available=personalization_memory_exposed(user)`. Every other route depends on `require_memory_api_context`. |
| P2-5 placeholder map table (`DATA_MODEL.md:2477-2482`) | Fixed | `supabase/migrations/20261004090000_account_deletion.sql:234-252` (runs: `user_id`, `subject_hash`, `analytics_distinct_id`), `:261-271` (placeholder map, "Deleted when the run completes"), `:290-306` (revocations, "deleted when the run completes"). The retention rule is no longer restated; the census owns it at `account-deletion-fk-census.md:134`, inside the linked section. |
| P3-1 setext heading (`DATA_MODEL.md:2491-2492`) | Fixed | A blank line now sits before `---`. |
| P3-2 "held exactly as long as nobody runs the sweep" | Fixed | The sentence is removed. |
| P3-3 MVEE "confirms its revocation" (`argus-minimum-viable-ecosystem-experience.md:733`) | Fixed | Now "has confirmed". |
| P3-4 order rule (`cuadrao-profile-hidden-rows-backend.md:17-18`, `:47-57`) | Fixed | Rows 5 and 6 are swapped in the list and in the sections, with the section bodies moved byte for byte. "Rows 4 to 6 also depend on chat" still holds for Memory, Shared conversations and Personalization. |

## New facts, anchors and locks

- **Anchors.** `#steps-in-order` resolves to the one `### Steps, in order` heading (`mvee-five-lane-handoff.md:512`). `#lane-6-account-deletion` resolves to `:491`. The new census link `#placeholders-one-per-sharing-scope-none-tied-to-the-person` resolves to `account-deletion-fk-census.md:127`. The untouched runbook and API contract anchors in the same paragraph still resolve.
- **Founder-locked copy block.** `### Copy (founder-locked, Iris's wording)` starts at `mvee-five-lane-handoff.md:630`. The delta touches only lines 85, 175, 188 and 571. Unchanged.
- **`account_deletion_request` acceptance line.** `mvee-five-lane-handoff.md:622` is byte-identical at both commits.
- `git diff --check` reports nothing.

Not checked: rendered Markdown output on GitHub.
