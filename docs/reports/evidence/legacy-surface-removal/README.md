# Legacy surface removal browser evidence

Recaptured on 2026-08-07 after merging integration
`f6fc8f78253c3929229fc8950d6169e6288f7463` and applying the completed review
follow-ups through `f4e0ac06f76b1bc303526a63504bceb134604c5f`.

## Method

- Ran the local Next.js app at `http://127.0.0.1:3200/chat` with mock auth and
  the repository's synthetic, memory-only development backend.
- Used headless Playwright Chromium at a 1440 x 1000 desktop viewport.
- Asserted that `Strategies` and `Collections` were absent from the rendered
  chat and settings text.
- Observed zero browser console errors across the successful capture run.
- Stopped the local preview after capture.

No provider, LLM, Supabase, or hosted environment was called by this browser
check.

## Evidence

- `ordinary-chat.png`: the normal empty-chat composer and starter actions.
- `sidebar.png`: the expanded sidebar with New chat, Search, Recents, and
  Settings; no retired navigation destinations.
- `settings.png`: the current Profile, Data Controls, and Preferences menu; no
  retired settings rows.
