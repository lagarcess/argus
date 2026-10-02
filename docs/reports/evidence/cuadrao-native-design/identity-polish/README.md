# Profile and invitation polish — October 2, 2026

UI-only preview on `codex/cuadrao-design-scan-recents`.

## Source and scope

Application source: `9354619d759cc1d275d1c8dcb3322aba3e17b7ce`.
Final verification source: `484776e080b784b7287c330035f229ca4a0e2e09`;
intervening commits only refine export tests. Signed build **3414** compiled,
installed and version-verified on the founder's iPhone 15. Automatic launch failed
because the device was locked; no physical interaction acceptance is claimed.

Profile has a larger existing avatar and tighter header spacing. Native photo
pan/pinch, accessible zoom/move/reset controls and original-source recropping
preserve crop Cancel and outer profile Save/Cancel independently. Plan sample
cards inherit existing art, member context and name; native sharing exports the
same composition. Photos access is add-only and requested by Save Image.
No new avatar catalog, personal QR, username/discovery, upload or real join flow.

## Verification

Eight distinct native journeys passed across focused runs:

- Settings navigation and logout clearance at larger text (retained at 7d5c46b0).
- Profile draft Save/Cancel/validation (retained at 7d5c46b0).
- Dark English support at larger text (retained at 7d5c46b0).
- Photo selection, Save/Cancel and removal (271bc805).
- Native share presentation and dismissal (271bc805).
- Crop Cancel, slider, move, pinch, drag, reopen, reset and outer Cancel (9354619d7).
- English invitation at largest Dynamic Type in dark mode (9354619d7).
- Native Save Image through the actual add-only permission alert (484776e0).

The crop test initially exposed a real presentation defect: the crop sheet was
attached to a Form Section whose rows change. Moving its state and presentation
to the editor Form fixed the same journey. Later export-test corrections target
the observed native action Cell and the actual Allow permission button.

213 source-coordinate crop geometry checks passed. Modularity budget and diff
checks passed. Final scoped review found no concrete issues; it included the
crop-presentation fix. Retained earlier screenshots were revalidated against the
final app diff: only profile crop presentation changed after their capture.

Apple Vision decoded both the displayed QR and the actual JPEG saved to Photos.
The payload remains `Cuadrao design preview | <sample group UUID>`; no join URL.
The saved JPEG was visually inspected: artwork, name, QR and sample disclosure
are intact. Fixture photos are synthetic; no personal photo is committed.

## Artifacts

- [Crop after native pan/pinch](crop-pan-zoom.png)
- [Reopened crop reset to full source](crop-reset-full-source.png)
- [Spanish invitation](invitation-card-es.png)
- [Native share sheet](native-share.png)
- [Dark largest-text disclosure and reachable share](invitation-dark-large-en.png)
- [Actual saved invitation JPEG](saved-invitation.jpg)

## Limits and owners

Photos and identity edits remain session-local UI data. Sample cards do not
create live membership. Connected avatar storage and identity belong to C08;
real invitation permissions, expiry/revocation and guest acceptance belong to
C02 in the main execution board. The design guide owns the visual rules.
