# Confirmed deletion cleanup: source handoff

Base: `8146d16e90633eb543781f8882665482f0d5dca9`, guarded #875 landing.
This is a new isolated actor-boundary slice. The #875 worker and its historical
QA evidence are unchanged.

## Boundary and source change

`acknowledgeConfirmedAccountDeletion(_:cleanup:)` now requires a synchronous
throwing `@Sendable (UUID) throws -> Void` callback with no default. Inside the
existing actor, it acquires the mutation guard, checks absent session and pending
proof, validates completed journal/receipt owner, command and initiating revision,
invokes cleanup with the journal's exact UUID, then removes only that record.
There is no await or other suspension between admission and the effect. There is
no callback-free overload and no new cleanup journal.

The existing completed record owns cleanup retries. A thrown cleanup error leaves
it intact. If acknowledgement storage fails after successful cleanup, the same
record survives; retry must tolerate the already-missing directory. Relaunch
readback still derives the receipt from that record. Beginning a new account's
adoption already owns the mutation guard and cannot be interrupted by cleanup.

The [architect sketch](design.md) records the two alternatives and selected shape.
This is not the final app adapter. Receipt-store paths, UI and actual Application
Support directories remain untouched.

## Precise gap and prepared proof

The previous caller sequence is `clear A files; await acknowledge A receipt`.
A completed, then B signed in before that caller ran. The actor rejects stale A
at acknowledgement, but A's files have already been removed. The API cannot undo
an effect that the caller performed before admission.

[BaselineDeletionCleanupGapTests.swift](BaselineDeletionCleanupGapTests.swift)
is prepared for the exact #875 source test target. It uses the production session
actor with synthetic HTTP responses, unique temporary A/B directories and actual
filesystem operations. It observes A removal before stale acknowledgement rejects
while B and its files survive. This is an intentional historical-API baseline
probe, not a current caller. **It has not run; no runtime reproduction is claimed.**

Current package test source checks:

- A completes, B adopts, stale A callback has zero A/B filesystem effects.
- Valid completed cleanup receives the journal UUID; missing directory is
  idempotent and an unrelated user's temporary directory survives.
- Callback failure keeps files and the completed obligation; relaunch retries
  cleanup without another deletion POST.
- Successful cleanup followed by acknowledgement-storage failure keeps the
  obligation; repeated idempotent cleanup finishes without another deletion POST.
- Active B SDK adoption rejects cleanup before effects and preserves pending proof.
- Accepted 202, uncertain deletion and ordinary sign-out cannot authorize cleanup.

All fixtures live under unique temporary directories. No actual Application
Support data, provider, hosted, PostgreSQL or paid operation is exercised by them.

## Caller migration and verification limits

The executable package caller now passes an explicit test-only no-op callback
where no filesystem obligation exists. New filesystem cases supply real cleanup
callbacks. The unsafe production signature is removed.

#875's archived live harness remains immutable historical evidence. Its
[migrated copy](LiveDeletionTests.swift) passes an explicit no-op callback on its
stale-owner denial path, which has no filesystem obligation. Root's independent
QA must exercise that copied harness against this new source; the old 1-pass SDK
result does not prove the new boundary. The historical baseline probe is the only
intentional callback-free reference in this new evidence folder.

Source/static review is not runtime proof. Swift package tests, baseline gap
probe, migrated live harness, app compilation and filesystem behavior remain
unrun until root schedules independent QA. Do not create the small PR or claim
READY before that verification. No Mac, PG, hosted, provider or paid calls ran
while authoring this source.

## Author checks

Independent bounded source review of the actor and six new filesystem cases found
no concrete blocker. It ran no compilation or tests. Python modularity and diff
whitespace checks pass; source fingerprints are recorded for the queued verifier.
The callback boundary changes one production method, with no vault, server,
migration, app UI, receipt-store or actual user filesystem change.
