# Legacy surface removal browser evidence

Captured on 2026-08-06 from the candidate working tree after merging
`038a4e7750d49ad284d6d902b37b221496a70b16` and applying the four review
follow-ups. The final commit does not change the rendered UI.

## Method

- Ran the local Next.js app at `http://127.0.0.1:3000/chat` with mock auth and
  the repository's synthetic, memory-only development backend.
- Used Playwright Chromium at a 1440 x 1000 desktop viewport.
- Asserted that `Strategies` and `Collections` were absent from the rendered
  chat and settings text.
- Observed zero browser console errors during the successful settings run.
- Stopped the local preview after capture.

No provider, LLM, Supabase, or hosted environment was called by this browser
check.

## Evidence

- `ordinary-chat.png`: the normal empty-chat composer and starter actions.
- `sidebar.png`: the expanded sidebar with New chat, Search, Recents, and
  Settings; no retired navigation destinations.
- `settings.png`: the current Profile, Data Controls, and Preferences menu; no
  retired settings rows.
