# Daily-cap notice treatment

The daily cap uses Argus's existing neutral `FailureNotice` and typed recovery
mapping. It announces status with `role="status"`, keeps the rejected question
visible, and shows the localized reset time. Copy, ratings, and the answer menu
are absent because admission stopped before Argus produced an answer. The
notice uses the available mobile width, capped at the existing 660px content
width. No new design primitive, upsell, or retry action was added.

Official product references checked on 2026-09-26:

- [Codex usage limits](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan)
  describes a limit notice/banner with the reset time and available account
  actions.
- [Grok release notes](https://grok.com/release-notes/jul-18-2026) explicitly
  describe usage-limit cards that show when the limit resets.
- [Claude Code limits](https://support.claude.com/en/articles/14552983-models-usage-and-limits-in-claude-code)
  describes a limit-reached message with the reset time and applicable recovery
  options.

These references support presenting an application status with a concrete
reset time. They do not establish identical visual styling across the three
products; no private account was deliberately exhausted to inspect a limit.
Argus's existing notice system owns the visual treatment here. Its acceptance
screenshots and browser assertions verify the actual implementation.

## Reset truth and user settings

Both compute-admission owners (`src/argus/api/chat/guest_compute_ceiling.py`
and `registered_compute_ceiling.py`) send `Retry-After` from the remaining
seconds in `align_usage_period(now_utc, "day")`. Both durable claim migrations
set the database timezone to UTC and end the window at the next UTC midnight.
The guest-session and signed-in environment overrides change the number of
questions; they do not change this reset schedule.

The web uses that response's full delay, without the 503 retry clamp, and
rounds the resulting instant to the displayed minute. Only a missing/invalid
header uses the documented next-UTC-midnight fallback. The profile supports
language, locale, country, and currency, but no timezone preference. Browser
timezone therefore owns the local display, including daylight-saving offsets;
country is not used to infer a timezone. The Usage settings panel's execution
and grounding windows are separate allowances and do not own this chat cap.

The founder's follow-up requests consistent `AM`/`PM` in both supported
languages. This overrides the package's Spanish day-period styling example
(`p. m.`), while retaining the specified localized sentence. No second parser
or quota schedule was introduced.

Verification: `tests/test_compute_reset_contract.py` exercises real chat 429
responses for guest and signed-in configured limits, at UTC midnight,
mid-day, and just before reset. Web tests check DR, UTC-positive, and winter/
summer daylight-saving display. Neither backend runtime nor user settings
were changed.
