# Issue #337 Guest Acceptance Evidence

Date: 2026-08-02

Status: **PASS on exact candidate head**

Candidate SHA: `220824ba775883f28b138b9cb7d8fdd5c716831e`

Source evidence: G-01/G-02 in
`docs/reports/2026-08-01-current-checkpoint-experience-feedback.md`.

## Acceptance correction

The first #337 browser fixture identified itself as a registered account and
kept the rail visible with two completed-result ticks. That did not represent
the founder-observed Guest session. A Guest has one simulation, so after the
stale clarification tick cleared, the existing two-tick visibility threshold
also hid the legitimate completed-backtest tick.

Red proof reproduced both failures:

- the Guest-shaped deterministic browser replay could not find the activity
  rail when one completed result remained;
- `conversationRailVisible(12, 1)` returned `false`.

The correction retains the 12-message and desktop thresholds and lowers only
the legitimate tick threshold from two to one.

## Exact-head acceptance replay

Mode: local production build, real disposable Supabase Guest Auth, durable
Supabase messages/run/usage, no provider turn, no hosted mutation.

The seeded transcript preserves the evidence shape without inventing runtime
prose:

1. One completed MSFT backtest exists as a durable completed run and result
   message.
2. The long transcript contains the earlier typed clarification, “Which asset
   should I test?”
3. The user supplies `AAPL`.
4. A later active AAPL confirmation resolves the clarification.
5. The page hydrates from the durable API, then reloads and hydrates again.

Observed and asserted before and after reload:

- account kind is `guest`; the screenshot visibly says “Temporary chat” and
  offers “Sign in”;
- the rail is visible with exactly one tick;
- the surviving tick is `Backtest finished — MSFT · Buy and hold`;
- no `Needed attention` tick exists;
- the completed result chart remains present;
- durable state is exactly 12 messages, one completed run, and one Guest
  simulation unit;
- route receipts: zero;
- cost ledger rows: zero;
- browser safety errors: zero;
- hosted writes: zero;
- credential exposure: zero.

Command:

```bash
ARGUS_EXPECTED_CANDIDATE_SHA=220824ba775883f28b138b9cb7d8fdd5c716831e \
  bash scripts/qa/run-guest-experience-qa.sh preflight \
  --grep "issue 337 Guest recovery"
```

Result: `1 passed`.

## Sanitized visual evidence

Local evidence pack:

- `temp/qa-evidence-guest/220824ba775883f28b138b9cb7d8fdd5c716831e/authoritative/issue-337-guest-recovered.png`
- `temp/qa-evidence-guest/220824ba775883f28b138b9cb7d8fdd5c716831e/authoritative/issue-337-guest-recovered-reload.png`

Both files have SHA-256:
`a097a27c1c70af6a66d6cd38ae6fa1fa8297721573dade9bd19b80b159a6895a`.

The identical hashes are expected: reload preserves the same durable transcript
and rail state.

## Disposition

**Proven fixed on the exact candidate head for the source Guest persona.** The
stale clarification marker clears, the Guest's single legitimate completed-run
marker remains visible, and reload does not regress either result.

This is a seeded durable acceptance replay, not a paid interpreter or market-
data run. That is intentional: #337 changes a frontend render-time projection,
and the replay validates the real Guest/Auth/API/persistence boundary without
spending a provider turn or changing hosted state.
