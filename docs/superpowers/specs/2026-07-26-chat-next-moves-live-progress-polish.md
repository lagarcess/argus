# Chat Polish: Stacked Next-Move Rows + Honest Live Progress

**Status:** FOUNDER-DIRECTED FOLLOW-UP — direction approved 2026-07-26; row anatomy, resolved-group rule, and sources-drawer promotion approved 2026-07-27. Slices A, C, and D delivered; Slice B remains.
**Shape:** three PRs, in order.

| PR | Scope | State |
| --- | --- | --- |
| **PR 1** — Slices A + C | Every UI change, zero runtime change | ✅ **Merged** — [#281](https://github.com/lagarcess/argus/pull/281), reconciled with integration (guest #279, costs #280) before merge |
| **PR 2** — Slice D | Discovery selection carries resolved identity | ✅ **Complete** — identity delivered and live-proven; chosen-state marker cut |
| **PR 3** — Slice B | Live progress lines | Not started; blocked on three backend prerequisites in §4 |

**Delivered in PR 1 beyond the original slice definition,** found during implementation and browser QA:

- A shared `turnInFlight` lock so persistent discovery rows cannot fire turns
  around a disabled composer (§2). Per-tab UI state only — the concurrency gap
  is recorded as backend scope in §5.
- Source dates format in UTC when they are calendar dates, so a publisher's date
  is not shifted a day west of UTC.
- The source count pluralizes through the catalog's `_one`/`_other` convention.
- Both sources-panel controls carry measured 44px tap targets (Codex P2).
- `markComposerActionsInactive` scoped to what it owns: retry and artifact
  actions are superseded, conversational options are left to the row renderer.
  This completes the intent of #85, which introduced the function to replace an
  indiscriminate wipe; the non-card branch was the last unconverted remnant.
- Dead `inputActions` state removed with the composer strip it fed.

**Slice D is complete and closed.** Its one behavior — a tapped candidate keeps
the identity the resolver already verified — is delivered and proven against the
real stack: tapping UNP after a railroad discovery used to answer "Argus can't
run Backtest UNP directly yet for UNP", the chip text read as a strategy name,
and now answers "What date window should I use for UNP?". The chosen-state
marker was cut (§2 table) and carry-forward on switch was deferred out of the
lane as general interpreter work owed to typed input too.

**Still open in the lane:** Slice B only. Plus the guest grounded-discovery
allowance, which is its own spec
(`2026-07-27-guest-grounded-discovery-quota.md`).
**Owner:** Follow-up lane after PR #276 merges (branch from `codex/private-alpha-next`; if #276's merge is held, stack a child branch on `claude/grounded-discovery-release-9cc859` and review against it as parent).
**Parent context:** Grounded Discovery Search v1 (issue #244, PR #276), founder UI-taste review of 2026-07-26.
**Scope class:** Small full-slice polish lane. Frontend presentation + one additive runtime event surface. No API-contract breaks, no new tables, no new flags, no new provider calls. One recorded product contract does change: outbound source links (Slice C).

---

## 1. Why

Founder review of the shipped discovery surface against current SOTA chat UIs
(Grok, Perplexity, ChatGPT) landed on one shared pattern: agent work renders as
**one evidence trail with two states** — stream what is actually happening while
working, then collapse into compact persistent evidence — and conversational
next steps render as **stacked rows, not pill chips**.

Two concrete gaps in Argus today:

1. Conversational affordances (clarify options, discovery candidates, footer
   follow-ups) render as `rounded-full` pills. Sentence-length options wrap
   badly (worse in es-419), and discovery candidate pills hide the
   backend-provided `reason_text` in a hover tooltip users never see.
2. During a discovery turn the user watches a generic interpret-stage label
   while the backend genuinely searches the web and verifies candidates. The
   real work is invisible.

Founder decisions recorded here so later lanes do not re-litigate:

- **Adopt** stacked arrow rows for conversational next moves.
- **Adopt** honest live sub-stage lines for the discovery pipeline.
- **Reject** a rotating search carousel for v1 — Argus makes exactly one
  bounded search per discovery turn; rotation would fabricate activity. It
  becomes legitimate only when a future research arc runs multiple real
  searches.
- **Promote** the "N sources ›" drawer into this lane with clickable outbound
  source links (founder decision 2026-07-27, superseding the earlier deferral
  and the no-links posture — see Slice C). The inline plain-text sources line
  itself is unchanged.
- **Keep** pills for true buttons: card CTAs, starter prompts, the user's
  echoed action bubble.
- **Do not** copy open-ended engagement follow-ups ("Explore AI cybersecurity
  risks") — PRODUCT.md anti-pattern; Argus follow-ups stay typed and grounded.

## 2. Slice A — Stacked next-move rows (frontend only)

### Behavior

- New shared presentation (working name `NextMoveRow` list) in
  `web/components/chat/`, per the founder-approved mock:
  - **At rest:** no border and no fill. A leading muted `↳` glyph
    (corner-down-right) plus row spacing carries the affordance. Flat, zero
    shadows, muted palette per `.agent/designs/argus/DESIGN.md`.
  - **On hover/press:** a hairline border (~0.5–1px, ~8–10px radius) plus wash
    (`black/5` light, `white/6` dark) appears, **sized to the text**, not to the
    column. A short label gets a short box.
  - **Hit area is not the visible box.** The tappable region spans the full
    message column and is ≥44px tall regardless of how narrow the hover box is.
    Never require aiming at the glyph or the text.
  - **Touch has no hover.** The rest state must read as tappable on its own;
    the wash is a pointer-device affordance, and press state covers touch.
  - Staggered fade/slide-in per existing message motion; optional 0.5px hairline
    above the group as a separator.
- Surfaces converted:
  1. **Assistant footer message actions** (`ChatMessage.tsx`
     `footerMessageActions`) — currently small pills under the message.
  2. **Discovery candidate chips** (`ChatMessage.tsx` discovery block) — become
     rows rendering `Backtest {symbol} · {name} — {reason_text}`; `reason_text`
     moves out of the `title` tooltip into visible muted text; row tap sends the
     existing typed `select_discovery_candidate` action unchanged.
  3. **Composer actions** (`ChatInterface.tsx` `composerActions`) — move from
     the floating centered strip above the input to stacked rows directly under
     the owning assistant message, so a question and its answer options live
     together. The composer strip rendering path is removed; gating conditions
     (hide while streaming/hydrating) carry over.
- Pills remain for: `StrategyResultCard` / confirmation-card CTAs, starter
  prompts, the user-turn action echo bubble.

### Resolved next-move groups (required with this slice, not after it)

Moving clarify options under their owning message removes the guard that
hides them today: `composerActions` renders only the **latest** AI message's
actions (`ChatInterface.tsx`, `[...messages].reverse().find(role === "ai")`).
Under the new placement every historical group stays on screen and re-tappable,
so a user can answer a question that was settled several turns ago. Without the
rule below, this slice ships that regression.

Approved behavior, by group semantics:

- **Clarify / direction options — exclusive.** One question, one answer. Once
  the pending need is settled, the whole option group stops rendering. Nothing
  is lost: the user's choice is already in the transcript as their own message.
- **Discovery candidates — non-exclusive.** Backtesting AKAM does not retire
  CHKP. Candidate rows persist indefinitely and stay tappable; tapping one later
  sends an ordinary user turn against whatever context is then active (the
  no-supersession rule already recorded in the Grounded Discovery design §8).
- **Footer follow-ups** follow the clarify rule when they answer a pending
  need, and the discovery rule when they are an open menu.

**Keep today's resolution rule; only the placement changes.** A clarify group
renders only while its message is the latest AI message in the conversation —
the exact condition `composerActions` already applies
(`[...messages].reverse().find(role === "ai")`). Once a newer assistant turn
exists, the question has been responded to and its options stop rendering.

This deliberately requires **no new backend field**. The rule is a structural
fact of the transcript, not an inference about backend truth, and it survives
reload because transcript order is persisted. It also means the semantics
users experience today are unchanged — this slice moves where the options
appear, not when they are live — so the regression risk is limited to the
relocation itself.

Discovery candidate rows opt out of this rule by construction: they are owned
by their message's `metadata.discovery` sidecar, not by the latest-AI-message
gate, and therefore persist.

**Locked dispositions (founder decision 2026-07-27).** These were argued and
settled; do not reopen without new evidence.

| Option | Disposition | Reason |
| --- | --- | --- |
| Remove candidate rows once one is tapped | **Rejected** | Costs more, not less. The user then asks "what were those railroads again?", which is a fresh metered search to re-tell them something already told. Measured: three turns in a live session produced exactly one search; re-taps consume no search and no discovery quota. |
| Freeze a row after one tap | **Rejected** | No requirement owner, no observed failure, and it contradicts grounded discovery design §8. It eliminates one case (double-tap) out of seven; every hard case is about switching *between* candidates and survives untouched. It also forbids the reasonable act of re-running the same asset over different dates. |
| Discovery-specific machinery for mid-setup switches | **Rejected as framed** | A tap is an ordinary user turn (design §8). "Tap UNP while answering a CSX date question" is the same event as typing it, and that path already exists and is tested. The observed failure was a parse defect (`"Backtest UNP"` read as a strategy name), not a state defect. |
| Keep rows live, mark what was chosen, handle switches honestly | **Accepted** | Preserves paid-for evidence, keeps re-testing one tap away, and makes the decision legible. |
| Chosen-state marker | **Cut** (founder decision 2026-07-27) | Prevents no observed failure — the user's own echo bubble already shows the choice. The cheap version also fights a decision locked in this same lane: graying a row reads as *disabled* everywhere else in this UI (the in-flight lock uses exactly that), but these rows stay deliberately tappable so an asset can be re-run over different dates. Graying one that still works would be the interface lying. If a tester ever reports losing track across a long transcript, build it as a "done" affordance — a check or muted tag at full text strength — never as a gray-out. |
| Carry assumptions forward on a mid-setup switch | **Deferred, not this lane** | A general interpreter improvement owed to typed input too, not a discovery debt. |

**In-flight lock (in this slice).** The composer disables itself while a turn
runs. Persistent discovery rows must obey the same lock or they become a way to
fire turns around it — the per-message streaming flag does not cover a row on an
older message. One shared `turnInFlight` signal drives both. Disabled rows stay
visible and readable, because they are evidence, and simply stop accepting taps.

**One current behavior is deliberately removed.** Assistant footer actions today
do not disappear on older messages — they fade to `opacity-0` and return on
hover (`ChatMessage.tsx`, `footerVisibilityClass`). Hover does not exist on
touch, so that third state goes away: footer option rows render on the newest
assistant message and nowhere else.

Do **not** reach for the confirmation-card mechanism
(`confirmation_state !== "active"` + `confirmationStatusAllowsActions(...)`).
That pattern exists because cards carry durable backend lifecycle state that
outlives the turn. Clarify options do not, and adding a marker for them would
buy nothing the latest-message rule does not already give.

### Non-goals

- No change to action payloads, `chat_action` persistence, hydration, or the
  `metadata.discovery` sidecar. Presentation only.
- No new i18n keys for candidates (`chat.discovery_results.test_candidate`
  stays); option labels remain backend/labelKey-driven.

### Text handling — language-agnostic, not Spanish-specific

Argus routes in any language, so rows are sized by rules, never by tuning
against one locale. es-419 is a test case, not the design target.

- **Never truncate identity.** The symbol and the resolver-owned name always
  render in full. Only `reason_text` may clamp, at two lines, and it must never
  retreat into a tooltip — surfacing it is the point of this slice.
- **Logical CSS only** (`padding-inline`, `margin-inline-start`,
  `text-align: start`) so RTL scripts (Arabic, Hebrew) mirror without new code.
  The `↳` glyph must mirror with the flow or be swapped for a mirroring icon.
- **Separators are elements, not string glue.** `·` and `—` render as their own
  nodes; do not concatenate them into a translated string, and do not assume
  their order survives localization.
- **No fixed row height.** `min-height: 44px`, content grows the row.
- **`overflow-wrap: anywhere`** so Chinese/Japanese/Thai, which have no spaces
  to break on, wrap instead of overflowing.
- **Font stack must cover non-Latin scripts** or unmatched glyphs render as
  tofu boxes.

### Tests

- Update pinned frontend contract assertions (`alpha-frontend.test.ts` pins on
  the current pill markup/`actionLabel` sites) to the row renderer.
- Row rendering unit tests: reason text visible, typed action fired with a
  payload byte-identical to today's, composer-strip removal does not orphan
  gating.
- Resolved-group tests: an answered clarify group stops rendering, discovery
  candidate rows persist, and both survive reload identically to the live
  session.
- Browser QA (EN + es-419 as the long-string probe, plus one RTL and one CJK
  string fixture): clarify options under the message, candidate rows, hydration
  parity after reload, no clipping at any length, 44px targets on mobile
  viewport, rest-state affordance legible without hover.

## 3. Slice C — Sources drawer (frontend only; promoted into this lane)

Founder decision 2026-07-27: the "N sources ›" affordance ships **with Slice A**,
in the same PR, and source entries are **clickable**. This supersedes the
earlier deferral to the research arc and the no-outbound-links posture recorded
in the Grounded Discovery design §6.

### Behavior

- The inline sources line stays exactly as it is (muted plain text, domains +
  "as of" date). A trailing "N sources ›" control opens a panel.
- The panel is a **pure renderer** of the already-persisted
  `metadata.discovery` sidecar — one entry per source: title, plain-text
  domain, date. No new backend data, no new tables, no re-query, no new event.
- Desktop: right-side slide-over. Mobile: bottom sheet. Dismiss on backdrop tap
  and Escape; focus trapped while open and restored on close.
- Reload renders the panel identically from persisted metadata.

### Outbound links — approved, with three hard rules

Clicking a source opens the publisher in a new browser tab. The earlier
injection-hardening objection does not survive scrutiny: the model never
follows these URLs, extraction is schema-forced, and the resolver — not the
page — decides what is tradable. A user verifying a source is normal and
expected behavior. The real risks are narrower, and these rules cover them:

1. **`target="_blank"` with `rel="noopener noreferrer"`.** No opener handle, no
   referrer leakage.
2. **The visible domain is always derived from the URL being opened, and is
   always shown.** Provider-supplied `title` text is untrusted and may not be
   the only visible label — a title reading "Official NVDA Filing" must never
   disguise where the link actually goes. Domain wins any conflict.
3. **Framing is descriptive, never endorsing.** These are the pages Argus read,
   not recommended reading. Argus surfacing a link is not a claim about the
   publisher.

URLs are already https-only and length-bounded at the sanitizer, so no new
validation is required — assert it rather than re-implement it.

### Tests

- Panel renders from persisted metadata only; zero network calls on open.
- Every rendered link carries `rel="noopener noreferrer"` and a visible domain
  matching the href's host; a fixture with a misleading title proves the domain
  still governs the visible label.
- Open/close, focus trap and restore, Escape and backdrop dismiss.
- Reload parity; EN + es-419 date formatting.

## 4. Slice B — Honest live progress for discovery (runtime event + frontend)

**Ships separately from Slices A and C.** Slice A/C are frontend-only and can
land as one PR. Slice B is blocked on three unresolved backend facts, verified
against integration `f66238a5` on 2026-07-27, none of which were known when
this spec was written:

1. **There is no channel for emitting a sub-stage event.** `stage_start` is
   synthesized in `runtime.py` from LangGraph `on_chain_start` events, filtered
   to `node_name in WORKFLOW_NODE_NAMES` and deduped by node name. Code inside a
   stage function — and the discovery composer sits several layers below the
   `interpret` node — has no way to push an event into that generator. This
   channel must be built (contextvar-backed queue, or a side channel merged into
   the `astream_events` loop) and must bypass both the node-name filter and the
   dedupe set. This is the bulk of the slice's cost and was previously described
   as "the existing runtime event stream mechanism."
2. **The provider Search call blocks the event loop.** `provider.search(...)` in
   `discovery/composer.py` runs a synchronous `httpx.Client` POST
   (`discovery_search/http_post.py`) inside an async coroutine, with no thread
   offload. While it runs, the SSE writer cannot be scheduled — so both progress
   lines would arrive together when the search returns, instead of streaming.
   The slice's entire premise fails until this call is offloaded. Fixing it also
   removes a latent concurrency problem unrelated to this lane: one discovery
   search currently stalls every other in-flight chat stream on that worker.
3. **The "unknown stages fall back to the neutral label" claim is false.**
   `ChatInterface.tsx` does
   `t(\`chat.status.${stage}\`) || t('chat.status.preparing')`, and `i18n.ts`
   sets no `parseMissingKeyHandler` or `returnEmptyString`, so i18next returns
   the missing key itself — truthy — and the fallback never fires. An older
   frontend receiving `discovery_search` renders the literal string
   `chat.status.discovery_search`. The fallback must be fixed for the
   additive-event compatibility claim to hold.

Also required: `web/lib/argus-api.ts` types the event as `{ stage: string }`;
`detail?: string` must be added.

### Behavior

- The discovery composer path (flag-on only) emits two additive sub-stage
  events through the existing runtime event stream while the interpret-stage
  turn is running:
  1. `stage_start` with `stage: "discovery_search"` and
     `detail: <human subject of the search>` — emitted immediately before the
     single provider Search call.
  2. `stage_start` with `stage: "discovery_verify"` — emitted before resolver
     validation of extracted candidates.
- **Display text is the human subject, not the raw machine query.** `detail`
  carries the localized-turn-language subject derived from the typed
  interpretation (`category_description`, else anchor symbols joined, else
  omitted). The deterministic provider query string is not shown to users; the
  event names the real subject of the real call without exposing machine query
  syntax.
- Frontend `stage_start` handling extends from
  `t("chat.status." + stage)` to pass `detail` as an interpolation variable.
  New keys (EN + es-419):
  - `chat.status.discovery_search` — "Searching the web — {{detail}}" (and a
    detail-less variant),
  - `chat.status.discovery_verify` — "Verifying candidates against supported
    markets".
  Unknown stages keep falling back to the neutral preparing label, so old
  frontends remain compatible (additive event, no contract break).
- Canon constraints (DESIGN.md §11) hold: events fire only when the work
  actually happens — no frontend timers, no events on the flag-off path, no
  events when the search is skipped (allowance exhausted / not configured).
  Recovery turns keep their existing behavior.

### Non-goals

- No rotating/multi-line carousel (single search — see §1).
- No persistence of progress lines; they are transient stream state, absent
  from hydration, exactly like today's stage labels.
- No new stage on the graph — these are sub-stage events inside interpret,
  emitted through the channel built per prerequisite 1 above.

### Tests

- Runtime unit tests: event emission order and payload on the flag-on path;
  zero discovery events on flag-off, not-configured, and allowance-exhausted
  paths; language of `detail` follows the detected turn language.
- Frontend unit tests: label mapping + interpolation, fallback for unknown
  stage values.
- Browser QA at implementation head: EN and ES discovery turns show
  search → verify lines advancing with real backend timing; non-discovery
  turns unchanged.

## 5. Slice D — Discovery selection carries resolved identity (runtime + frontend)

**Ships separately, after Slice A/C.** Founder-approved 2026-07-27; not in the
UI PR. Recorded here so the lane is not re-derived later.

### The problem

Tapping a discovery row sends the bare text `Backtest AKAM` and deliberately
passes no structured context — asserted today by
`tests/agent_runtime/discovery/test_discovery_selection_action.py`
(`test_runtime_receives_no_structured_action_context`). The interpreter then
re-derives everything from four words, including the asset identity that
`resolve_asset()` had just verified through the provider seconds earlier. PR
#276's own live QA records the cost: tap → "which supported direction?" →
"which dates?" → confirmation.

### The distinction that makes this safe

The existing rule — chips are prevalidated natural-language prompts, never
execution shortcuts (Grounded Discovery design §8) — forbids passing a
**prepared action**. It does not require discarding **identity**.

- **Identity** ("this is AKAM, Akamai Technologies, equity, resolver-verified")
  is what an `@ticker` mention already carries. It removes ambiguity about
  *which asset*. Safe, and the payload already holds it.
- **A prepared action** ("run this backtest with these parameters") would skip
  interpretation and confirmation. Still forbidden.

Interpretation, every deterministic guardrail, and the confirmation card all
stay exactly as they are. The turn saves the user from re-answering a question
Argus had already answered for itself.

### Behavior

- The `select_discovery_candidate` payload already carries `{symbol, name}`;
  extend it with the resolver-owned `asset_class` and consume it in the runtime
  as a mention-equivalent, not as an action context.
- **Standalone selection** (no active draft or result): Argus knows the asset,
  and asks once for what it genuinely lacks — strategy and dates. It must not
  ask which asset was meant.
- **Post-result / post-draft selection:** the existing artifact-continuity
  contract resolves the anchor (structured action payload → active confirmation
  → latest completed result) and patches only the asset; capital, dates,
  timeframe, benchmark, cadence, and strategy carry forward, landing directly on
  a corrected confirmation card.
- Strategy-parameter defaults are already applied on option selection
  (`normalize_indicator_parameters` in `interpreter/pending_option.py`) and need
  no change: selecting an RSI or crossover option fills period and thresholds
  from the indicator spec's declared defaults rather than asking.

### Carried into this slice: concurrent turns are not a UI concern

Slice A adds a shared `turnInFlight` lock so the composer, clarify rows, and
persistent discovery rows all stop accepting input while a turn runs. That lock
is **per-tab UI state**. It closes the accidental double-tap and the impatient
re-click, which is what it was built for. It does not close:

- two browser tabs open on the same conversation, each firing a turn;
- a replayed or scripted request that never renders the UI at all;
- a turn started in one tab while another tab is mid-stream.

None of that is discovery-specific — it is general chat-runtime concurrency, and
discovery rows only made it visible by being the first affordance that survives
outside the newest turn. Recorded here because Slice D is the backend-touching
slice in this lane, not because Slice D owns the problem: if the fix grows past
a conversation-scoped guard, it deserves its own issue rather than riding along.

Smallest credible shape: a conversation-scoped in-flight guard on the chat
endpoint that rejects or supersedes a second concurrent turn, consistent with
existing quota and supersession semantics. No UI change follows from it — the
frontend already renders backend truth.

### Why this needs proving, not assuming

The post-result path is the weakest-evidenced acceptance point in the whole
Grounded Discovery lane. No test asserts the carry-forward, and the recorded
live QA shows the clarify-heavy standalone shape. Design §8 originally
specified two chip texts ("Test CRWD with this setup" post-result vs "Backtest
CRWD" standalone); the two-variant idea was dropped during live QA when "Test"
was parsed as a strategy name, and only the verb was fixed. Whether continuity
carries today is unknown.

### Tests

- Selection with an active result patches only the asset; capital, dates,
  benchmark, timeframe, and strategy are unchanged and the turn reaches a
  confirmation card without a clarify round.
- Standalone selection never asks which asset was meant.
- Interpretation and confirmation still run on every selection turn; no path
  reaches execution without the card.
- Live eval: one discovery-selection case per continuity shape.

## 6. Documentation tasks in the lane

- `docs/API_CONTRACT.md`: document the two additive `stage_start` stage values
  and the `detail` field where stream events are specified (Slice B PR).
- `.agent/designs/argus/DESIGN.md` §11: add the two stage→label mappings to the
  stage table; record the pills-are-buttons / rows-are-next-moves distinction,
  the rest/hover row anatomy, and the exclusive-vs-menu resolution rule.
- `docs/superpowers/specs/2026-07-25-grounded-discovery-search-v1-design.md`:
  note that §6's no-outbound-links posture is superseded by Slice C.

## 7. Acceptance

**PR 1 — Slices A + C (every UI change; zero runtime change):**

1. No pill-styled conversational affordances remain in assistant messages;
   pills persist only on cards, starter prompts, and user action echoes.
2. Rows are borderless at rest, show a text-width hover/press wash, and keep a
   full-column ≥44px hit area independent of the visible box.
3. Discovery candidate rows show resolver-owned name and `reason_text` without
   tooltips; tapping sends the unchanged typed action; transcript hydration
   renders identically.
4. An answered clarify group stops rendering from backend-provided state;
   discovery candidate rows persist and stay tappable; both agree after reload.
5. The sources panel renders from persisted metadata with zero network calls;
   every link carries `rel="noopener noreferrer"` and a visible domain matching
   its href host.
6. No clipping at any string length, in LTR, RTL, and CJK fixtures; es-419
   parity for every new string.
7. Bounded diff: no runtime routing, quota, provider, or sidecar contract
   changes; pinned contract tests repinned deliberately, never weakened.

**PR 2 — Slice D (selection identity):**

8. A discovery selection never asks which asset was meant.
9. Selection with an active result or draft patches only the asset and reaches a
   confirmation card with capital, dates, timeframe, benchmark, and strategy
   intact.
10. Interpretation, guardrails, and the confirmation card still run on every
    selection turn.

**PR 3 — Slice B (live progress):**

11. The three prerequisites in §4 are resolved before the events land.
12. A flag-on discovery turn shows "Searching the web — {subject}" then
    "Verifying candidates…" advancing with real backend timing, driven solely by
    backend events; flag-off, not-configured, and recovery paths emit nothing new.
13. An older frontend receiving an unknown stage renders the neutral preparing
    label, not a raw key.

## 8. Explicitly deferred (research-arc backlog)

- Rendering the search *steps* inside the sources panel — only meaningful once
  the research arc genuinely runs multiple sequential searches.
- Real rotating activity trace once multiple sequential searches exist.
- Any personalization of suggestions.
