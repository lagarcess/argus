# Discovery continuity and cheap verified rows

Status: PR A landed via #295 at `8f17a45e`; PR B and promotion remain
Parent branch: `codex/private-alpha-next`
Supersedes the open work in `2026-07-27-guest-grounded-discovery-quota.md` §9
and §12, and carries in Slice B from
`2026-07-26-chat-next-moves-live-progress-polish.md` §4. Those are findings logs;
this is the implementation contract.

**Where they disagree, this document is correct.** Three of their claims were
written from symptoms and turned out to be wrong on inspection:

- §12.1 "identity fix appears absent" — identity arrived fine; the cause is the
  incomplete-rule copy path (§5 here).
- §12.5 "no retry affordance exists" — the rail exists; discovery is not on it
  (§4 here).
- §9 "guest expiry is fixed at 10 minutes" — that is the handoff token. The
  workspace lives 7 days by database constraint (§10.1 here).

---

## 1. What this is

Nine items across two PRs. Four are defects with confirmed root causes, two are
new capability, one is infrastructure, one is measurement that needs no code, and
one — language parity — binds every other item.

**Where this lands:** when all nine are done, grounded discovery is
code-complete and promotion is the only work remaining (§14). That is the point
of the scope; do not defer pieces into a follow-up lane.

**PR A — the discovery pass.** One story: discovery answers become actionable
and honest.

| # | Item | Kind | Section |
| --- | --- | --- | --- |
| 1 | Cheap verified rows as the default discovery path | capability | §3 |
| 2 | Retry affordance for failed searches, and stop charging for them | defect | §4 |
| 3 | Incomplete rule reported as an unsupported one | defect | §5 |
| 4 | Answering the pending question routed to change-conflict | defect | §6 |
| 5 | Guest allowance measurement | none — already instrumented | §7 |
| 6 | Offload the blocking provider search | defect | §8 |
| 9 | Language parity — English and Spanish, binds items 1–8 | required | §11 |
| — | CI gate globs `tests/*_postgres.py` | gate | §12.2 |

Items 2, 3, 4 and 6 are independent and can land in any order. Item 1 is the
largest and should land last, because item 3 changes copy on a path item 1
exercises heavily. Item 4 gets its own commit — it is the interpret/edit spine,
its size is unknown until the diagnostic runs, and it must be droppable without
holding the rest.

**PR B — guest identity and lifetime.** One story: the guest workspace's
identity and lifetime are correct.

| # | Item | Kind | Section |
| --- | --- | --- | --- |
| 7 | Slice B — honest live progress lines | capability | §9 |
| 8 | Guest identity and lifetime | defect | §10 |

Item 7 requires item 6, so it cannot precede PR A. It may ride PR A instead if
the event-channel infrastructure lands small; that is a judgment call at build
time, not a decision to make now.

**Why two PRs and not one.** Item 8 re-keys the allowance consumed on *every*
guest message, and item 7 adds a new mechanism to the runtime streaming loop.
Bundled with a discovery rewrite, a regression in either reads as a discovery
bug, and one contentious piece holds four ready ones hostage. Founder informed
2026-07-27; the container is the founder's call and the spec is written to work
either way.

---

## 2. Decisions already made — do not relitigate

- Argus is **free**. There is no paid tier. The only distinction is guest
  (rotating anonymous workspace) versus registered (durable account).
- Guests keep **2** grounded searches, metered per visitor. The visitor metering
  and global ceiling shipped in PR #291 and stay exactly as they are.
- A guest discovery ask is answered by the **cheap verified path by default**. A
  grounded search fires when the interpreter judges the answer needs facts newer
  than the model knows, **or** when the user asks for one explicitly.
- An ungrounded answer must be visibly ungrounded. A remembered shortlist
  presented as current is forbidden by the grounded discovery design §10, and
  today's behavior violates it.
- No regex, no keyword lists, no hardcoded language gates before LLM
  interpretation. The currency judgment is a field on the interpreter's typed
  output, not a phrase match.
- **English and Spanish parity is a build requirement, not a follow-up.** No item
  in this spec is done in one language (§11). Founder decision 2026-07-27, moved
  in from the closure gates so that promotion is the only work left when these
  PRs land.

---

## 3. Item 1 — cheap verified rows

### 3.1 The problem

Ask "which pharma stocks could I test?" today and you get JNJ, PFE and MRK as
prose from model memory: no search, no sources, no date, and nothing tappable.
The turn was never classified `asset_discovery`, so it never reached the
discovery composer and the meter never fired.

Two failures in one. The answer is unactionable, and it is indistinguishable
from a researched one — which is what makes grounded discovery worth its cost.

### 3.2 The insight this is built on

What moves a guest toward value is a **tappable verified row**, not a search.
"Which pharma stocks could I test?" was answered as well by the brain as by a
search — currency bought nothing. "Which stocks IPO'd in the last two months?"
cannot be answered without one.

So currency is the axis, not account class.

### 3.3 Shape

| Path | When | Cost | Output |
| --- | --- | --- | --- |
| Cheap verified | default | one LLM call | rows, no sources, unsourced marker, "Search for current results" row |
| Grounded search | interpreter says currency is needed, or user asks | one metered search | rows + sources + freshness date |

