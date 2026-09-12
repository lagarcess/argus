# Greetings gated by demonstrated interest: browser evidence

Captured at code commit `0364c152` on `claude/argus-greetings-teach-method-1ae4c8`
(integration base `b0a7cf08`), headless Chromium, light theme, reduced motion.

**Exact-head revalidation.** Every commit after `0364c152` changes only files
under this directory, so the captured code is the code at the PR head:

```bash
git diff 0364c152 HEAD -- . ':!docs/reports/evidence/greetings-by-interest'
```

prints nothing. Any later code commit invalidates these shots and they are
recaptured.

| Shot | Who | Backend `interest` | Line shown |
| --- | --- | --- | --- |
| `registered-weekend-*` | registered, no history | `{"markets": false}` | `day_d`, neutral |
| `fan-weekend-*` | registered, owns one completed run | `{"markets": true}` | `session_closed_weekend_a` |
| `guest-weekend-*` | guest | not requested | `day_d`, neutral |

Each shot exists in `en` and `es-419` at 390 and 1280 wide. The `.txt` files
record the rendered greeting, the key it was checked against and the interest
the backend served. For the guest it reads `unread`: a guest greeting never
calls `GET /market/session`, because a guest's pool reads neither the session
nor interest and a visitor may have no identity yet.

**What was real.** The backend ran in memory mode with mock auth and synthetic
market data, no provider keys. `interest` came from `GET /market/session`
unmodified. The fan's history is a real completed AAPL buy-and-hold run created
through `POST /api/v1/backtests/run` before the fan and guest shots, so the
guest shots were taken while the same backend user had market interest.

**What was faked, in the browser only.** The session phase was rewritten to
`closed_weekend` (the calendar needs provider keys), and the browser clock was
fixed to Saturday 2026-10-03 12:00 New York, a day whose rotation lands a market
fan on the weekend line. The guest is the real `/me` response re-marked as a
guest. None of this is in shipped code.
