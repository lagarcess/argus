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
