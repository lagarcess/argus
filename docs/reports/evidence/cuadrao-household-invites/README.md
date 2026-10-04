# Cuadrao iPhone: Household and beta invitation journeys

**Head these screenshots vouch for:** `031ad3cd018a77e1672366e9cde044d4087dadf9` on
`claude/cuadrao-household-invites-ios`, the plain merge of `origin/codex/cuadrao-release-ui`
(`c82f093d5`) into the lane's code head `1051c7f829890ca4c29396f407499efc5ba8cfbd`. The branch
started at `ad0532f11a6c3c199c9c6d82a01329dd0bddafcc` (W1's merge of integration `a8c37d3a`). The
commit that adds this folder changes only files under it.

**Simulator:** iPhone 17e, iOS 27 simulator, UDID `8B7975F1-1338-4966-90E2-770416CAF174`, Xcode 27.0.

## What these screenshots are, and what they are not

They come from `ios/ArgusFoundationUITests/InvitationsUITests.swift`. The tests launch the Debug app
with `--invitations-harness`, which shows the connected invitation screens and the real
`InvitationsModel` over `InvitationsStubServer`. The stub answers `/api/v1/invites` with the response
shapes in `docs/api/openapi.yaml` and the problem codes in `src/argus/api/households.py`. A typed code
picks the server outcome, for example `EXPD-…` answers `409 invitation_expired`.

They are simulated acceptance. They do not prove a round trip against a local or hosted API. No
local backend was started for this lane, because worker W4 holds the local Supabase stack. The
request list for a live round trip is in the lane report.

The sign-in screen in the signed-out shots is a stand-in inside the harness. The real sign-in flow
is `ConnectedCuadraoAuthFlow`, which shows the same saved-invitation notice above it.

Connected Cuadrao keeps light welcome tokens in every appearance (`WelcomePalette.adaptsToAppearance`),
so the gate pages look the same in the dark shots. System screens, such as the Invitations list,
follow dark mode.

## Screens

Every name ends in `-es-light`, `-es-dark`, `-en-light` or `-en-dark` (es-419 and en).

| File prefix | State |
| --- | --- |
| `gate-ready` | Signed in, the server gate is on and the account has not been admitted |
| `gate-invalid` | A code that names no invitation (`404 invitation_not_found`) |
| `gate-rate-limited` | Too many lookups (`429 invite_rate_limited`) |
| `link-saved-signed-out` | A cuadrao.ai invitation link opened while signed out. The intent waits for sign-in |
| `invitations-hub` | Sent invitations with server states (accepted, not accepted yet), and the founder's group links (full with waitlist overflow, expired) |
| `personal-invitation-created` | A new beta invitation: quota from the server, code, link and QR, and "sharing is not acceptance" |
| `admitted-link-return-es-light` | An admitted person opens a beta link. Nothing is redeemed and they return to the app |

## Rerun

```bash
SIMULATOR_ID=<udid> docs/reports/evidence/cuadrao-household-invites/capture.sh
```

The script runs only `InvitationsUITests` through `ios/scripts/verify.sh`, exports the named
attachments into `screens/` and scales them to 1280 px.
