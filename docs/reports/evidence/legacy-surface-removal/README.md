# Legacy surface removal browser evidence

Captured on 2026-08-06 from the candidate tree based on
`9664e221fa50187d6b078ccdfcffd90cbc76d852`.

## Method

- Ran the local Next.js app at `http://127.0.0.1:3109/chat` with mock auth.
- Used Playwright Chromium at a 1440 x 1000 desktop viewport.
- Fulfilled only the ordinary read requests needed for this visual check with a
  registered QA profile, normal usage allowances, and one recent chat.
- Asserted that `Strategies` and `Collections` were absent from the rendered
  chat and settings text.
- Observed zero browser console errors during the successful settings run.
- Stopped the local preview after capture.

No provider, LLM, Supabase, or hosted environment was called by this browser
check.

## Evidence

- `ordinary-chat.png`: the normal empty-chat composer and starter actions.
- `sidebar.png`: expanded Recents with a normal persisted chat row; no retired
  navigation destinations.
- `settings.png`: the current Profile, Data Controls, and Preferences menu; no
  retired settings rows.
