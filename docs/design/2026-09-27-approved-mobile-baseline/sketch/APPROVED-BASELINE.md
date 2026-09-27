# Argus sketch — approved visual and interaction baseline

Founder accepted this sketch as the current design baseline on September 27, 2026: “ok good enough, lock all of this”.

Entry point: `index.html`, currently served at http://127.0.0.1:8025/.
This document records the accepted sketch. `INHERITANCE.md` contains source comparisons, detailed decisions and verification limits. It does not supersede repository product/API/data authority or authorize production implementation, deployment, or unfinished native capabilities. `typography.html` is an earlier exploration, not this baseline.

## Preserve when continuing the design

- Keep the current Argus visual identity: restrained near-black/white surfaces, muted semantic accents, Space Grotesk and Inter. Bundled fonts match the repository assets. Financial amounts stay neutral unless an actual status/change warrants semantic color; figures use tabular numerals.
- Primary CTAs are near-black pills with white labels; secondary actions use a light neutral fill. Surface CTA targets are at least 48px. Remove decorative CTA arrows; use chevrons for navigational rows. Keep appropriate chat-specific follow-up behavior distinct.
- Shared mobile surface headings use Space Grotesk 500 at 32/22/18px; body uses Inter. Existing chat/settings-specific sizes remain. Marketing headline sizes are not mobile defaults.
- Bottom navigation: Home, Accounts, Chat, Plan, Search. Preserve the glass treatment and icon-only presentation. Reading scroll shrinks the main-surface bar while retaining all five destinations; upward scroll expands it. Updates keeps its separate hide-on-scroll treatment. Profile/settings keeps its own navigation treatment.
- Header: bell/profile outside active conversations. Empty Chat keeps Recents/New chat plus bell/profile; active Chat keeps Recents/New chat plus Share/More. No phone conversation title or redundant Argus branding in the chat header. Recents/Search/options retain titles. New chat has one header entry point. Header targets are 48px, with 8px group gaps and 16px side spacing.
- Preserve the continuous scroll-edge blur without solid banner seams; Profile & settings overview and Personal details are excluded. Keep reduced-motion/transparency behavior.
- Preserve inherited profile icons, avatar choices, feedback types/templates and settings details. Shared Conversations naming, notification settings concept, Rate the App concept, smaller ghost A and version/build placeholder remain.
- Preserve the time-sensitive greeting, starter prompts and empty-chat A. The subtle neutral edge-light study is decorative, not loading; reduced motion disables it.
- Composer: two rows, “Type a message” placeholder, Plus below left, dictation and future spoken-conversation controls below right. Text/attachments reveal Send in place of the waveform. Keep 48px toolbar targets and 8px spacing.
- Plus opens the composer-attached tray with Scan receipt, Choose photo and Upload file; it replaces starter chips while open. No separate context picker or mock @ anchoring. Existing production mentions are not changed.
- Typing closes the tray. Opening Plus while typing exchanges the keyboard for the tray. On a real phone, keyboard appearance hides the menu and positions the composer directly above the keyboard; keyboard dismissal restores the resting composer/menu. Avoid an intermediate layout jump. Desktop focus without a software keyboard leaves navigation available.
- Outside background taps dismiss keyboard/tray without clearing or sending. Scrolling alone does not dismiss them. Interactive controls retain their first-tap action. Drafts persist across surface switches in the local session. Escape respects the active dialog/tray/focus layer.

## Boundaries that remain open

Native keyboard transitions, safe areas, hardware touch targeting, native back gestures and haptics still require device verification. The web sketch uses a viewport heuristic and does not establish native acceptance. Some toolbar pointer checks were unreliable through browser automation and were checked with keyboard activation instead.

All accounts, chats, captures, proposals and settings are disposable local examples. Reload resets session data. No live model, microphone, camera, upload, bank connection, persistence, notifications, sharing publication or store integration is implied. Final account onboarding, real cross-surface context transport and backend contracts remain separate work. Design acceptance is not runtime acceptance.

## Preservation

A timestamped sibling checkpoint contains this complete sketch, font assets/licenses, inheritance notes, available preview screenshots and SHA-256 checksums. The zip archive is verified against those bytes. Earlier checkpoints remain intact. Continue subsequent exploration in the working sketch without rewriting this checkpoint.
