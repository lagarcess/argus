# Argus Result Voice Bridge Implementation Plan

> **For agentic workers:** Execute inline from this branch. Keep the slice small:
> remove the visible Try next result action, preserve typed next-step follow-ups,
> and verify the current Quick take / Explain result boundary.

**Goal:** Make the approved result voice bridge real in product code, not just in
docs. Quick take and Explain result remain visible result surfaces. Try next is
not a visible result-card action. A user-typed next-step question still routes
through the backend result follow-up path.

**Architecture:** Backend result cards stay canonical and already emit
`show_breakdown`, `save_strategy`, and `refine_strategy`. The web app must treat
that set as the only visible result-card action set and must not render unknown
or legacy result actions from persisted metadata. Backend next-experiment facts
remain available only for typed follow-up answers.

**Guardrails:**

- Do not remove Quick take.
- Do not remove Explain result.
- Do not delete backend `next_experiment` follow-up handling.
- Do not add Research Lab or Perplexity integration.
- Do not make frontend prose invent result explanations or next tests.
- Do not broaden the hidden Strategies/Collections surfaces.

## Tasks

- [x] Add a frontend regression that a result card hides legacy
  `next_experiment` / `try_next` actions while keeping Explain result and
  Refine idea.
- [x] Add a hydration regression that persisted result metadata drops unsupported
  visible result action types before card render.
- [x] Patch the web result-action helper and card ordering to use one visible
  allowlist: `show_breakdown`, `refine_strategy`, `save_strategy`.
- [x] Keep backend follow-up tests green so typed "what should I try next?"
  still uses `next_experiment` focus and supported fact-bank options.
- [x] Run focused web/backend tests, `git diff --check`, and browser smoke the
  result surface if the local app starts cleanly.

## Execution Notes

- Focused frontend tests passed.
- Focused backend follow-up and breakdown tests passed.
- Production web build passed.
- `git diff --check` passed.
- Browser smoke was attempted against `http://127.0.0.1:3000/dev/result-card`,
  but local `next dev` returned 404 for both `/` and `/dev/result-card` in this
  environment. The dev server was stopped; browser live QA remains a readiness
  batch item.

## Acceptance Criteria

- No visible Try next action or CTA can be rendered from result-card action
  metadata.
- Explain result remains visible.
- Refine idea remains visible.
- Save remains available only through the existing strategies flag behavior.
- Typed next-step follow-up behavior remains intact.
- Focused tests pass and the implementation is committed as one completed slice.
