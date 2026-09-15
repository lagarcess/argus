# Issue #641: bounded saved-transcript reads

## Result

An unanswered-turn check reads from the raw API snapshot's last saved message,
using the existing inclusive anchor. It follows cursors only through new messages.
When only the unchanged anchor returns, it returns the same snapshot and does not
hydrate or apply UI state. A changed suffix is combined with the saved API data
and projected by the existing chat rules, retaining unchanged display objects.

Ordinary activity refreshes retain full-history reconciliation. The 180-second
runtime timeout, account/navigation cancellation, anchors, scroll, and sender
deduplication remain. No API shape, DB/migration, model-facing text, user-facing
copy, render.yaml, or release-contract changes. All tests are provider-free.
#640 remains deferred.

## Request-count proof

Both tabs first load 1,000 saved messages through ten real fixture pages each.
The sender then saves a user message and the observer loads it from an idle
activity update. The test holds the turn across two idle checks, then saves the
assistant reply without another activity/focus event.

| Observer phase | Before | After |
| --- | --- | --- |
| Two unchanged checks | 22 requests / 2,002 messages | 2 requests / 2 messages |
| Reply arrives | 11 requests / 1,002 messages | 1 request / 2 messages |

The extra anchor returned per check is deliberate: an in-place update to that
saved message is still detected. A separate 205-message suffix test proves cursor
pagination never returns to old history. A runtime test counts zero applications
for unchanged responses. A canonical projection test verifies new replies update
existing retry actions without reconstructing rules in the loader.

[Red browser log](browser-red.txt), [green browser log](browser-green.txt),
[red unit log](unit-red.txt), [green unit log](unit-green.txt).

| Locale | Before | After |
| --- | --- | --- |
| English | [frame](red/641-long-conversation-en.png) | [frame](green/641-long-conversation-en.png) |
| Spanish | [frame](red/641-long-conversation-es-419.png) | [frame](green/641-long-conversation-es-419.png) |

Frames intentionally show the older message anchor. Tests assert the reply exists
once, the URL anchor and scroll offset stay unchanged, the sender does not reread
after send admission, and observer polling stops after the reply. The sender's
existing pre-send transport-recovery snapshot remains unchanged and is excluded
from the pending-reply interval.

## Verification and provenance

- Integration base: `538aec3a9947caf8eb290a1f87551a2212496d44` after #635 landed as
  `0714aafa88f9841ee1c27a29f048970a3e315b8f`.
- Red: runtime from integration, at spec head
  `ecc02868ad4186ad68bd4cea357fe55b4d0b3836`, with new tests and a test-only page
  loader injection seam. Both browser languages fail on the request counts.
- Green capture: implementation head `11a12abdcd53b21b5fb6b221875a1a33156d9fda`.
- All **21 browser cases pass**, comprising the prior 19 accepted cases plus two
  long-history cases. Four previously established baseline cases remain excluded
  exactly as documented in [#598 evidence](../issue-598/README.md).
- **51 focused unit cases**, **2,019 frontend tests**, production build, lint
  (zero errors, eight existing warnings), and [modularity](modularity.txt) pass.
- Local free Python harness: 233 pass; two tests and trajectory-module collection
  cannot import the installed SciPy native extension (`__thread_bss` loader
  error). No backend code changed. Hosted backend CI is required before delivery.
- Final-head revalidation and Codex outcome will be recorded in the terminal PR
  audit after the review loop finishes. This file is acceptance evidence, not a
  terminal readiness claim.

```sh
bun test --cwd web __tests__
PLAYWRIGHT_PORT=3198 bun run --cwd web test:e2e conversation-activity-ui.spec.ts conversation-transcript-freshness.spec.ts --grep-invert 'durable backtest stays|coarse pointer|resolved clarification'
```
