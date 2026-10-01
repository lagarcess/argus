# Cuadrao Profile flow revision

September 30, 2026. UI-only proposal, awaiting founder visual approval. Replaces
the initial Profile treatment rejected as generic. HTML remains the functional
inventory; this pass refines hierarchy, presentation and local editing.

## References actually inspected

Mobbin returned flow previews, which were visually inspected; sampled previews
are not a claim that every screen in every app was exhaustively audited.

- [Claude editing profile](https://mobbin.com/flows/05a1eb18-d66b-4ff5-ad1d-528d215476b7): focused identity editing and explicit confirmation.
- [Wise personal details](https://mobbin.com/flows/f8b5070c-d22d-4883-a2c8-174aec95d379): settings-to-identity separation.
- [Airbnb account settings](https://mobbin.com/flows/c808890f-1025-46e0-a083-2da40e5a081f): root destinations and dedicated settings page.
- [Revolut profile](https://mobbin.com/flows/b3e1e7fa-a35a-4402-a00d-449ff3483ef0): clear identity anchor and grouped destinations; no upsell/referral tiles borrowed.
- [Claude memory summary](https://mobbin.com/flows/042680b7-2b5d-4c0a-9aba-e1e86f5c6d10): progressively disclosed memory management. Cuadrao retains confirmed context; automatic inference is not adopted.
- [Apple settings](https://developer.apple.com/design/human-interface-guidelines/settings): relevant, organized app settings.

Mobbin artwork was not copied into the product. The local HTML settings.js and
previous reference notes provided the capability inventory.

## Implemented proposal

Compact identity + Edit profile; three bounded, icon-free destination groups;
consistent native child titles and surfaces; focused editing sheet with Save and
Cancel; privacy content vs sharing/recovery grouping; feedback on a child page.
All current root destinations remain reachable. Memory, files and chats still
read Search's example definitions. One profile owner holds local preferences and
feedback draft; name editing stages changes until Save.

## Verification

- Simulator build passed without diagnostics; device build passed.
- Visually inspected Spanish root, editing sheet, privacy, personalization and help.
- Opened/dismissed edit sheet, reached privacy and Help > Feedback.
- Changed response length Automatic > Brief, left and reopened Personalization,
  and observed Brief retained. This checks local state propagation.
- Saved profile.jpg, editor.jpg, privacy.jpg and personalization.jpg. Privacy
  remains visually applicable after the later unrelated feedback/field-label edits.
- Installed the separate Cuadrao Preview bundle on the paired iPhone. Launch
  was blocked by the locked device; physical interaction is pending.
- No extra simulator or build cache. Existing Argus app/session untouched.

Text-entry automation reported success without changing field values; edit Save,
changed-draft Cancel and feedback input/save are NOT accepted as verified.
Complete English, Dynamic Type and VoiceOver acceptance remain pending.
Profile photo/avatar customization, full locale/theme settings, complete
notification scheduling, formatting/voice/advanced controls, privacy management,
feedback submission, real usage/auth/security/legal wiring remain follow-up scope.
No real service mutation, support send, notifications, model calls or deployment.
