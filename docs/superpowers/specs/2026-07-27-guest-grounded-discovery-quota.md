# Guest Grounded Discovery: Meter the Ask, Don't Gate the Tap

**Status:** FOUNDER-DIRECTED — direction approved 2026-07-27; implementation not started.
**Owning issue:** [#244](https://github.com/lagarcess/argus/issues/244) (grounded discovery), consuming the guest surface from #279.
**Scope class:** Small backend slice. One allowance, no new conversion reason, no new UI.

---

## 1. Why now

The guest experience landed (#279) after the grounded discovery design was
written. Two things changed:

- **"Registered users only" is stale.** The grounded discovery design §1 records
  guest discovery as needing a separate founder decision. That decision is made:
  Argus is for everyone, and the guest surface is an acquisition funnel that
  shows value and converts at points of high value.
- **Discovery has no guest gate of any kind.** Verified against integration
  `94296ab8`: `src/argus/agent_runtime/discovery/` and
  `src/argus/domain/discovery_search/` contain no guest handling, and
  `discovery_evidence.py` does not distinguish account kind. Guests reach the
  same chat runtime, so a guest discovery question runs a real metered search.

Not a live exposure today — Render carries neither the flag nor the provider
key, so discovery is inert for everyone. It becomes real the moment the key is
set for the canary. Render/promotion configuration is owned elsewhere and is not
this slice's concern; the runtime gap is.

## 2. The decision

**Meter the ask. Do not gate the tap.**

For a backtest, cost and value coincide — you run it, you see it. For discovery,
Argus pays the provider on the **ask**, before knowing whether the guest cares.
That asymmetry is why one control cannot do both jobs:

| Moment | Instrument | Visible to the guest? |
| --- | --- | --- |
| Guest asks a discovery question | Per-session allowance | No — silent, like message metering |
| Allowance exhausted | Existing `discovery_limit_reached` recovery | Yes — honest copy, zero provider cost |
| Guest taps a candidate | **Nothing new** | — flows into the ordinary lifecycle |

### Why the tap must not be gated

Every existing guest conversion reason — `second_simulation`, `message_limit`,
`save_decision`, `new_conversation`, `keep_history` — fires after real value has
been *demonstrated*. `isExactGuestRunReplay` shows the same care: re-running an
identical backtest stays free, and only a genuinely new simulation converts.

A guest's "aha" is a backtest result with real numbers. Walling the discovery tap
would convert them on a list of names, before they have ever seen a result —
gating earlier, on weaker proof, and cannibalizing `second_simulation`.

Letting the tap through makes discovery a conversion **amplifier**: it
manufactures more distinct things the guest wants to run, which drives them into
the existing gate faster and with higher intent. Guest journey:

```text
discovery ask (metered, silent)
  -> full result: rows, reasons, sources line
  -> tap a candidate (no gate)
  -> confirmation card
  -> first run free
  -> real result with numbers        <- the aha
  -> second distinct run converts    <- existing second_simulation gate
```

No new conversion reason, no new wall, no new copy.

## 3. Behavior

- A guest session carries a small grounded-discovery allowance. The exact number
  is founder-owned (§6); the shape is per session, not per hour/day, because a
  guest session is the unit the funnel cares about.
- Within allowance, a guest discovery turn behaves exactly as it does for a
  registered user: one bounded search, resolver-validated candidates, rows,
  reasons, and the sources line.
- **The result is shown in full.** No blur, no teaser, no redacted candidate
  list. A partial result destroys the proof the funnel depends on.
- Beyond allowance, the turn returns the existing typed
  `discovery_limit_reached` recovery with **zero provider calls**. It is honest
  copy, not a conversion wall.
- Registered-user allowances (`ARGUS_DISCOVERY_HOURLY_LIMIT`,
  `ARGUS_DISCOVERY_DAILY_LIMIT`) are unchanged.

## 4. Metering identity

The allowance must be counted on whatever identity the guest lane already uses
for its own limits. **Do not invent a second scheme.**

A fresh guest session otherwise buys another search, which is the same
session-recycling problem the guest lane already had to solve for messages. This
slice inherits that answer rather than re-deriving it — and if the guest lane's
identity turns out to be weaker than this cost warrants, that is a finding to
raise, not to paper over with a frontend check.

Backend owns the count. Frontend gating alone is bypassable, and this one costs
money.

## 5. Non-goals

- No new `GuestConversionReason`, no tap wall, no discovery-specific paywall UI.
- No blurred, teased, or partial candidate lists.
- No change to registered-user quotas or to the discovery pipeline itself.
- No cost dashboard, no per-turn cost equation, no ledger rework. Deliberately
  deferred; the ledger has known gaps (the discovery row is skipped when no
  Supabase gateway is present, and market-data provider coverage is unaudited)
  and those must be resolved before any cost number is trustworthy.
- No Render, flag, or promotion work — owned at promotion time.

## 6. Open decision

- **The allowance number.** One search per guest session is the smallest thing
  that shows the value; two allows a second, better-aimed question after the
  first result teaches them what Argus can do. Recommend starting at **one** and
  raising it on evidence, since raising a limit is reversible and cheap while
  lowering one after testers see it is not.

## 7. Acceptance

1. A guest discovery ask within allowance returns a full, resolver-validated
   result identical to the registered-user experience.
2. A guest discovery ask beyond allowance makes **zero** provider calls and
   returns the existing `discovery_limit_reached` recovery.
3. Tapping a candidate as a guest raises no wall and reaches a confirmation card.
4. A guest's first run stays free; the second distinct run converts through the
   existing `second_simulation` reason, unchanged.
5. The allowance is enforced backend-side and counted on the guest lane's
   existing identity; a frontend-only bypass attempt does not obtain a search.
6. Registered-user discovery behavior is byte-identical to today.

## 8. Documentation

- Grounded discovery design §1: mark "Registered users only" superseded by this
  slice, with the date and the owning decision.
- `docs/DATA_MODEL.md`: note the guest allowance alongside the existing
  `discovery_searches` resource.
- Issue #244 pending register: replace the guest line with this slice.
