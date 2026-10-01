# Household invitation link — September 30, 2026

Spanish-first native design preview; English copy is maintained in the same views.
Supersedes the name-entry/Simular aceptación mock in the cold-start checkpoint.

## Try it

Existing mirror: http://localhost:3200/.
Hogar → Invitar a alguien → Compartir invitación opens the real iOS share sheet.
After a link exists, the quiet Personas shortcut reopens its status and controls.
Home no longer carries an invitation-status card; see the [People separation](../household-people/README.md).
Close it with X to return. Ver como invitado shows the recipient screen with
Aceptar invitación and Ahora no. Acceptance shows confirmation; Continuar returns
to the sender's household preview with sample member Alex. No personal accounts
are created or shared by acceptance.

The iOS sheet lists installed sharing apps. This simulator has no WhatsApp or
Messages sharing extension; a device can present its own supported destinations.
The actual shared payload explicitly says it is a preview and uses a reserved
non-resolving cuadrao.invalid URL, not a production invitation. No messages were
sent or contacts requested during verification.

Sharing creates a local example link once and reuses it while available. Closing
the sheet or completing a sharing action does not prove delivery or acceptance.
The UI says Enlace disponible / Nadie se ha unido todavía. Only the recipient's
explicit sample acceptance updates membership. Cancelling invalidates the local
invitation; a future invitation gets a fresh identity. Recipient acceptance checks
that its invitation is still current. Relaunch resets all sample invitation state.

## Verification

Build succeeded, no reported warnings/errors:
`build_run_sim_2026-10-01T00-10-26-967Z_pid12375_9141aa80.log` (UTC filename).

Inspected native journey: create Household → open invitation → native share sheet
→ close without sharing → link available, no member → recipient preview → Ahora
no, state unchanged → reopen → accept → confirmation and joined Household.
Separate pass: cancel invitation → confirm → invitation action restored.
Screenshots are included. git diff --check passed.

The preview was relaunched with `-AppleLanguages (es) -AppleLocale es_DO` to verify
Spanish system actions (Copiar / Agregar a Lecturas). Installed extension names
remain owned by the system/extensions. User/device-wide language settings were not
changed. English strings are present and source reviewed; this continuation's
native interaction checks were Spanish. The previous cold-start pass included an
English Home visual check.

Uses the same simulator (8AFB6084-8918-416E-9164-E21061306BEC), bundle
(local.cuadrao.design), project and /private/tmp/cuadrao-native-design-build cache.
No new simulator or build directory.

## References and boundaries

- [Splitwise member invitation](https://mobbin.com/flows/9b15f463-36ad-4752-9ccc-aec98127fa83): direct members and share-a-link entry points.
- [Alan family invitation](https://mobbin.com/flows/1a1edfa6-6c51-4b11-9b6b-3e47016e463a): email and access explanation, not its broad default sharing policy.
- [DICK’S list sharing](https://mobbin.com/flows/469ee0f4-c7c2-447d-b489-876db447c803): standard native share sheet, not household access semantics.
- [Apple activity views](https://developer.apple.com/design/human-interface-guidelines/activity-views).

Still open: recipient authentication/install handoff, real token validity and
recipient restrictions, server membership/permissions, existing-account sharing
consent, expiration/revocation recovery, member removal/leave, device and larger
text/VoiceOver acceptance. This UI proposal does not authorize or implement those
contracts. The example recipient represents an already signed-in person.
