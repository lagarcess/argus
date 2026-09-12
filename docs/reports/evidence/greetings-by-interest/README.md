# Greetings gated by demonstrated interest: browser evidence

Captured at code commit `a70a5351` on `claude/argus-greetings-teach-method-1ae4c8`
(integration base `b0a7cf08`), headless Chromium, light theme, reduced motion.

| Shot | Who | Backend `interest` | Line shown |
| --- | --- | --- | --- |
| `registered-weekend-*` | registered, no history | `{"markets": false}` | `day_d`, neutral |
| `fan-weekend-*` | registered, owns one completed run | `{"markets": true}` | `session_closed_weekend_a` |
| `guest-weekend-*` | guest | `{"markets": true}` | `day_d`, neutral |

Each shot exists in `en` and `es-419` at 390 and 1280 wide. The `.txt` files
record the rendered greeting, the key it was checked against and the interest
the backend actually served.

**What was real.** The backend ran in memory mode with mock auth and synthetic
market data, no provider keys. `interest` came from `GET /market/session`
unmodified. The fan's history is a real completed AAPL buy-and-hold run created
through `POST /api/v1/backtests/run` before the fan and guest shots.

**What was faked, in the browser only.** The session phase was rewritten to
`closed_weekend` (the calendar needs provider keys), and the browser clock was
fixed to Saturday 2026-10-03 12:00 New York, a day whose rotation lands a market
fan on the weekend line. The guest is the real `/me` response re-marked as a
guest, with the same backend interest as the fan, so the shot shows that a
guest's own runs never earn market flavor. None of this is in shipped code.
