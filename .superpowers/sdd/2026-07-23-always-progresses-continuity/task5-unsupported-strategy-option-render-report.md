# Task 5 Unsupported Strategy Option Render Report

## Outcome

Typed `unsupported_strategy_logic` options now render as the existing
`select_response_option` action in both live final events and persisted reload
hydration. The assistant's LLM-authored recovery text remains unchanged.

## Root Cause

The backend already persisted an `unsupported_recovery` clarification with
`reason_code = unsupported_strategy_logic` and three typed options. The
frontend localized those options inside recovery text, but projected actions
only for coverage recovery and unsupported timeframes. The live final-event
path and persisted hydration path therefore both dropped the option controls.

## Red Evidence

Command:

```text
cd web
bun test __tests__/chat-recovery-display.test.ts \
  __tests__/chat-message-hydration.test.ts \
  __tests__/alpha-frontend.test.ts
```

Result before production edits: exit 1, 102 tests passed, 3 failed, and 1
module export error. The exact failures proved:

- the generic strategy-option projector did not exist;
- persisted strategy recovery hydrated `message.actions` as `undefined`;
- `ChatInterface` did not project unsupported-strategy actions from final
  events.

## Implementation

- Added one typed metadata projector for the existing RSI threshold,
  buy-and-hold, and moving-average crossover option kinds.
- Required a matching typed option id and typed `replacement_values`.
- Rejected unknown, missing, or mismatched option metadata.
- Forwarded the server-provided `replacement_values` object unchanged so the
  backend remains the admission authority.
- Reused existing localization keys and the existing
  `select_response_option` action type.
- Wired the same projector into live final events and persisted message
  hydration.

No backend, API, schema, lifecycle, timeframe, provider, dependency, or action
type changed.

## Files

- `web/lib/chat-recovery-display.ts` — typed action projection and safety
  filtering.
- `web/lib/chat-message-hydration.ts` — persisted reload wiring.
- `web/components/chat/ChatInterface.tsx` — live final-event wiring.
- `web/__tests__/chat-recovery-display.test.ts` — supported payload and unsafe
  metadata coverage.
- `web/__tests__/chat-message-hydration.test.ts` — LLM voice and reload
  coverage.
- `web/__tests__/alpha-frontend.test.ts` — live wiring contract.
- `.superpowers/sdd/task5-unsupported-strategy-option-render-report.md` — this
  evidence record.

## Green Evidence

```text
cd web
bun test __tests__/chat-message-hydration.test.ts \
  __tests__/chat-recovery-display.test.ts \
  __tests__/chat-retry-actions.test.ts \
  __tests__/chat-retry-action-history.test.ts \
  __tests__/chat-lifecycle-source.test.ts \
  __tests__/alpha-frontend.test.ts
```

Result: exit 0, 153 passed, 0 failed.

```text
cd web
bun test __tests__
```

Result: exit 0, 466 passed, 0 failed.

```text
cd web
bun run lint
```

Result: exit 0.

```text
cd web
bun run build
```

Result: exit 0. Next.js compiled, TypeScript completed, and all 13 static pages
generated. Node emitted the existing `DEP0205` `module.register()` deprecation
warning.

```text
git diff --check
```

Result: exit 0.

## Complexity Assessment

The correction is proportional: one shared projector, two small wiring points,
and focused tests. The projector derives actions only from typed ids and
replacement values; it does not parse the original prompt, assistant prose, or
display labels. The label map was simplified after the first green pass. No
new abstraction or public contract was needed.

## Commit

Commit SHA: the exact SHA is the commit containing this report and is recorded
in the worker handoff. A Git commit cannot embed its own final SHA because that
text would change the commit content and therefore change the SHA.

The slice is independently committable and reversible.

## Remaining Gates

- Browser QA was not performed because this delegated correction explicitly
  forbids browser QA. Founder-visible daily-bar unsupported momentum recovery
  should verify all three localized option buttons live, select the
  moving-average option, and reload the same controls.
- Release-captain review remains required before promotion.
