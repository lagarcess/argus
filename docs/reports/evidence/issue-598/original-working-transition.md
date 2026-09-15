# Superseded working-transition implementation

This historical report describes the first implementation, which Codex rejected.
The current acceptance record is [README.md](README.md).

# Issue #598: second-tab reply refresh

## Cause and change

The activity runtime already learned that remote work moved to `idle`, but it
invalidated transcripts only for conversations outside the active view. The open
second tab was deliberately skipped. Both history and activity-mutation responses
now use one settlement handler, reading only accepted reducer state. An open
conversation without a local request asks the existing API transcript loader for
saved messages. The sender retains its stream-owned transcript. Navigation owns
message replacement, account/navigation cancellation, hydration and scroll restore.
No new message store, activity transport, API contract, or model-facing text.

## Browser proof

Chromium 1.59.1 Playwright runner, two pages in one browser context, one shared
intercepted API fixture. All API requests are fulfilled locally; unexpected API
requests fail. No providers or paid runs. This is browser/UI proof, not live backend
persistence proof. Saved reply text is deliberately fixture-authored in both locales.

- Red: unchanged integration `edeaffa9f6565e4750fa0685a050f10aefd6d718`.
  Both `en` and `es-419` see working activity, then the sender sees the reply;
  the observing tab still lacks it after ten seconds.
- Green: both tabs contain exactly one saved reply and one user message. Observer
  makes one new saved-message request; sender makes none. A repeated activity
  projection does not load or append again. No reload or focus injection after
  completion: the existing activity poll discovers settlement.
- Existing scroll-position acceptance passes: a reader above the latest activity
  keeps their position and the Jump control still reaches the new activity.
- Eleven activity browser cases pass. Four pre-existing suite failures reproduce
  on the unchanged integration code: result-card heading, mobile Recents opener,
  clarification rail count in English, clarification rail count in Spanish.
  These remain outside #598; `baseline-browser.txt` records all four plus the two
  expected #598 failures. No acceptance assertion was weakened.

| Locale | Before, observer | After, observer | After, sender |
| --- | --- | --- | --- |
| English | [red](red/598-en-tab-b.png) | [green](green/598-en-tab-b.png) | [sender](green/598-en-tab-a.png) |
| Spanish | [red](red/598-es-419-tab-b.png) | [green](green/598-es-419-tab-b.png) | [sender](green/598-es-419-tab-a.png) |

## Deterministic verification

- Reload unit tests first failed (7 expected failures), then passed.
- Frontend suite after reconciliation: 1,998 passed.
- Frontend lint: zero errors, eight existing warnings outside this change.
- Production frontend build: passed.
- Required free mocked evaluation harness: 270 passed; retained through integration
  because no evaluator, runtime interpretation or model-facing surface overlaps.
- Shared modularity budget: passed on the reconciled tree.

Reproduce from the repository root:

```sh
bun test --cwd web __tests__/conversation-activity-transcript-reload.test.ts __tests__/use-conversation-activity.test.tsx
PLAYWRIGHT_PORT=3198 bun run --cwd web test:e2e conversation-activity-ui.spec.ts --grep 'second tab|completion while scrolled'
```

## Integration and evidence provenance

- Original integration base: `edeaffa9f6565e4750fa0685a050f10aefd6d718`.
- Reconciled integration: `a4a183138aadf1cff8268d0ce169e444732116fe`.
- One-way merge: `08caf9863aadf679d969bbea1cd6bceaae5cb4d2`.
- Overlap: #604 adds sharing providers around ChatInterface messages/composer and
  changes receipt-only API/data contracts, receipt migration and locales. It does
  not change activity projection, message loading, request ownership or our tests.
  No environment variable changes. Shared rendering-owner overlap warrants the
  repeated 11-case activity browser acceptance, full frontend suite and build.
- Red evidence remains valid for the original integration baseline. Green images
  and accepted log were recaptured after reconciliation with the callback cleanup
  below. The final PR audit will explicitly revalidate these committed images at
  the exact PR head after CI and the requested Codex review return.
- Review and CI are pending at evidence commit time; this is not a terminal audit.

Tested web file blobs (before the evidence-only commit):

- `web/__tests__/conversation-activity-transcript-reload.test.ts`: `672d362e84307d87bfcfb9ebe676a664a14bf5ae`
- `web/__tests__/fixtures/conversation-activity-runtime.ts`: `45fa9e9842d4ffc026ed3ff0f0659d21c9f0ecba`
- `web/__tests__/use-conversation-activity.test.tsx`: `e94f337fe02050fba07c8a4b473393d9eda10df7`
- `web/components/chat/ChatInterface.tsx`: `d178847e684592278c6c0b32479fe1a9ac0e30d8`
- `web/components/chat/useConversationActivity.ts`: `1a29cc3e7a61fc3c84acca1046d2aed99578b584`
- `web/e2e/conversation-activity-ui.spec.ts`: `ca72733c2fbeeda2d15f8dbf7c42e7c49dadf431`
