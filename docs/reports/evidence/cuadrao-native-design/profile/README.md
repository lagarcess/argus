# Cuadrao Profile proposal

September 30, 2026. Native UI-only redesign of the HTML profile foundation.

## References inspected

The local mobile-lock/settings.png and settings.js root/child hierarchy were inspected before implementation.

- [Things settings](https://mobbin.com/screens/fe872e1e-90a8-4409-a62f-8360b64d7080): short single-line destinations, help separated from preferences.
- [Wise security/privacy](https://mobbin.com/screens/7ff1c601-1814-4eb0-85c2-8029227abfad): distinct account/security actions.
- [Wise personal details](https://mobbin.com/screens/8c827bb0-573a-48c3-80ae-3951b85e568a): move identity detail behind one entry.
- [Claude settings](https://mobbin.com/screens/737ee839-f3ec-4c8d-a5ec-a0ffa6b747df): account/app grouping; no upgrade promotion borrowed.
- [Apple settings guidance](https://developer.apple.com/design/human-interface-guidelines/settings): keep settings relevant and avoid confusing duplication of system options.

Mobbin images were inspected inline, not copied into the app.

## Result

One identity row; App (preferences, personalization, notifications); Cuenta (security, data/privacy, usage); Ayuda; sign out. Root has no repeated descriptions, giant branding/footer, or nested cards. All root destinations fit at the tested simulator size. The selected tab supplies screen context.

Native destinations use Form and NavigationStack. Name edits are staged with Save; preview account/preferences state has one local owner. Memory/files/chats reuse the search example definitions. Security/deletion/legal actions do not call services. Usage is explicitly unconnected. No fictional live usage counts or successful account mutations are shown.

## Verification and limits

Simulator and physical-iPhone builds passed. Inspected root (profile.jpg), Data/privacy (privacy.jpg), notifications and personal editing controls. Navigated Data/privacy -> Memory -> shared example detail and back to root. Profile editing fields and Save are reachable; text-entry/save/cancel and toggle mutation were not accepted as verified because the automation bridge did not reliably change those controls.

The separate Cuadrao Preview was installed on the paired iPhone. Automatic launch was blocked because the phone was locked; the installed update can be opened manually after unlocking. Existing Argus app identity/session is preserved. No additional simulator or build cache was created.

These screenshots remain visually applicable after consolidating the example email into the single profile owner; rendered text is unchanged. Full English, Dynamic Type, VoiceOver, physical touch interaction and connected behavior remain pending. Profile photo, complete notifications/voice/advanced, real privacy management and service integration are follow-up work, not silently retired capabilities.
