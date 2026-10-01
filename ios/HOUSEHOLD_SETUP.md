# Connected Household

The Connected Cuadrao shell mounts Household Home, account details and Search
beside Personal. `ARGUS_HOUSEHOLDS_ENABLED` stays server-default-off. The native
client uses the canonical `/api/v1/households` and `/household-invitations` API;
it has no membership store or money calculation. Accounts remain on Home.

Create/open and recipient preview/defer/accept are separate from People and
explicit account consent. Acceptance grants membership only. Owners choose
current members and view-only access; activity editing is an explicit switch.
People also exposes invite revocation, member removal, transfer and close/leave.
Household Plan and Argus show their supported-scope notice.

The existing device-only write journal is partitioned by actor and Household
namespace. It stores exact command bytes and the original membership/version.
Retry survives relaunch and uses the same key. Invitation creation replay has
metadata but no recovered capability; revoke and replace that invitation.
Selection and authorization changes invalidate protected reads and editor state.
Departure returns to Personal without deleting legitimate financial records.

## Verification entry points

- `ios/FinancialModelTests/run_household.py`: actual presentation model with
  controlled transport delay, scope change, sign-out, asset decoding and retry.
  Set `ARGUS_HOUSEHOLD_MODEL_SCRATCH_PATH` to the assigned isolated cache.
- `FinancialLoopUITests/testHouseholdTwoUsersConsentEditingRevocationAndSpanishRelaunch`:
  create, defer/accept, explicit view access, relaunch, edit permission, expense
  25 then correction20 (1000→975→980), actual Search hit/back context, Spanish
  relaunch, owner withdrawal and recipient absence. It creates its own fixture.
- `FinancialLoopUITests/testHouseholdConfirmedResponseLossCreateAndAcceptRecoverAfterRelaunch`:
  opt-in confirmed upstream success followed by response loss, saved journal,
  relaunch, exact retry and one original Household/membership outcome.
- `FinancialLoopUITests/testHouseholdResumeEditingSearchAndWithdrawalOnPreservedFixture`:
  optional continuation on the same actual fixture, using public fixture UUIDs.

Use the existing secure `ios/scripts/auth/run-ui.py` credential injection. Never
put credentials or invitation capabilities in committed files or screenshots.
The current lane uses API59520, Auth59501 and PostgreSQL59502. Recovery alone
uses the assigned proxy59532 with
`ARGUS_TEST_RESPONSE_LOSS_PROXY=true` and
`ARGUS_TEST_FAULT_URL=http://127.0.0.1:59532/__fault`; direct API configuration
is restored afterward by the runtime owner. `--port-base 59500 --api-port 59520`
selects those endpoints in the runner.
The new bundle and cache are owned by the execution manifest; the old demo
remains separate. Tests use existing ConnectedChrome helpers and no auth bypass.

Continuation accepts `ARGUS_TEST_HOUSEHOLD_RESUME_STAMP`,
`ARGUS_TEST_HOUSEHOLD_RESUME_ID`, `ARGUS_TEST_HOUSEHOLD_RESUME_SHARED_ID`, and
`ARGUS_TEST_HOUSEHOLD_RESUME_PRIVATE_ID` through the secure runner's in-memory
xctestrun environment. It requires the assigned local fault URL as an allocation
guard; no fault needs arming for that continuation.

Stable selectors include `household.add`, `household.intro.create/join`,
`household.selector`, `household.people`, `household.share.account.<UUID>`,
`household.share.member.<membershipUUID>`, `household.share.edit.<membershipUUID>`,
`household.account.<UUID>`, `household.correct.<activityUUID>`,
`household.search.<activityUUID>` and `household.pending.retry`. Account and
activity controls are scoped to the active `screen.home` or `screen.search`.
UI test screenshots cover safe consent/detail states and never the invitation.

Backend regression coverage lives in `tests/household/` and
`tests/financial_accounts/test_household_projection.py`. PostgreSQL cases create
and clean only their own UUID users. They cover canonical consent incarnation,
receipt races/rejoin, hidden legs/history/refund dependencies, account attribution,
unknown currency totals and original-owner RLS. The migration disposition and
exact wire are in `docs/DATA_MODEL.md` and `docs/API_CONTRACT.md`.
