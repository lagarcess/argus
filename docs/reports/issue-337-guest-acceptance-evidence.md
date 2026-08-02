# Issue #337 Guest Acceptance Evidence

Date: 2026-08-02

Status: **PASS on exact candidate head**

Candidate SHA: `0e07299fe93fd5e9af3148dd89a970f6b228bbf5`

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

## Review correction: prove the recovered path

The first implementation treated any later active confirmation as recovery.
That could hide an earlier clarification when the confirmation belonged to an
unrelated idea. The corrected projection uses only existing backend-owned
transcript metadata:

- the clarification supplies `pending_strategy.strategy` and its
  `requested_field`;
- the active confirmation supplies `confirmation_payload.strategy`;
- the marker clears only when the confirmation fills the requested field and
  typed strategy facts or the source-result artifact prove continuity;
- a relative date fact may match its backend-canonicalized `{start, end}` form
  only when both sides preserve the same raw date text and requested date range,
  and the confirmation's effective range agrees with the rendered strategy;
- missing or conflicting relationship evidence keeps the marker visible.

Focused regression coverage includes an AAPL clarification followed by an
unrelated MSFT confirmation, an active confirmation with no typed path, and a
confirmation that still lacks the requested field. It also covers equivalent,
unproven, and conflicting relative-date canonicalization paths.

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
4. The pending path carries the relative date “past year” plus its requested
   range; a later active AAPL confirmation carries the same raw and requested
   provenance plus its effective range, proving that its canonical dates
   continue that path.
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
ARGUS_EXPECTED_CANDIDATE_SHA=0e07299fe93fd5e9af3148dd89a970f6b228bbf5 \
  ARGUS_GUEST_QA_APP_PORT=3105 \
  ARGUS_GUEST_QA_API_PORT=8015 \
  bash scripts/qa/run-guest-experience-qa.sh preflight \
  --grep "issue 337 Guest recovery"
```

Result: `1 passed`.

## Sanitized visual evidence

Local evidence pack:

- `temp/qa-evidence-guest/0e07299fe93fd5e9af3148dd89a970f6b228bbf5/authoritative/issue-337-guest-recovered.png`
- `temp/qa-evidence-guest/0e07299fe93fd5e9af3148dd89a970f6b228bbf5/authoritative/issue-337-guest-recovered-reload.png`

SHA-256 before reload:
`a097a27c1c70af6a66d6cd38ae6fa1fa8297721573dade9bd19b80b159a6895a`.

SHA-256 after reload:
`664a7b107e13bf55ee9311c0e52f9c7dd8784af082c522039c92dea74af5e7e7`.

The different framing reflects scroll restoration after reload; both captures
show the same single completed-backtest rail marker and no attention marker.

## Disposition

**Proven fixed on the exact candidate head for the source Guest persona.** The
stale clarification marker clears, the Guest's single legitimate completed-run
marker remains visible, and reload does not regress either result.

This is a seeded durable acceptance replay, not a paid interpreter or market-
data run. That is intentional: #337 changes a frontend render-time projection,
and the replay validates the real Guest/Auth/API/persistence boundary without
spending a provider turn or changing hosted state.
