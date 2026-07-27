# Guest Grounded Discovery: Meter the Cost, Gate the Value

**Status:** FOUNDER-DIRECTED — direction approved 2026-07-27; implementation not started.
**Owning issue:** [#244](https://github.com/lagarcess/argus/issues/244), consuming the guest surface from #279.
**Scope class:** Small backend slice. One allowance row, one identity key, one spend ceiling, two truth fixes. No new mechanism.
**Base:** `codex/private-alpha-next` at `ea2b3f35` or later.

---

## 1. Why this exists

Guest mode is the acquisition funnel. Discovery is the most persuasive thing
Argus does for a stranger: five real, resolver-verified, source-backed names in
seconds. Withhold it and guest mode demonstrates a chat box.

It is also the only guest action that spends **third-party money per use on an
unauthenticated visitor**. Messages and simulations cost compute; a discovery
ask costs a metered search on top.

Founder decision 2026-07-27: **"registered users only" in the grounded
discovery design §1 is superseded.** Argus is for everyone, gated at points of
high value.

## 2. The organising idea: metering is not gating

This is the rule that keeps discovery from cannibalising the existing funnel.

| Instrument | Question it answers | What happens at the limit |
| --- | --- | --- |
| **Conversion gate** | Is this worth an account? | Sign-in wall, action captured and resumed |
| **Meter** | Can we afford this right now? | Honest "not right now", conversation continues |

Every existing guest limit is a **gate**: `message_limit`,
`second_simulation`, `save_decision`, `new_conversation`, `keep_history`. Each
fires at a moment where the user has felt value and is reaching for more.

**Discovery's allowance is a meter, not a gate.** Exhausting it does not ask
anyone to sign up. It says the search budget is spent, the conversation keeps
going, and the user still walks toward the gates that already exist. That is
precisely why it cannot cannibalise them.

This is not invented. Perplexity runs the same split: unlimited cheap searches,
**5 Pro Searches per day** metered — the expensive operation is metered while
the signup ask lives elsewhere. ChatGPT's account-free tier does the same, with
guest access itself conditioned on "region, traffic, and abuse controls".

### Where conversion happens, unchanged

```text
guest asks a discovery question   -> metered, silent, no gate
  -> full result: rows, reasons, sources
  -> taps a candidate             -> no gate
  -> confirmation card
  -> first run free               -> the aha: a real result with numbers
  -> second distinct run          -> GATE (second_simulation), unchanged
```

Discovery is an **amplifier for the existing gate**: it manufactures more
distinct things a guest wants to run, driving them to `second_simulation`
faster and with higher intent. Walling the tap would convert on a list of names
before any result had been seen — earlier, on weaker proof, and cannibalising
the gate that works. The research is unambiguous: gate after the aha moment,
never before, and ungated entry produces roughly 3x more people who start.

**No new `GuestConversionReason`. No new wall. No new copy.**

## 3. The core issue: we meter identities, and identities are free

Every allowance keys on `user_id`. For a registered user that is sound — a
`user_id` costs an email and a signup. For a guest it costs nothing:

- a guest workspace lives **10 minutes**, fixed from creation
  (`supabase_guest_accounts`);
- on expiry the next bootstrap silently issues a **new workspace with a new
  `user_id`** (`renewed_after_expiry: true`);
- a new `user_id` means **every per-user counter resets**.

Guest creation is CAPTCHA-gated and IP-limited to 5 per 10 minutes
(`AUTH_GUEST_ATTEMPT_LIMIT`), so the ceiling today is roughly five fresh
allowances per ten minutes per IP. At one search per workspace that is **30
searches an hour — three times the registered limit of 10.** The guest
allowance would be weaker than the paid one.

The failure is not the number. It is that the allowance was keyed to a
**session artifact that renews on a timer** rather than to the visitor.

### The wrong goal, and the right one

Making identity unforgeable is not achievable. IPs rotate, incognito is free,
CAPTCHAs get solved. Chasing it produces fingerprinting complexity that still
loses. ChatGPT's answer — a persistent device identifier that survives cookie
clearing — raises the cost of a fresh identity but does not eliminate it.

**The goal is bounded cost, not unforgeable identity.** Two instruments, aimed
at two different people:

| Threat | Instrument |
| --- | --- |
| The curious user who notices refreshing gives them more | Allowance keyed to the visitor, not the session |
| The adversary who rotates IPs and solves CAPTCHAs | A global daily ceiling on discovery spend |

The first is the realistic case and the one that matters most. The second
cannot be prevented, only bounded — which is exactly what provider-level spend
caps exist for, and the standard practice for protecting a free tier backed by
a paid API.

## 4. The design

Three changes, all on machinery that already exists.

### 4.1 Add discovery to the guest allowance table

`usage_limits.allowance_windows()` already resolves per-account-class limits,
and guests already have a `guest_session` period spanning their fixed expiry.
`_GUEST_ALLOWANCES` covers messages (10), simulations (1), and feedback (5).
**Discovery is the only metered resource missing.** Add
`GUEST_DISCOVERY_ALLOWANCE` beside the others so it is tuned where the rest are,
and make `discovery_evidence.discovery_usage_limits()` consult account class
instead of returning registered limits unconditionally.

### 4.2 Key the guest discovery counter to the visitor, not the workspace

The guest allowance must survive workspace renewal. Key it on the same client
identity `_enforce_guest_attempt_limit` already derives (`_client_identity`,
which prefers the first `x-forwarded-for` hop), rather than on `user_id`.

Renewal then stops handing out a fresh budget, which closes the casual path
completely: waiting out the timer or refreshing returns nothing new. This is the
change that makes the slice actually deliver "not exploitable" for the realistic
user.

Registered users are untouched — they stay keyed on `user_id`, which is what a
durable account identity is for.

### 4.3 Bound total discovery spend with a global daily ceiling

A per-visitor limit shapes normal use. It cannot bound an adversary who rotates
identity. A **global daily cap on attempted discovery searches** can, and it is
the only control that makes worst-case cost a number you chose rather than a
number someone else picks.

- Counted on the same `cost_ledger_entries` / usage machinery already recording
  every attempted search.
- When exhausted, discovery returns the existing typed
  `discovery_limit_reached` recovery with **zero provider calls** — no new
  failure mode, no new copy.
- Applies to guests and registered users alike, because an adversary with an
  email is still an adversary.
- Set generously enough that no honest day reaches it; it is a circuit breaker,
  not a budget.

### Why this is durable rather than a v1

- **Policy is data.** A limit is a table entry, not a branch. A future account
  tier is another row.
- **One counter, one settlement path, one recovery message** shared by both
  classes.
- **No new table, no migration, no parallel guest code.**
- **Backend-owned.** A frontend bypass obtains nothing.
- **Two independent bounds.** Per-visitor shapes behavior; global caps cost.
  Neither depends on the other holding.

## 5. Behavior

- A guest discovery ask within allowance behaves **exactly** as it does for a
  registered user: one bounded search, resolver-validated candidates, rows,
  reasons, sources line.
- **The result is shown in full.** No blur, no teaser, no partial list — a
  redacted result destroys the proof the funnel depends on.
- Beyond allowance, or beyond the global ceiling, the turn returns
  `discovery_limit_reached` with zero provider calls. Honest, not a wall.
- Registered allowances (`ARGUS_DISCOVERY_HOURLY_LIMIT` /
  `ARGUS_DISCOVERY_DAILY_LIMIT`) are unchanged.
- The global kill switch (`ARGUS_GROUNDED_DISCOVERY_ENABLED`) still precedes
  everything.

### The numbers

**Three grounded searches per visitor per day.** One proves the value, but a
single search is a poor sample of a product whose whole promise is *asking
Argus things*. Three lets a guest try a category, a peer question, and a
second idea after seeing a result — which is when discovery does its funnel
work. It remains well under the registered allowance of 10/hour, so it never
inverts the incentive.

**Global ceiling:** a daily attempted-search cap set from measured normal
volume once the surface has real traffic. Until then, a deliberately
conservative starting value, recorded in config and raised on evidence.

Both are config, not code. Raising a limit is cheap and reversible; lowering one
after testers have seen it is not.

## 6. Capability truth fix (in scope, not a gate)

`can_use_grounded_discovery=False` is a false statement: discovery works for
both classes today. Its only consumer is a guest command-palette notice
claiming discovery "isn't available yet". Set it **`True` for both**, so the
contract matches observable behavior and the false notice stops rendering.

**A correction, not a mechanism.** Per-class on/off gating is deliberately not
built: the global flag and the per-account allowance cover every real need,
discovery has no UI affordance to hide (it is triggered by what the user says
and classified by the interpreter), and with discovery rolling out to everyone
both switch positions would be identical. It would be a control with no
consumer.

## 7. Dropped-candidate copy fix (in scope)

A dropped candidate lands in `unverified_names` and may be voiced as
*"mentioned in sources but not verifiable as tradable."* That became false in
`ea2b3f35` for one case: a Grayscale Bitcoin trust **is** tradable — it was
dropped because Argus could not confirm it was the asset the user meant.

| Why it was dropped | Honest statement |
| --- | --- |
| Symbol resolved to nothing | not verifiable as tradable |
| Resolved asset did not match the named entity | could not confirm this is the asset you meant |

Validation already knows which branch rejected each candidate, so carry the
reason (`unresolved` / `uncorroborated`) alongside the name and let voicing
state the matching fact. Voicing keeps consuming typed facts only.

A wrong explanation for a correct decision is the same class of defect as a
wrong candidate.

## 8. Non-goals

- No new `GuestConversionReason`, tap wall, or discovery paywall UI.
- No blurred, teased, or partial candidate lists.
- No per-class capability gating (§6).
- No device fingerprinting. It raises the cost of a fresh identity without
  bounding it, and the global ceiling bounds cost directly.
- No change to registered quotas, the discovery pipeline, or the search boundary.
- No new admission control — CAPTCHA and the IP limiter already exist.
- No cost dashboard or per-turn cost equation. The ledger has known gaps and
  must be trustworthy before numbers derived from it are.
- No Render, flag, or promotion work.

## 9. Recorded, not fixed here

- **Messages and simulations have the same identity hole.** Both key on
  `user_id`, so both reset on workspace renewal. Real, and larger than this
  slice; log against the guest lane rather than folding in.
- **Guest expiry is fixed at 10 minutes from creation, not sliding.** A guest
  reading a backtest result can lose the workspace mid-thought. Guest-lane
  territory.
- **`discovery_allowance_available` fails closed into
  `discovery_limit_reached`**, telling a user they are out of searches when the
  counter merely could not be read. Pre-existing; recorded on #244.

## 10. Edge cases the implementation must handle

1. **Guest converts mid-conversation.** The workspace hands off from
   `source_user_id` to `destination_user_id` — different accounts. Guest usage
   stays on the guest identity, the new account resolves registered limits, and
   nothing double-counts.
2. **Guest workspace expires mid-turn.** Settlement is already best-effort and
   must not fail the turn.
3. **Concurrent asks.** The counter clamps at the ceiling and the attempt is
   logged, exactly as the registered path already does.
4. **Client identity unavailable** (missing `x-forwarded-for`). Fail closed to
   the most restrictive bucket rather than issuing an unmetered allowance.

## 11. Acceptance

1. A guest discovery ask within allowance returns a full, resolver-validated
   result identical to the registered experience.
2. A guest ask beyond allowance makes **zero** provider calls and returns
   `discovery_limit_reached`.
3. **Renewing a guest workspace does not restore the discovery allowance.**
4. Exceeding the global daily ceiling stops discovery for everyone with zero
   provider calls and the same honest recovery.
5. Tapping a candidate as a guest raises no wall and reaches a confirmation card.
6. A guest's first run stays free; the second distinct run converts through the
   existing `second_simulation` reason, unchanged.
7. Enforcement is backend-side; a frontend-only bypass obtains no search.
8. Registered discovery behavior is byte-identical to today.
9. `can_use_grounded_discovery` reports `True` for both classes and the guest
   command-palette notice no longer appears.
10. A candidate dropped for failing corroboration is described as one Argus
    could not confirm, never as one that is not tradable.

## 12. Documentation

- Grounded discovery design §1: already marked superseded; point it here.
- `docs/DATA_MODEL.md`: `discovery_searches` resolves per account class, and the
  guest counter keys on client identity.
- `docs/API_CONTRACT.md`: the capability's corrected value.
- Issue #244 register: replace the guest line with this slice.
