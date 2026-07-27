# Chat Polish: Stacked Next-Move Rows + Honest Live Progress

**Status:** FOUNDER-DIRECTED FOLLOW-UP — direction approved 2026-07-26; implementation not started.
**Owner:** Follow-up lane after PR #276 merges (branch from `codex/private-alpha-next`; if #276's merge is held, stack a child branch on `claude/grounded-discovery-release-9cc859` and review against it as parent).
**Parent context:** Grounded Discovery Search v1 (issue #244, PR #276), founder UI-taste review of 2026-07-26.
**Scope class:** Small full-slice polish lane. Frontend presentation + one additive runtime event surface. No API-contract breaks, no new tables, no new flags, no new provider calls.

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
- **Defer** the compact "N sources ›" drawer/panel to the research arc; the
  inline plain-text sources line is correctly sized for ≤5 unlinked sources.
- **Keep** pills for true buttons: card CTAs, starter prompts, the user's
  echoed action bubble.
- **Do not** copy open-ended engagement follow-ups ("Explore AI cybersecurity
  risks") — PRODUCT.md anti-pattern; Argus follow-ups stay typed and grounded.

## 2. Slice A — Stacked next-move rows (frontend only)

### Behavior

- New shared presentation (working name `NextMoveRow` list) in
  `web/components/chat/`: full-width, left-aligned rows; leading `↳` glyph
  (corner-down-right); ≥44px hit area; hover wash (`black/5`–`white/6`);
  staggered fade/slide-in per existing message motion; no borders between rows,
  optional 0.5px hairline above the group. Flat, zero shadows, muted palette —
  all per `.agent/designs/argus/DESIGN.md`.
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

### Non-goals

- No change to action payloads, `chat_action` persistence, hydration, or the
  `metadata.discovery` sidecar. Presentation only.
- No new i18n keys for candidates (`chat.discovery_results.test_candidate`
  stays); option labels remain backend/labelKey-driven.

### Tests

- Update pinned frontend contract assertions (`alpha-frontend.test.ts` pins on
  the current pill markup/`actionLabel` sites) to the row renderer.
- Row rendering unit tests: reason text visible, typed action fired with
  unchanged payload, composer-strip removal does not orphan gating.
- Browser QA (EN + es-419): clarify options under the message, candidate rows,
  hydration parity after reload, long Spanish labels un-truncated, 44px targets
  on mobile viewport.

## 3. Slice B — Honest live progress for discovery (runtime event + frontend)

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
  emitted via the runtime's existing event stream mechanism.

### Tests

- Runtime unit tests: event emission order and payload on the flag-on path;
  zero discovery events on flag-off, not-configured, and allowance-exhausted
  paths; language of `detail` follows the detected turn language.
- Frontend unit tests: label mapping + interpolation, fallback for unknown
  stage values.
- Browser QA at implementation head: EN and ES discovery turns show
  search → verify lines advancing with real backend timing; non-discovery
  turns unchanged.

## 4. Documentation tasks in the lane

- `docs/API_CONTRACT.md`: document the two additive `stage_start` stage values
  and the `detail` field where stream events are specified.
- `.agent/designs/argus/DESIGN.md` §11: add the two stage→label mappings to the
  stage table; record the pills-are-buttons / rows-are-next-moves distinction.

## 5. Acceptance

1. No pill-styled conversational affordances remain in assistant messages;
   pills persist only on cards, starter prompts, and user action echoes.
2. Discovery candidate rows show resolver-owned name and `reason_text` without
   tooltips; tapping sends the unchanged typed action; transcript hydration
   renders identically.
3. A flag-on discovery turn shows "Searching the web — {subject}" then
   "Verifying candidates…" driven solely by backend events; flag-off and
   recovery paths emit nothing new.
4. EN + es-419 parity for every new string; frontend + backend suites green;
   pinned contract tests repinned deliberately, never weakened.
5. Bounded diff: no runtime routing, quota, provider, or sidecar contract
   changes.

## 6. Explicitly deferred (research-arc backlog)

- "N sources ›" affordance opening a side evidence panel (renders the archived
  `metadata.discovery` trail; revisit outbound-link policy then — plain text
  today is an injection-hardening decision).
- Real rotating activity trace once multiple sequential searches exist.
- Any personalization of suggestions.
