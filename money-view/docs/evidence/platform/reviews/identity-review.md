# Identity/settings review

## Fix re-review: addressed

Reviewed only `identity-review-fix.diff` against the original P2 and for new breakage in that delta. The reported 26 focused tests and Ruff pass were not rerun.

**Final spec compliance verdict: pass for the reviewed identity/settings backend scope.** The original final-membership finding is addressed. Removal now clears personal records for the removed household. If memberships remain, credentials, preferences, other households' records and sessions remain usable. Final-membership removal uses the same `delete_local_identity` function as account deletion, clearing personal identity records and credentials and leaving an inactive referential tombstone. Shared financial data is preserved.

**Final code quality verdict: pass for the fix delta.** No new actionable findings. Cleanup remains inside the existing transaction; the shared helper preserves the prior account-deletion behavior. The added parameterized lifecycle test covers both final and non-final removal, personal-data cleanup, preserved other-household access, unchanged shared domain data and restart behavior.

The API handoff documents the destructive removal policy and its required UI confirmation. Frontend confirmation remains a captain-owned integration check, outside this backend diff review.

Reviewed the frozen `identity-review.diff` against `money-view/docs/PLATFORM_PLAN.md` and the identity API handoff. Read-only inspection; the reported 24 focused tests and clean Ruff result were not rerun. No application code, Git state, environment, providers, or services were changed.

## Initial spec compliance: changes requested (superseded)

The backend covers persistent credentials/sessions, personal preferences/profile/avatar, household roles and canonical country currency, confirmed memories, export/reset/deletion, usage/help and local-only feedback. Archive/trash correctly belongs to the assistant domain. One reachable member-lifecycle gap prevents the removed user from completing the promised personal-data lifecycle.

### [P2] Removing the final membership strands the user's personal data

- **Location:** `money-view/server/platform/identity.py:530-537` (`remove_member`). Related gates: `Identity.login` rejects users without memberships, `Identity.context` requires a current membership, and `settings.delete_account` requires that context.
- **Trigger:** A locally created member saves a confirmed memory or feedback, then the household owner removes that member. All normally created users have exactly one membership.
- **Actual result:** Removal deletes the membership and revokes sessions, while leaving the active user row, password hash, preferences, memories and feedback. Subsequent login fails with `household_access_denied`. The member cannot export or delete their personal data. Creating a member again generates a new user ID, so that action cannot restore access to the retained records.
- **Impact:** Ordinary member removal creates an inaccessible account with retained personal information and no supported cleanup path. This is separate from correctly denying further access to shared household data.
- **Requested change:** Define and implement the final-membership removal behavior so retained personal data remains manageable or is explicitly disposed of. A bounded local policy is sufficient; do not silently delete shared household financial records. Add one lifecycle check covering save personal data, remove the final membership, and the chosen recoverable/cleanup outcome.

## Initial code quality: changes requested (superseded)

No additional actionable quality findings. SQLite transactions keep multi-domain reset/deletion atomic, current requests derive roles from membership, password changes revoke existing sessions, and memory/feedback reads enforce user plus household ownership. Settings use a shared validated preference document; effective currency derives from household country/override rather than relabeling financial records.

Intentional fixture credentials are not reported as a vulnerability. Loopback Host enforcement, complete domain registration, deposit ownership and frontend behavior remain captain-owned integration surfaces; this review makes no acceptance claim for those surfaces.
