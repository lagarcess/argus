# Guest Grounded Discovery: One Allowance Model, Two Account Classes

**Status:** FOUNDER-DIRECTED — direction approved 2026-07-27; implementation not started.
**Owning issue:** [#244](https://github.com/lagarcess/argus/issues/244) (grounded discovery), consuming the guest surface from #279.
**Scope class:** Small backend slice. One allowance row, one capability truth fix, no new mechanism.
**Base:** `codex/private-alpha-next` at `ea2b3f35` or later.

---

## 1. Why this exists

Guest mode is the acquisition funnel. Discovery is the most persuasive thing
Argus does for a stranger: five real, resolver-verified, source-backed names in
seconds. Withhold it and guest mode demonstrates a chat box.

It is also the only guest action that spends **third-party money per use on an
unauthenticated visitor**. Messages and simulations cost compute; a discovery
ask costs a metered search on top. So the question was never whether guests
should discover — it is how to show them the best thing Argus does without
opening a faucet.

Founder decision 2026-07-27: **"registered users only" in the grounded
discovery design §1 is superseded.** Argus is for everyone, gated at points of
high value.

## 2. Current state, verified against `ea2b3f35`

Read this before designing anything; four of these findings shrink the work.

- **Guests are real users.** `GuestWorkspace` carries a `user_id`, so every
  per-user mechanism already applies to them. No parallel identity.
- **A guest allowance model already exists.** `usage_limits.allowance_windows()`
  resolves per-account-class limits, and guests already have a `guest_session`
  period spanning their fixed expiry. `_GUEST_ALLOWANCES` currently covers
  messages (10), simulations (1), and feedback (5).
- **Discovery is the only metered resource missing from that table.**
  `discovery_evidence.discovery_usage_limits()` returns registered
  hour/day limits unconditionally and never consults account class.
- **A guest workspace lives 10 minutes** (`supabase_guest_accounts`), and guest
  creation is IP-rate-limited to 5 attempts per 10 minutes
  (`AUTH_GUEST_ATTEMPT_LIMIT`, `_AUTH_ATTEMPT_WINDOW_SECONDS`).
- **`can_use_grounded_discovery` is dead and wrong.** Declared on
  `AccountCapabilities`, set `False` for *both* guest and registered, and never
  read by the discovery runtime — discovery runs regardless. Its only consumer
  is a guest command-palette notice claiming discovery "isn't available yet",
  which is false today.

## 3. The design

**Do not build guest quota. Add discovery to the allowance model that already
distinguishes account classes.**

Two layers, both already in place:

| Layer | Mechanism | Change needed |
| --- | --- | --- |
| **Allowance** — how many searches an account may make | `discovery_searches` usage counter, limits resolved by `allowance_windows()` | Add one `_GUEST_ALLOWANCES` row; make discovery consult account class |
| **Admission** — how cheaply a new guest identity is minted | IP limiter on `POST /auth/guest` | **None.** Already exists; do not duplicate |

### Why this is durable rather than a v1

- **Policy becomes data.** A limit is a table entry, not a branch. A future
  account tier is another row, not another code path.
- **One counter, one settlement path, one recovery message.** Guests and
  registered users share `discovery_searches`, so accounting, reconciliation,
  and the honest `discovery_limit_reached` recovery are identical for both.
- **No new table, no migration, no parallel guest code.**
- **Backend-owned.** A frontend bypass obtains nothing.

### Why per-guest is inherently per-session

Each guest workspace mints a **new `user_id`**, so a per-user counter resets
when the workspace does. The allowance is therefore per-workspace *by
construction* — no new period type, no lifetime bookkeeping. The `guest_session`
window already spans the account's fixed expiry.

This also names the real bound honestly: **what limits a determined visitor is
the IP limiter on guest creation, not the per-account allowance.** The allowance
shapes the funnel; admission control bounds abuse. Conflating them would lead to
over-building the wrong layer.

### The tap stays ungated

Settled 2026-07-27 and unchanged here. Discovery feeds the **existing**
`second_simulation` conversion moment rather than competing with it:

```text
discovery ask (metered, silent)
  -> full result: rows, reasons, sources
  -> tap a candidate (no gate)
  -> confirmation card
  -> first run free
  -> a real result with numbers      <- the aha
  -> second distinct run converts    <- existing gate, unchanged
```

Walling the tap would convert a guest on a list of names before they had ever
seen a result — earlier, on weaker proof, cannibalising `second_simulation`. No
new `GuestConversionReason`, no new wall, no new copy.

## 4. Behavior

- A guest discovery ask within allowance behaves **exactly** as it does for a
  registered user: one bounded search, resolver-validated candidates, rows,
  reasons, sources line.
- **The result is shown in full.** No blur, no teaser, no partial list. A
  redacted result destroys the proof the funnel depends on.
- Beyond allowance, the turn returns the existing typed
  `discovery_limit_reached` recovery with **zero provider calls**. Honest copy,
  not a conversion wall.
- Registered allowances (`ARGUS_DISCOVERY_HOURLY_LIMIT` /
  `ARGUS_DISCOVERY_DAILY_LIMIT`) are unchanged.
- The global kill switch (`ARGUS_GROUNDED_DISCOVERY_ENABLED`) still precedes
  everything and is unchanged.

### The allowance number

**One search per guest workspace.** A workspace lives 10 minutes; one grounded
search is enough to prove the value, and a second in that window adds cost
without adding persuasion. Raising a limit is cheap and reversible; lowering one
after testers have seen it is not.

Recorded as `GUEST_DISCOVERY_ALLOWANCE` beside the existing guest constants so
it is tuned in the same place as messages and simulations.

## 5. Capability truth fix (in scope, not a gate)

`can_use_grounded_discovery=False` is a false statement: discovery works for
both classes today. Set it **`True` for both**, which:

- makes the contract match observable behavior;
- removes the guest command-palette notice that wrongly says discovery is
  unavailable.

**This is a correction, not a mechanism.** Per-class on/off gating is
deliberately *not* built: the global flag and the per-account allowance already
cover every real need, discovery has no UI affordance to hide (it is triggered
by what the user says, classified by the interpreter), and with discovery
rolling out to everyone both switch positions would be identical. Building it
would add a control with no consumer.

## 6. Dropped-candidate copy is inaccurate (in scope)

When a candidate is dropped it lands in `unverified_names`, and the voicing call
may mention it as *"mentioned in sources but not verifiable as tradable."*

That sentence became false for one case in `ea2b3f35`. A Grayscale Bitcoin
trust **is** tradable — it was dropped because we could not confirm it was the
asset the user meant, which is a different statement. The copy conflates two
distinct reasons:

| Why it was dropped | Honest statement |
| --- | --- |
| Symbol resolved to nothing | not verifiable as tradable |
| Resolved asset did not correspond to the named entity | could not confirm this is the asset you meant |

Voicing consumes only typed facts, so the fix is to carry the drop **reason**
alongside the name rather than to write per-case prose: validation already knows
which branch rejected each candidate. Two reason codes are enough
(`unresolved`, `uncorroborated`), and the voicing prompt states the matching
fact.

Small, but this product's whole claim is that it does not say things it cannot
support. A wrong explanation for a correct decision is the same class of defect
as a wrong candidate.

## 7. Non-goals

- No new `GuestConversionReason`, tap wall, or discovery paywall UI.
- No blurred, teased, or partial candidate lists.
- No per-class capability gating (§5).
- No change to registered quotas, the discovery pipeline, or the search boundary.
- No new admission control — the IP limiter is sufficient and already exists.
- No cost dashboard or per-turn cost equation. The ledger has known gaps (the
  discovery row is skipped without a Supabase gateway; market-data coverage is
  unaudited) and must be trusted before any number derived from it is.
- No Render, flag, or promotion work.

## 8. Edge cases the implementation must handle

1. **Allowance read fails.** `discovery_allowance_available` fails closed today,
   which is right for spend — but it currently maps to
   `discovery_limit_reached`, telling the user they are out of searches when the
   counter simply could not be read. That is a false statement to the user and
   must be distinguished. *(Pre-existing; recorded on #244.)*
2. **Guest expires mid-turn.** A workspace can lapse between the pre-turn
   allowance read and post-turn settlement. Settlement is already best-effort
   and must not fail the turn.
3. **Guest converts mid-conversation.** After claiming a workspace the account
   becomes registered; the next discovery ask resolves registered limits. Prior
   guest usage does not transfer, and must not be double-counted.
4. **Concurrent asks in one workspace.** The same race the registered path
   already handles: the counter clamps at the ceiling and the attempt is logged.

## 9. Acceptance

1. A guest discovery ask within allowance returns a full, resolver-validated
   result identical to the registered experience.
2. A guest ask beyond allowance makes **zero** provider calls and returns
   `discovery_limit_reached`.
3. Tapping a candidate as a guest raises no wall and reaches a confirmation card.
4. A guest's first run stays free; the second distinct run converts through the
   existing `second_simulation` reason, unchanged.
5. The allowance is enforced backend-side; a frontend-only bypass obtains no
   search.
6. Registered discovery behavior is byte-identical to today.
7. `can_use_grounded_discovery` reports `True` for both classes, and the guest
   command-palette notice no longer appears.
8. A candidate dropped for failing corroboration is described as one Argus
   could not confirm, never as one that is not tradable.
9. A fresh guest workspace gets a fresh allowance, and guest creation remains
   bounded only by the existing IP limiter.

## 10. Documentation

- Grounded discovery design §1: already marked superseded; point it here.
- `docs/DATA_MODEL.md`: note `discovery_searches` now resolves per account class.
- `docs/API_CONTRACT.md`: note the capability's corrected value.
- Issue #244 register: replace the guest line with this slice.
