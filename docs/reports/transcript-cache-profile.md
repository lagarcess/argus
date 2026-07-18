# Transcript Cache p50/p95 Measurement Protocol (#252)

Status: locally executable protocol, defined and run in the Wave 0 laboratory
branch. These are **local bun-runtime numbers on the development machine**;
the issue's browser switching/scroll/reload/logout EN/ES profile with cold/warm
p50/p95 on a deployed candidate remains an external gate.

## Protocol definition

- **Fixture**: 8 conversations, each a 30-message transcript (~representative
  alpha session length; ~80-character lines, byte-estimated by the cache).
- **Runtime**: bun test runtime on the local development machine
  (`web/__tests__/chat-transcript-cache-profile.test.ts`). No network; the
  loader is an immediately-resolving async stand-in, so cold numbers measure
  the cache/controller path, not provider latency.
- **Warm** sample: a fresh-cache revisit inside the 60s freshness window
  (`navigate()` resolves synchronously from cache; loader must not run).
- **Cold** sample: a cache-miss navigation (authenticated-state cleared each
  round-robin lap) through the async loader path.
- **Sample size**: 50 navigations per scenario; p50/p95 over per-navigation
  wall time (`performance.now()` from navigate() to the ready state).
- **Budgets asserted in the test**: warm p95 < 5 ms with zero loader calls;
  cold p95 < 25 ms.

## Recorded run (this branch)

Command:

```bash
cd web && bun test __tests__/chat-transcript-cache-profile.test.ts
```

Recorded run (2026-07-18, local dev machine, bun runtime; the
`transcript-cache-profile {...}` log line carries any run's exact values):

| Scenario | p50 | p95 | Loader calls |
| --- | ---: | ---: | ---: |
| Warm fresh revisit | 0.0006 ms | 0.0065 ms (budget < 5 ms) | 0 (asserted) |
| Cold miss | 0.0138 ms | 0.0588 ms (budget < 25 ms) | one per miss |

The suite runs in every `bun test __tests__` invocation, so the budgets are
regression-guarded, and the printed profile line gives the exact numbers for
any specific run.
