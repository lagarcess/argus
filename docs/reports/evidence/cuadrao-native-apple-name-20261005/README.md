# Native Apple first-authorization name

## Scope and lineage

The native callback now formats Apple's `fullName` with `PersonNameComponentsFormatter` and synchronously journals the input through the existing `CredentialVault` before starting asynchronous sign-in. Names never enter Auth metadata or a second profile store. The API response remains the canonical profile.

Original dependency head is PR #864 commit `a24a6c60627460ddfd6042b3f42b342c5eff11f0`. Server name command is settled by PR #869. Original integration reference is `7d037b07d4b98b34c6c0ad3026811c7d2f28ae47`, merged normally into the isolated native branch. Intervening integration changes concern server money/deletion, environment membership and documentation. There is no native session-owner overlap. The name command consumes the landed server contract.

This branch cannot be READY until #864 lands, its final owner changes are reconciled, and the captain grants the serialized native verification slot. Global providers remain off. No provider, hosted, paid, simulator or device action is part of this evidence.

## Caller and ownership

```swift
let name = apple.fullName.map { PersonNameComponentsFormatter().string(from: $0) }
let authorization = try auth.prepareAppleName(displayName: name, subject: apple.user)
// The preceding call completes before the callback starts its Task.
let outcome = try await controller.signIn(with: credential,
    appleAuthorizationCode: code, appleNameAuthorization: authorization)
```

A vault-owned pregrant record contains only intent UUID, Apple subject, display name and creation time. It expires after 24 hours, is pruned on restore or the next callback, and requires a fresh successful Apple grant for the same subject after an interrupted exchange. Restore never replays a stored authorization code or ID token. No code/token is stored in the pregrant intent.

Actual grant adoption promotes the intent into `StoredSession` with durable user UUID and grant UUID, under `.apple` sign-in provenance. Existing `PendingCredentials` retains its revoke/adoption meaning. SDK refresh derives the pending command and grant method from that envelope. Before dispatch, the session owner requires the current account epoch, canonical `/me` user ID, canonical Apple subject and successful Apple credential validation. Different subjects discard the command without dispatch.

`POST /api/v1/me/apple-name` receives only `display_name`. A canonical successful envelope, including a server no-op for an existing name or explicit clear, acknowledges the exact bound intent. A lost response or outage retains the account-bound command for restore or `retryAppleNameInitialization(expectedIdentity:)`. Name failure remains separate from code capture and never replays its one-time code. Sign-out and refused adoption use the existing account retirement owner. An unavailable adoption before `/me` succeeds preserves the subject-only callback for a fresh grant; no signed-in claim is made for an incomplete adoption.

Two alternatives were considered. Replacing the entire vault with one large envelope gives atomic transition writes but rewrites mature revocation storage. Keeping a separate command journal throughout its life duplicates cross-record account binding. Pregrant record followed by the existing session envelope is the smallest design that covers the callback-to-grant interval and keeps authenticated facts in one owner. Keeping the pregrant copy until successful adoption handles a crash between promotion and cleanup.

## Verification status

Synthetic regression source covers callback durability before grant, Unicode/trim, name outage, lost response/relaunch, no code replay, explicit edit/clear no-op, different subjects, sign-out/stale identity, denied adoption, SDK refresh preservation, unknown grant refusal, expiry, late revalidation, uncertain Apple validation, callback storage failure and failed durable acknowledgement.

No Swift build or test has run yet. The Mac lease remains with the captain's active owner. `git diff --check` and the Python modularity budget on the reconciled tree pass. Independent source review found recoverable adoption failures clearing the callback; the fix now preserves it for coded 5xx and storage failure. Review of that fix delta returned clean. Runtime verification and exact-head native build remain pending. This document is source preparation, not terminal acceptance.