Both paths emit **the same sidecar contract**. That is the point: continuity is
inherited, not reimplemented.

### 3.4 Interpreter change

Add one field to the `asset_discovery` typed request:

```
needs_current_facts: bool
```

True when the correct answer changes with time — recent events, IPOs, this
week's movers, current rankings. False when the answer is stable — sectors,
categories, peers, "names like X".

This is a judgment about the **answer**, not the wording. "Which pharma stocks
could I test?" and "what pharma names should I look at?" are the same need and
both resolve False. It rides the existing interpretation pass. Do not add a
second LLM call, and do not add a phrase list.

Anchors: `src/argus/agent_runtime/llm_interpreter_types.py`,
`src/argus/agent_runtime/llm_interpreter.py`.

### 3.5 Composer change

`discovery_stage_result_if_applicable`
(`src/argus/agent_runtime/discovery/composer.py:53`) currently owns every
`asset_discovery` turn and always searches. Add the cheap branch **before** the
allowance check at line 78:

1. `asset_discovery` and not `needs_current_facts` and not an explicit search
   request → cheap path. No allowance read, no charge, no provider call.
2. Otherwise the existing grounded path, unchanged.

When the allowance is exhausted (line 78's `discovery_limit_reached`), fall
through to the cheap path instead of the recovery message. A guest who has spent
both searches still gets verified rows; they just are not current. This is the
founder's position from §12.8 and it is only acceptable because of §3.7.

### 3.6 Cheap path implementation

New module `src/argus/agent_runtime/discovery/model_knowledge.py`. Same
deterministic spine the grounded path uses:

1. LLM names candidates from the typed `AssetDiscoveryRequest` — **no free-text
   parsing of the user message**, same as `extraction.py` does for search
   results.
2. Every name goes through `resolve_asset()`. Unresolvable names are dropped and
   surfaced through the existing `unverified_names` channel with the copy fix
   already shipped in PR #291.
3. Validated candidates are voiced by the existing voicing step.
4. Emit the sidecar with `sources: []`.

Reuse `validation.py` as-is, including the `_resolution_matches_request()`
corroboration gate. Ticker collisions are the same hazard on both paths — the
gate exists because TRX resolved to a stock when a crypto was meant.

### 3.7 The unsourced marker — derived, never asserted

Do **not** add a `grounding` flag to the sidecar. Zero sources is the signal:

> A discovery sidecar with `sources.length === 0` is ungrounded and must render
> the unsourced marker.

This is unforgeable. A flag can disagree with the evidence; a derived marker
cannot. It also handles a case a flag would get wrong — a grounded search that
came back with no usable sources **is** ungrounded at that point, and correctly
renders as such.

No schema version bump. `DiscoverySidecar` is unchanged
(`web/components/chat/types.ts:274`).

Frontend, in `DiscoverySourcesPanel` / `ChatMessage`:

- `sources.length > 0` → sources panel, unchanged.
- `sources.length === 0` → a short line stating the rows come from general
  knowledge rather than a current search, plus the footer row in §3.8.

Copy goes in `web/public/locales/en/common.json` and the `es-419` file. Both
languages, same landing.

### 3.8 The deliberate-search row

When the marker shows and the viewer has allowance left, render a footer row:
**"Search for current results"**. Tapping it re-runs the same ask as a grounded
search and spends one.

This is the escape hatch that makes the classifier's accuracy a non-issue. Being
wrong toward "needs currency" costs one search — exactly what searching every
time would cost, so it is never worse. Being wrong the other way leaves the user
with cheap rows and a one-tap override.

Use `NextMoveRow` (`web/components/chat/NextMoveRow.tsx`). Do not build a new
row component. Hide the row when the allowance is spent — an affordance that
cannot fire is worse than none.

### 3.9 Continuity — the reason this holds together

Tapping a cheap row must behave exactly like tapping a grounded one. It already
will, provided the cheap path emits the same sidecar: the frontend derives the
mention from the sidecar, not from the path that produced it.

`discoveryCandidateMention()` (`web/lib/chat-discovery-sidecar.ts`) turns a
tapped candidate into `asset:{asset_class}:{symbol}`, which is how identity
survives into the next turn. This is the fix that shipped as `ea2b3f35`; the
cheap path inherits it for free and must not re-derive identity from chip text.

**Acceptance for this specifically:** tapping a cheap verified row must reach
"What date window should I use for {SYMBOL}?" — the asset known, never re-asked.

---

## 4. Item 2 — retry, and not charging for our own failures

### 4.1 What is actually wrong

§12.5 said the retry affordance does not exist. It does. The gap is narrower.

`discovery_search_failed` is raised with `retryable=True`
(`src/argus/agent_runtime/discovery/composer.py:117`), but the frontend renders
retry from `metadata.retry_last_turn`
(`web/lib/chat-retry-actions.ts:171`) — and the discovery failure path never
attaches that key. `recovery.retryable` alone renders nothing.

The rail is complete and already self-supersedes when a newer turn arrives
(`src/argus/api/message_store.py:877`). Discovery is simply not on it.

### 4.2 Fix

Attach `metadata.retry_last_turn` on the `discovery_search_failed` recovery, the
same shape other retryable recoveries use. Render it as a footer row under the
user's run via `NextMoveRow`, consistent with §3.8.

> **Build disposition (superseded 2026-07-28).** The stage-patch attach never
> reached metadata: `WorkflowState` declares no `retry_last_turn` channel, so
> the graph dropped it silently, and `complete()` strips the key from
> completed turns by design. The lifecycle already owns this contract —
> retryable discovery failures now finalize via `recoverable_failure()`, which
> anchors the durable retry to the persisted user request, marks the turn
> `recoverable_failed`, and does not settle the message allowance (our outage,
> not the user's spend). Witnessed live: "Reintentar" rendering from persisted
> metadata and replaying the ask. No new row component; the standard rail.

### 4.3 Stop charging for failed searches

`usage["search_attempted"]` is set to True **before** the provider call
(`composer.py:99`) and cleared only for `not_configured` (line 107). So
timeouts, HTTP errors and malformed responses all charge the allowance.

`record_discovery_search_evidence`
(`src/argus/api/chat/discovery_evidence.py:259`) charges on
`search_attempted is True`. Change the rule to:

> Charge when the turn produced a usable result — that is, when `fallback_code`
> is absent.

Do not wait on the provider's billing policy for errored requests. Whatever
Perplexity bills us, charging a stranger for our own outage is wrong, and the
global daily ceiling already bounds real spend.

> **Refinement found in build (2026-07-27): the ceiling is exempt.** "The
> ceiling bounds real spend" is only true if the ceiling counts every attempt —
> failed provider calls can still be billed. So the global ceiling charges on
> every attempt, and only the user's allowance forgives failures. One rule per
> bound, each matching what that bound protects.

A retry that succeeds charges normally. A retry that fails charges nothing.

### 4.4 Why this matters more at two than at three

At an allowance of two, one provider blip costs half a guest's premium taste and
makes them retype. Their takeaway is "Argus is broken", not "the search provider
blipped".

---

## 5. Item 3 — an incomplete rule reported as an unsupported one

### 5.1 Root cause, corrected

§12.1 is titled "identity fix appears absent on the guest path". **That is
wrong** and an agent working from it will hunt the mention plumbing and find
nothing.

The observed message was *"Argus can't run Backtest WMT directly yet **for
WMT**"*. That trailing "for WMT" comes from `_primary_symbol(strategy)`
(`src/argus/agent_runtime/clarification_contract.py:199`). **The asset resolved
correctly. Identity arrived.**

The real cause is two lines below:

```python
subject = raw_value or "that rule"
return f"Argus can't run {subject} directly yet{symbol_suffix}. ..."
```

`clarification_contract.py:210`. When there is no unsupported reason code the
rule is *incomplete*, not unsupported — the comment at line 202 says so
explicitly — but the copy still names a subject from `raw_value`, which here was
the chip's own text. A missing rule gets reported as an unsupported one.

Tapping "Backtest WMT" means "test WMT, I have not named a strategy yet". It is
intermittent because it depends on `raw_value` being populated.

### 5.2 Fix

When `_unsupported_reason_code(response_intent)` is `None`, the copy must not
name a subject at all. Ask for the rule:

> "What rule should I test for {symbol}? Which supported direction should I
> use: {options}?"

Keep the existing `raw_value` copy for the paths that genuinely have an
unsupported reason code — `sentiment_news_rule`, `future_performance`,
`unsupported_time_granularity` are all correct as written.

Both languages. Mirror in `web/public/locales/*/common.json` where the
`unsupported_recovery*` keys live.

### 5.3 Acceptance

Tapping a discovery row for an asset with no strategy named must ask what to
test. It must never claim a capability limit for a rule the user never gave.

---

## 6. Item 4 — answering the question routed to change-conflict

### 6.1 What was observed

Argus asked *"What date window should I use for JNJ?"*. The guest answered *"this
year so far"*. Argus replied *"I could not resolve that choice without changing
your current idea"* and offered Provide missing detail / Keep idea unchanged /
Cancel.

The interpreter was right: `semantic_turn_act=answer_pending_need`,
`reason_codes=['date_range_answered']`.

### 6.2 Not a split brain — confirmed

`artifacts/continuity.py`, `clarification_contract.py` and
`interpreter/date_window_repair.py` contain **zero** guest branching. Guest and
registered run identical code. Year-to-date resolution exists and works
(`src/argus/nlp/natural_time.py:249`, resolving to Jan 1 → today).

So this is not a guest regression. It is a state the registered path can reach
too and that we have not happened to hit.

### 6.3 The guard

`no_progress_response_if_equivalent`
(`src/argus/agent_runtime/artifacts/continuity.py:51`) fires when all three hold:

- `semantic_turn_act == "answer_pending_need"`
- `missing_fields` is non-empty
- entry and exit snapshots assess as `no_progress` (line 132)

The answer was understood, so one of two things happened. **This is the one
thing static reading cannot settle** — it needs the recorded turn.

**Diagnostic, before any fix.** From the recorded turn, establish:

- (a) Did `candidate_strategy` carry the resolved window? If not, resolution
  produced a value that never reached the draft — fix the patch.
- (b) Was `missing_fields` non-empty because of a **different** field? If so the
  guard is firing correctly and the copy is wrong: it must ask for that other
  field, not offer a change-conflict menu.

Write the answer into this section before changing code.

### 6.4 The invariant, either way

> Answering the exact question Argus asked must never produce a change-conflict
> menu.

Whichever cause the diagnostic finds, that is the property the fix must
establish and the test must hold.

### 6.5 Scope note

This is the interpret/edit spine, not discovery. It is in this pass because it
was found here and it is the most corrosive of the four to a chat-first product
— the user answered correctly and was told they were changing their mind.
Related to the #271 protected-edit work.

---

## 7. Item 5 — measurement, no code

§12.3 recorded that a guest gets 10 messages and 2 searches, and that discovery
asks plus follow-ups exhaust messages before searches. The 2 may be unreachable.

**No instrumentation is needed.** `first_result_completed` already exists in
`GuestFunnelEventKind` (`src/argus/observability/guest_funnel.py:14`).

The metric that matters is **did a guest reach one real backtest result**, not
whether they spent their searches. Item 1 largely dissolves the tension anyway:
once most discovery asks are answered cheaply, searches are reserved for asks
that need currency.

Do not tune any allowance number in this pass. Read `first_result_completed`
against real guest sessions first.

---

## 8. Item 6 — offload the blocking provider search

### 8.1 Why this is here

`provider.search(...)` in `discovery/composer.py` runs a **synchronous**
`httpx.Client` POST (`discovery_search/http_post.py`) inside an async coroutine
with no thread offload. While it runs, the event loop cannot schedule anything
else.

The consequence is not cosmetic: **one discovery search stalls every other
in-flight chat stream on that worker.** A user who never asked a discovery
question waits on a stranger's Perplexity call.

It was found as blocker #2 of Slice B, but it is a production concurrency bug
that stands on its own. It lands here because item 1 already rewrites this file.

### 8.2 Fix

Offload the call — `anyio.to_thread.run_sync` or an async client. Keep the
timeout behavior identical; `config.timeout_seconds` must still bound it.

### 8.3 Acceptance

Two chat streams, one issuing a discovery search: the second stream's tokens
keep arriving while the search is in flight. Prove it with two concurrent live
turns, not a unit test — the failure is a scheduling property.

---

## 9. Item 7 — Slice B, honest live progress lines

Carried in from `2026-07-26-chat-next-moves-live-progress-polish.md` §4. That
slice listed three blockers. **Item 6 above retires the second one.** Two remain,
and they are the slice's real cost.

### 9.1 Blocker — there is no channel for a sub-stage event

`stage_start` is synthesized in `runtime.py` from LangGraph `on_chain_start`
events, filtered to `node_name in WORKFLOW_NODE_NAMES` and deduped by node name.
The discovery composer sits several layers below the `interpret` node and has no
way to push an event into that generator.

A channel must be built — contextvar-backed queue, or a side channel merged into
the `astream_events` loop — and it must bypass both the node-name filter and the
dedupe set. **This is infrastructure, and it is the bulk of the slice.**

### 9.2 Blocker — the neutral-label fallback does not work

`ChatInterface.tsx` does ``t(`chat.status.${stage}`) || t('chat.status.preparing')``.
`i18n.ts` sets no `parseMissingKeyHandler` and no `returnEmptyString`, so
i18next returns the missing key itself, which is truthy. The fallback never
fires, and an older frontend receiving `discovery_search` renders the literal
string `chat.status.discovery_search`.

Fix the fallback. Until it works, the "additive events are backward compatible"
claim is false for every deployed client.

Also required: `web/lib/argus-api.ts` types the event as `{ stage: string }`;
add `detail?: string`.

### 9.3 Behavior

Two additive sub-stage events from the discovery composer path, streamed while
the interpret stage runs. Full behavior and non-goals are in the next-moves spec
§4 — do not restate them here, build from that section.

### 9.4 Sequencing

Item 6 must land first. Without it both progress lines arrive together when the
search returns, which is precisely the dishonesty the slice exists to remove.

### 9.5 Search value visibility — per-row citations (founder-approved 2026-07-28)

Grounded rows should wear their evidence. Every grounded candidate already
carries `source_indices` into the sidecar, so no backend change is needed:

- Each grounded candidate row renders a small domain chip after the reason
  text — the domain of its first source (`sources[source_indices[0]].domain`),
  muted, non-competing with the title.
- Tapping the chip opens the existing sources drawer anchored to that source.
  No new outbound-link surface; the drawer keeps ownership of URLs.
- Cheap rows have no indices and render no chips — one more visible
  difference between a researched answer and a remembered one, on top of the
  marker line.
- Bounds: one chip per row (first corroborating source); the drawer shows the
  rest. No per-claim prose citations — the rows are the claims here.

Acceptance: a grounded EN/ES response shows per-row domain chips opening the
drawer at the right source; cheap responses show none; screenshots both
themes.

---

## 10. Item 8 — guest identity and lifetime

Carried in from `2026-07-27-guest-grounded-discovery-quota.md` §9.

**This item changes every guest turn, not only discovery.** See §12 on why it
belongs in its own PR.

### 10.1 A correction that changes this item's shape

§9 of the source spec says *"Guest expiry is fixed at 10 minutes from creation,
not sliding. A guest reading a backtest result can lose the workspace
mid-thought."*

**That is the wrong object.** Verified against the schema on 2026-07-27:

- `guest_workspaces` carries `constraint guest_workspaces_fixed_expiry check
  (expires_at = created_at + interval '7 days')`, and the insert trigger sets
  `new.expires_at := new.created_at + interval '7 days'` regardless of what the
  application passes
  (`supabase/migrations/20260724101324_add_guest_workspaces.sql:76,104`).
- The 10 minutes belongs to `guest_workspace_handoffs` — the token that moves a
  workspace to an email
  (`supabase/migrations/20260724211312_guest_workspace_handoffs.sql:86`).

So a guest workspace lives **seven days**, fixed and non-sliding. Nobody loses a
workspace mid-thought on a ten-minute timer.

Nothing else in the stack is ten minutes either: `jwt_expiry = 3600`
(`supabase/config.toml:172`), one hour, with refresh-token rotation.

**Before any work on sliding expiry:** confirm against a real session whether
anything user-visible expires early. If something does, it is the anonymous Auth
session or the client token, not the workspace row, and that is a different fix
in a different place. Do not build sliding expiry for a problem that has not
been shown to exist.

### 10.1b The false fact is written into shipped code — correct it

PR #291 justified visitor-keying with the same wrong premise, in two places:

- `src/argus/api/chat/discovery_evidence.py:61` — *"it lives ten minutes and
  renewal mints a fresh user_id"*
- `supabase/migrations/20260727230000_add_visitor_usage_counters.sql:5` — the
  same sentence

**The code is right; the reason is wrong.** Visitor-keying is correct regardless
of the TTL — a fresh guest session mints a new `user_id` the moment someone
clears cookies or opens a private window, and no timer is needed for that. But a
comment that states a false fact will be trusted by the next reader, and this
one already propagated into two specs.

Fix the Python docstring directly. Leave the applied migration file alone —
correct the table's `COMMENT ON TABLE` in the next migration that touches this
area rather than editing a migration that has already run.

### 10.2 Messages and simulations reset on a fresh workspace

Real, and the one piece of §9 worth building.

`allowance_windows` (`src/argus/domain/usage_limits.py:78`) gives a guest a
`guest_session` window anchored to the workspace: `period_start = expires_at -
7 days`, `period_end = expires_at`. Both message and simulation allowances key
on `user_id`.

A new guest workspace mints a new `user_id`, so it mints a fresh 10 messages and
a fresh simulation. This is the same hole discovery just closed — it is simply
not on a ten-minute treadmill, so it is ordinary anonymous-abuse shape rather
than an urgent one.

**Fix:** the same treatment discovery received. Key on the visitor
(`discovery_counter_subject` in `src/argus/api/chat/discovery_evidence.py`, the
HMAC digest), charge into `visitor_usage_counters`, and use a plain day window
rather than `guest_session`.

**Product change this creates, and it needs an explicit decision:** today a
guest gets 10 messages per workspace, which lasts 7 days. After this change they
get 10 messages per visitor per day. That is *more* generous for a returning
visitor and *less* generous for someone opening fresh sessions. State the
intended number and window in this section before writing code.

### 10.3 A counter that cannot be read must not go silent

`discovery_allowance_available`
(`src/argus/api/chat/discovery_evidence.py:234`) fails closed: an unreadable
counter is treated as exhausted. Before this pass that surfaced as
`discovery_limit_reached` — telling a user they are out of searches when we
simply could not read the number.

**Item 1 changes what that failure looks like.** With the exhausted path falling
through to cheap verified rows, an unreadable counter now yields honest
ungrounded rows instead of a wrong error. Better for the user — and completely
invisible to us.

That is the same shape as the meter that silently never counted: swallowed as
`failure_classification="telemetry_only"`, so a dead counter and a healthy one
look identical.

**Required:** keep failing closed, and make the read failure loud — a distinct
counter or alertable log line separate from ordinary allowance exhaustion. The
user-facing behavior stays graceful; the operator-facing signal stops being
silent.

### 10.4 Not in this item

The stray confirmation card on a discovery ask (source spec §12.2) stays parked.
It is cosmetic, it has no confirmed cause, and it does not belong in a PR that
changes guest allowance identity.

---

## 11. Item 9 — language parity, English and Spanish

**This is a build item, not a closure gate.** It was recorded as something to do
later; the founder moved it into the build on 2026-07-27 so that when these PRs
land, the only remaining work on grounded discovery is promotion.

An item is not done in one language. Both, or not done.

### 11.1 What parity means here

Argus is language-agnostic by design — no phrase gates, no keyword routing, one
runtime spine that interprets before it branches. Parity is therefore not a
translation chore bolted on at the end; it is the property that proves the spine
actually works, and a surface that only renders in English is evidence the spine
was bypassed somewhere.

Supported languages are English and `es-419`. CI already enforces key parity
between the catalogs — that check passing is necessary and nowhere near
sufficient, because a key can exist and still render wrong or read like a machine
translated it.

### 11.2 Every surface this spec adds ships in both

| Surface | Section |
| --- | --- |
| Unsourced marker copy | §3.7 |
| "Search for current results" row | §3.8 |
| Retry row on a failed search | §4.2 |
| Incomplete-rule copy — "What rule should I test for {symbol}?" | §5.2 |
| Whatever §6's diagnostic produces | §6 |
| Sub-stage progress labels | §9.2 |

Catalogs: `web/public/locales/en/common.json` and
`web/public/locales/es-419/common.json`. Backend-composed copy follows the
existing `is_spanish` convention already used in
`artifacts/continuity.py` and `clarification_contract.py`.

### 11.3 The cheap path has a language trap the grounded path does not

The cheap path asks an LLM to name candidates and produces `reason_text` for each
row — **user-visible prose generated at runtime**, not a catalog string.

A Spanish discovery ask must produce Spanish reason text. The grounded path
already voices in the user's language; §3.6 step 3 reuses that voicing step
specifically so this is inherited rather than reinvented. Do not let the cheap
path assemble its own prose.

Same trap in `unverified_names` copy and in the query summary.

### 11.4 Journeys to prove live

From `2026-07-25-grounded-discovery-search-v1-design.md` §1.1, which defines J1,
J2 and J3. Run each in both languages against a real stack:

1. **J1 — standalone category discovery** — "¿Qué acciones de ciberseguridad
   puedo probar?" → verified rows → tap one → the asset is known and never
   re-asked → date window question → confirmation.
2. **J2 — post-result peer discovery.** See §11.5; this one is not a translation
   pass, it is unproven behavior in both languages.
3. **Cheap path marked ungrounded** — a Spanish ask with no currency need returns
   rows with the Spanish unsourced marker and a Spanish "search for current
   results" row.
4. **Failed search** — Spanish retry row renders, reads naturally, and works.
5. **Exhausted allowance** — the fall-through to cheap rows is honest in Spanish.

Together J1 and J2 in both languages are #244 acceptance criterion 9.

### 11.5 J2 has never been run, and no slice ever promised it

Criterion 1 on #244 covers "standalone **and post-result** peer/category
prompts". The standalone half is proven. The post-result half is not, and the
next-moves spec says so explicitly:

> "Post-result / post-draft selection: the selected asset keeps the
> resolver-owned identity. Any broader carry-forward of capital, dates,
> timeframe, benchmark, cadence, or strategy follows the general
> artifact-continuity contract and **is not promised by Slice D**."

So the behavior is *assumed* to work because artifact continuity exists. Nobody
has watched it.

**Run it, in both languages:** produce an NVDA result → "find companies similar
to Nvidia" → the response appears beside the result **without erasing it** → tap
AMD → the confirmation carries forward capital, date window, timeframe,
benchmark and strategy from the anchored setup, with only the asset changed.

**If carry-forward does not happen**, that is a finding, not a task to
improvise. Record it here with what actually carried and what did not, and raise
it before writing a fix — the artifact-continuity contract is the interpret/edit
spine and is out of this spec's scope to redesign.

### 11.6 Acceptance

Screenshots or transcripts in both languages for every surface in §11.2. A
passing catalog-key-parity check is not acceptance. Neither is a translation
nobody looked at.

---

## 11b. Live QA record (2026-07-28, local Supabase, both languages)

Everything below was watched on a real guest stack (real Perplexity, real
OpenRouter, real Alpaca resolution, real Postgres counters), not asserted from
tests.

**Witnessed working:**

- Cheap verified rows, EN and ES: resolver-verified tappable rows, honest
  dropped-names sentence, "From general knowledge, not a current search" /
  "De conocimiento general, no de una búsqueda actual" marker, zero provider
  calls in the log.
- Escalation row shown only while allowance remains, in both languages; tap
  sends the localized sentence as plain text and routes to a grounded search.
- Grounded search success (ES): five resolver-verified rows from real
  Perplexity results, Spanish reason text, "Fuentes: … · al 28 jul 2026"
  line, "5 fuentes ›" drawer with localized dates.
- Charging: the real `visitor_usage_counters` row advanced only on usable
  results (2/2 exact); failed searches charged the global ceiling but never
  the visitor; the visitor allowance survived two workspace renewals.
- Exhausted fall-through: with 2/2 spent, a discovery ask returned cheap rows
  with `can_request_search: false` — escalation hidden, marker shown, no dead
  end and no fake outage message.
- Failed search: honest voiced recovery in the user's language, turn
  finalized `recoverable_failed`, durable retry anchored to the request,
  "Reintentar" rendered and replayed on tap.
- Item 3 live: tapping a row lands on "Got it — PFE (Pfizer) against SPY.
  What date range…" — identity known, no capability-limit claim.
- Item 4 (founder's runtime fix) verified: "this year so far" advanced to a
  ready confirmation. No conflict menu.
- J2 post-result carry-forward, EN and ES: after an AAPL vs SPY result,
  tapping a peer row produced "Ready to test buy-and-hold for MSFT over
  July 28, 2025 – July 27, 2026" — window, strategy, and benchmark carried,
  only the asset changed. First time this journey was ever run.

**Defects found live and fixed in this PR** (each also a commit):

- `discovery_model_knowledge` was never registered in the LLM task registry —
  every cheap turn failed with a KeyError. Unit tests stub the call; only a
  real invocation consults the registry.
- The escalation row sent a typed `select_response_option`, which admission
  validates against the latest turn's registered options — rejected as stale.
  It now sends plain text; the sentence is the request.
- `retry_last_turn` never survived the graph (no state channel) — replaced by
  the `recoverable_failure()` lifecycle rail (see §4.2 disposition).
- An internal explanation sentence rendered as the unsupported-copy subject
  ("Argus can't run The requested assumption change needs clarification.
  directly yet."). Sentence punctuation now disqualifies a subject.
- Discovery voicing silently swallowed failures; now logged with
  classification.
- Voiced prose duplicated the rows and the marker (founder snapshot); voicing
  is now one framing sentence plus optional drops.

**Observed, recorded, NOT fixed here:**

- **Discovery ask during a pending confirmation is preempted** by an
  artifact-continuity corridor and answers "I can't search live sources…" — a
  false capability claim. Same family as issue #292; the corridor, not
  discovery, owns the turn. Needs its own slice.
- **One Spanish phrasing repeatedly failed interpretation** ("¿qué acciones de
  energía solar hay ahora?") with schema validation errors from both tier
  models under full conversation context; the bare schema call succeeds. The
  system degraded honestly (recovery + retry). Interpreter-robustness item,
  not discovery.
- **Confirmation summary mixes languages** ("Ready to test buy-and-hold for
  MSFT over 28 de julio de 2025…") — backend-composed summary line is
  English-framed with localized dates. Pre-existing composition behavior.
- **A stale auth cookie can blank the app** into an RSC redirect loop
  (backend-side session gone, client loops `/` ↔ `/chat`). Local-QA artifact
  of killing the backend, but the recovery path should not hard-blank.
  Guest-lane robustness note.

**Founder polish round 2 (2026-07-28, built as `3a682db9`):**

- **Silent drops.** Macro pattern adopted: *explain absences the user can see;
  never narrate internal filtering.* Voicing mentions a dropped name only when
  it is the user's own subject (typed anchor or named in their message), or
  when zero candidates verified (the drop is then the answer). Sidecar and
  telemetry keep full lists. Witnessed: Samsung/Lenovo/HP dropped silently
  behind a successful Apple-peers answer.
- **Row language unified on the subtle variant:** borderless at rest, hover
  brightens arrow + title together (no box, no shadow), hairline separators,
  shared `NextMoveTitle` across candidates, follow-ups, and the search
  escalation. Full-row >=44px hit area unchanged.

**Founder snapshot dispositions (2026-07-28):**

1. Redundant disclosures in the cheap reply — **fixed** (voicing rewrite).
2. "Action no longer attached" on the escalation tap — **fixed** (plain-text
   send).
3. Wordy failure voicing — **fixed** (two-sentence cap).
4. Retry appends a duplicate turn instead of replacing in place, and the
   failure copy says "type again" — **recorded**. SOTA (ChatGPT, Claude) is
   in-place regeneration: replace the failed assistant message, no new user
   bubble. The rail already supports replacement (`replacementAssistantId`)
   when no request-message anchor exists; unifying on in-place replacement is
   retry-rail work (#249-adjacent), not discovery. Message allowance is
   already NOT charged for retryable failures after this PR, so the quota
   half of the concern is resolved.
5. Exhausted-search presentation — after this PR the exhausted path shows
   cheap rows with the escalation hidden, so it cannot read as an outage.
   **Resolved 2026-07-28 (landed in this PR, `a200536e`):** the founder chose
   the appetite-gate. Doctrine: *upsell on appetite, never on apology* —
   transient failures keep plain retry; the guest exhausted answer carries a
   quiet teal banner where the hidden escalation row sat, opening the
   standard conversion modal with a typed `discovery_searches` reason
   (frontend union + backend schema/funnel literals + OpenAPI artifact).
   Registered users at their daily cap get nothing (no gate to offer,
   deliberate). Also landed: rows tint arrow+title with the palette teal
   (`#5ba897`) on hover in both themes — monochrome brightening was
   imperceptible in light mode.

---

## 12. Testing and gates

### 12.1 The rule that this pass exists partly to establish

Anything touching a usage counter needs a test that charges **real PostgreSQL**,
not the in-memory store. Two foreign-key defects shipped green in the previous
lane because the in-memory store accepts writes the real schema rejects, and the
failure is swallowed as `failure_classification="telemetry_only"` — so a
permanently dead meter looks exactly like a healthy one.

Item 2 changes charging behavior. It needs a real-Postgres test.

### 12.2 CI has the machinery; one list is hand-maintained

`guest-release-gates` (`.github/workflows/ci.yml`) starts a real Supabase and
runs a Postgres matrix, and `scripts/qa/assert_pytest_gate.py` **fails the build
on any skip**. Good.

But the step enumerates five files by hand (`ci.yml:139`), while the job one
above it is deliberately directory-level with the comment *"so new test files
are gated without editing this workflow"* (`ci.yml:59`). A new `_postgres.py`
test is therefore invisible in the gate unless someone remembers the list.

**Change the step to glob `tests/*_postgres.py`.** This widens the required gate
from five files to ten and makes the job slower. **Founder-approved
2026-07-27 — do not relitigate.** Silent omission is the failure mode being
prevented, and a hand-maintained list is how the two foreign-key defects
reached main.

### 12.3 Per-item acceptance

1. **Cheap rows** — "which pharma stocks could I test?" as a guest returns
   tappable validated rows, zero sources, visible unsourced marker, and a
   "Search for current results" row. Tapping a row reaches "What date window
   should I use for {SYMBOL}?". Zero provider calls in the log.
2. **Retry** — a forced provider failure renders a retry row under the run, the
   allowance is unchanged, and the retry succeeds against a healthy provider.
   Proven against real PostgreSQL, not memory.
3. **Incomplete rule** — tapping a row for an asset with no strategy asks what
   to test and never claims a capability limit.
4. **Pending need** — answering the asked question advances the idea. Diagnostic
   written into §6.3 before the fix.
5. **Measurement** — none.
6. **Async offload** — a second chat stream keeps producing tokens while a
   discovery search is in flight. Two concurrent live turns, not a unit test.
7. **Slice B** — two progress lines arrive separately, and an older frontend
   receiving an unknown stage shows the neutral label rather than the raw key.
8. **Guest identity** — a fresh guest workspace does not reset the message or
   simulation allowance. Real PostgreSQL.
9. **Language parity** — every surface in §11.2 evidenced in both languages, and
   the J1/J2/J3 journeys run in both (§11.4). **No item counts as accepted in
   one language.**

### 12.4 Browser QA is required

Every defect in the previous lane passed unit tests and died live: the source
dates a day early, the identity drop, the tap targets, both foreign keys. Run a
real guest session against local Supabase before calling any of this done.

Practical notes: only one Next dev server at a time (Next 16), one local
Supabase stack per machine, and a lane worktree's `.env` may be a symlink into
the integration worktree — `ls -la` and remove it before writing, or the shared
env is destroyed.

---

## 13. Out of scope

Each exclusion below is tracked as its own issue, so nothing here can drift.

- Tuning any guest **discovery** allowance number (§7) — issue #294, blocked on
  promotion by nature. The message and simulation numbers are a live decision
  inside §10.2 and must be stated there.
- The stray confirmation card on a discovery ask — issue #292, cosmetic, no
  confirmed cause (§10.4). Deliberately deferred until PR A lands, because it
  lives in the composer/routing code PR A rewrites.
- Sliding guest expiry — issue #293, unless its verification shows something
  real. The workspace lives 7 days by database constraint; the 10-minute figure
  in the source spec is the handoff token.
- Quick take / Explain / Try next surface ownership — #249. Two interplay notes:
  #249's runtime slice serializes behind PR A (`result_followups.py`, one-owner
  rule, its own text already says so), and after item 1 both "what should I try
  next?" and cheap discovery are unmetered LLM answers — the boundary between
  them is the typed act alone, never cost or wording. Item 1 also fixes the
  failure #249 polices: a typed discovery outcome being replaced by generic
  prose.
- Removing guest search. It stays at 2. The previous spec's §12.9 proposed
  registered-only and §12.10 corrected it; the visitor metering is load-bearing
  and unchanged.

## 14. The one thing left after this: promotion

**When every item here lands, grounded discovery is code-complete.** Promotion is
the only remaining work, and it is **out of scope for whoever builds this spec** —
it belongs to a promotion run with the founder.

Spanish parity used to sit here as a closure gate. It is now item 9 (§11), inside
the build, precisely so this section stays short.

### 14.1 What promotion covers, and why it is not yours

`render.yaml` contains **zero** `DISCOVERY` variables. No flag, no provider key,
no global daily ceiling. Every proof to date — including all of PR #291 — was
against a local stack.

Promotion means: set the runtime variables, run the `visitor_usage_counters`
migration on the hosted database, activate the flag under the normal canary
discipline. Founder activation is an explicit gate on #244 between provider
evaluation and runtime, and it is not something an implementing agent can or
should do.

**Do not** add `DISCOVERY` variables to `render.yaml` as part of these PRs, and
do not treat a local proof as a production one.

### 14.2 One issue edit that does belong in these PRs

#244's no-touch list forbids *"model-memory candidate lists presented as current
facts"*, and acceptance criterion 8 forbids falling back to *"uncited model
memory"* on outage.

The cheap path is model memory that is explicitly **not** presented as current —
that is what §3.7's derived marker guarantees — and outage behavior is unchanged
by this spec: a failed search gets a retry row (§4.2), never cheap rows. Only an
**exhausted allowance** falls through to the cheap path.

Compatible in substance. But someone reading #244 when this lands will read it as
a violation, so update the issue text in the same PR.

### 14.3 Closure checklist for #244

PR #295 completed PR A (items 1–6 and 9). PR B owns items 7–8.

- [x] PR A items 1–6 and 9 landed (§3–§11) through PR #295
- [ ] PR B items 7–8: honest live progress plus Guest identity/lifetime
- [x] Both-language journeys proven live, J1 and J2 (§11.4) — closes acceptance 9
- [x] J2 post-result carry-forward watched, not assumed (§11.5)
- [x] Real-PostgreSQL proof for anything touching a counter (§12.1)
- [x] #244 text reconciled with the cheap path (§14.2)
- [ ] **Promotion — founder, out of scope here (§14.1)**

---

## 15. Documentation to update on landing

- `docs/API_CONTRACT.md` — the sidecar's ungrounded case, and that zero sources
  is the marker's only source of truth.
- `docs/PRODUCT.md` — cheap verified rows as the default discovery path.
- Grounded discovery design §10 — reconcile "never a model-memory shortlist
  presented as current" with the cheap path, which satisfies it by being
  visibly unsourced rather than by not existing.
- Issue #244 register.
