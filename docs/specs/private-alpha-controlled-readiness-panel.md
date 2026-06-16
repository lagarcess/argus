# Private Alpha Controlled Readiness Panel

**Status:** Draft technical panel report
**Date:** 2026-06-12
**Branch:** `codex/private-alpha-next`
**Purpose:** Define what must be true before Argus is placed in the hands of a
small controlled alpha cohort, especially Spanish-first users.

This report is the technical readiness counterpart to the evidence-aware idea
loop product trial. The product trial asked what behavior Argus must prove. This
panel asks what can hurt users, corrupt the learning signal, or damage trust
before those users test the product.

Related addendum:

- [`private-alpha-performance-readiness-audit.md`](./private-alpha-performance-readiness-audit.md)
  captures the read-only performance panel findings and the measurement-first
  speed gates for controlled alpha.

## Executive Verdict

Argus should not open public guest mode yet.

Argus can plausibly reach a 5-6 named-user controlled alpha quickly, but only
after a focused readiness slice. The slice should not become an enterprise
compliance or infrastructure rewrite. It should close the highest-risk gaps that
would make the user test invalid or unsafe:

1. Spanish backend execution must work end to end.
2. Backtest results must be simple but reproducible and honestly described.
3. Auth, tenant ownership, feedback, and rate-limit surfaces need alpha-grade
   hardening.
4. Terms, Privacy Policy, and explicit alpha consent must be real, linked, and
   truthful.
5. Render workflow mode must be verified by canary before every tester window.
6. Product analytics must start privacy-first; Supabase feedback remains the
   durable user-listening source, and PostHog must not receive raw prompts,
   transcripts, result cards, or sensitive financial context.

The operating answer is:

> Controlled alpha after readiness slice. Public/guest mode after a separate
> public-readiness gate.

## Decision Gate

### Controlled Alpha Gate

This gate is for 5-6 named, trusted users. It assumes:

- users are allowlisted;
- users are adults;
- the founder can observe and support sessions;
- expected traffic is low;
- data can be manually inspected for debugging with disclosure;
- backtests can take around a minute while the workflow path is stabilized;
- product analytics can be lightweight and privacy constrained.

Controlled alpha should be blocked by:

- Spanish prompts cannot produce executable backtests;
- Terms/Privacy links are dead;
- the app cannot prove real workflow mode and a passing canary before sessions;
- feedback can persist arbitrary client context without caps/redaction;
- obvious cross-tenant parent-ID writes are possible through service-role
  backend paths;
- result persistence cannot support a reasonable reproducibility story.

### Public Guest Mode Gate

This gate is later. It requires:

- full abuse/rate-limit posture across anonymous sessions, IP/session/user
  quotas, and expensive actions;
- deeper security scan and attack-path analysis;
- privacy policy and analytics consent designed for unknown users;
- guest throttling and signup wall tested for privacy and user experience;
- operational monitoring and alerting;
- public-mode latency and concurrency benchmarks;
- support and deletion processes that do not rely on founder improvisation.

## Readiness Slice Recommendation

The readiness slice should be sequenced like this:

1. **Spanish backend execution**
   - Multilingual interpreter contract.
   - Canonical machine values from Spanish input.
   - Spanish date/timeframe/indicator normalization after LLM interpretation.
   - Spanish result, clarification, unsupported-boundary, and follow-up voice.
   - Current checkpoint: the readiness worktree now has focused backend tests
     proving the messy English/Spanish buy-and-hold shape with shorthand
     capital (`100k`) can reach a confirmation card with canonical
     `capital_amount=100000`, localized shell/card copy, compact localized date
     ranges, and no hard recovery. Latest Codex browser QA also proved the
     English `Change dates -> calendar 2024` path updates the active card to
     `Jan 1, 2024 -> Dec 31, 2024` instead of silently confirming the prior
     rolling range, and the Spanish `Cambiar fechas -> calendario 2024` path
     updates the active card to `1 ene 2024 -> 31 dic 2024` instead of leaking
     macro-context prose. The same browser pass now covers English
     `Change asset -> make it google instead` and Spanish
     `Cambiar activo -> ponlo con google mejor`, both updating the active card
     to provider-canonical `GOOGL` while preserving capital, period, and
     benchmark. A follow-up Spanish browser pass also proved
     confirmation -> run -> result card -> Quick take -> Explain result ->
     Refine idea -> messy refinement -> new confirmation -> cancel. That pass
     preserved Spanish runtime voice, canonical `GOOGL`, `$50,000`, a rolling
     six-month window, compact localized date ranges, and structured
     cancellation. A final local browser QA pass found and fixed two artifact
     locale leaks: Spanish quick takes no longer expose English optional-field
     labels such as `Initial capital` / `Timeframe`, and Spanish RSI
     confirmation cards render structured buy/sell rules in Spanish instead of
     raw internal English rule prose. The broader Spanish transcript matrix
     also passes locally for DCA, missing DCA amount clarification, mixed-asset
     clarification, currency-pair confirmation, unsupported valuation recovery,
     and localized artifacts. Browser recovery proof now covers Spanish
     unsupported valuation (`P/E`) -> supported proxy clarification -> messy
     RSI follow-up -> executable ETH confirmation. This is local runtime-spine
     proof, not the full Spanish release gate.

2. **Backtest trust hardening**
   - Provider-backed symbol validation even when `asset_class` is explicit.
   - Execution/chart/metric parity tests.
   - DCA wording and config clarity.
   - Persisted `config_snapshot` reproducibility.
   - Benchmark coverage and missing-data tests.

3. **Security and tenant hardening**
   - Production secure cookies. Closed locally in the readiness branch:
     browser-session cookies now force `Secure` when the request is HTTPS, when
     `x-forwarded-proto` is HTTPS, or when `APP_ENV`/related backend env marks a
     production-like deployment.
   - Allowlist/auth response normalization and throttling. Closed locally for
     public login failures, raw signup provider errors, and short-window
     login/signup attempt limits keyed by IP and normalized email.
   - Short-window quotas and accurate rate-limit behavior. Closed locally for
     authenticated chat, backtest, and feedback paths. Auth attempts use a
     separate in-process limiter because unauthenticated login/signup attempts
     cannot use the current `usage_counters.user_id` model before a user exists.
   - Parent ownership checks for service-role write paths. Closed locally in
     the readiness branch for direct backtest parent conversations, gateway
     backtest run parents, direct strategy parent conversations, durable job
     conversations, collection-strategy parents, and context-packet run
     attachments.
   - Feedback caps and context schema.

4. **Legal/privacy/consent**
   - Terms page.
   - Privacy Policy page.
   - Explicit alpha consent at signup or invite acceptance.
   - Adult-only boundary.
   - Real support/deletion contact.

5. **Workflow/SRE gate**
   - Render env drift check.
   - Warmup.
   - Canary.
   - Supported golden-path smoke.
   - Stale job monitoring.

6. **Analytics/feedback**
   - Supabase feedback verification.
   - Privacy-first PostHog event plan, postponed for this solo readiness pass
     and still disabled until founder-approved configuration.
   - Minimal loop metrics for the controlled study.

7. **UX research readiness**
   - Natural, current cold-start prompt slate.
   - Founder-led test script.
   - Spanish-first prompt set.
   - Success criteria and observation sheet.

## Must Fix Before Controlled Alpha

| Area | Must fix | Why it matters |
| --- | --- | --- |
| Spanish execution | Spanish natural language must reach the same executable interpreter and backtest path as English. Focused local proof exists for messy buy-and-hold prompts with shorthand capital, and the broader Spanish/runtime matrix passed locally on 2026-06-15. | Most controlled users prefer Spanish; static UI translation without execution breaks the core promise. |
| LLM runtime | Interpreter prompt/schema must state: any input language in, canonical machine values out, user-facing prose in resolved language. The current readiness work keeps user phrasing as evidence and asks focused audits to reconcile canonical fields when the primary pass preserved meaning only in prose. | Prevents Spanish values like `mensual`, `acciones`, or `comprar_y_mantener` from leaking into executable fields while also preventing lost user-stated facts such as `100k`. |
| Dates/timeframes | Date/window handling should use canonical `date_range_intent` and bounded evidence spans after LLM interpretation, not runtime-owned language tables. | Date and timeframe repair must scale beyond English/Spanish without adding phrase gates before the interpreter. |
| Backtest symbols | Explicit `asset_class` must narrow validation, not bypass provider-backed canonical asset resolution. | Prevents invalid or misclassified symbols from entering a run. |
| Backtest parity | Metrics, chart markers, fills, and stored run facts need parity tests against one coherent execution model. | Result cards are the trust surface. They must not disagree with engine truth. |
| Run persistence | `config_snapshot` should be sufficient to reproduce the run's assumptions and execution config. | Reload/history claims depend on durable reproducibility. |
| Terms/Privacy | Replace dead `#` Terms/Privacy links with real pages. | Users need clear disclosure before providing prompts, feedback, and account data. |
| Alpha consent | Add explicit acceptance of Terms/Privacy and no-advice/historical-simulation alpha terms. | Controlled alpha still involves sensitive user data and financial ideas. |
| Support/deletion | Configure real support email and manual account deletion path. | Current fallback support address is not user-ready. |
| Secure cookies | Verify deployed auth cookies are `HttpOnly`, `Secure`, and `SameSite=Lax`; force secure in production if proxy scheme is ambiguous. | Session security cannot depend on internal proxy scheme detection. |
| Allowlist auth | Normalize private-alpha login/signup errors enough to reduce allowlist enumeration. | Avoid exposing who is invited. |
| Rate limits | Add or verify short-window chat/backtest/auth/feedback throttles and accurate `429`/`Retry-After`. | Protects cost, trust, and small-alpha stability. |
| Tenant ownership | Add app-level ownership checks before service-role writes that accept parent IDs. | Service-role backend paths must preserve tenant boundaries. |
| Feedback privacy | Cap feedback payloads, schema context, and redact URL query strings. | Feedback should help us learn without collecting accidental secrets. |
| Workflow mode | Require real workflow dispatch/execution config and green warmup/canary before sessions. | Prevents in-process heavy execution or hidden workflow drift. |
| Confirmation action I/O | Resolved locally on `codex/private-alpha-readiness-clean`; [GitHub issue 112](https://github.com/lagarcess/argus/issues/112) should close after merge. Valid confirmation actions now reuse one recent-message read before entering runtime. | This remains a latency-sensitive action path that owns stale-confirmation guardrails, so the focused regression coverage must stay green. |
| Cold-start prompts | Replace stale exact-date starter chips/placeholders with natural rolling-window examples in English and Spanish. | Exact 2024 examples make Argus feel brittle and outdated, and they teach users that imprecise natural prompts may break the product. |

## Acceptable With Disclosure For Controlled Alpha

- No fees, slippage, liquidity, order queue, spreads, tax impact, or execution
  realism, as long as the app visibly says so.
- Backtests may take around a minute while the Render Workflow path is being
  hardened.
- Manual account deletion and support, as long as users are told the process.
- Persistent conversations, messages, backtest runs, route receipts, and
  feedback, as long as the Privacy Policy says this plainly.
- Founder/admin debugging access to alpha records, if limited to support,
  QA, and product learning, and disclosed.
- Static Spanish UI can continue to improve, but backend execution in Spanish
  cannot be deferred for Spanish-first users.
- PostHog can remain disabled during first sessions while Supabase records,
  route receipts, logs, and founder notes cover learning.

## Defer Until Public/Guest Mode Or Later

- Guest mode and anonymous usage quotas.
- Public excerpts or share links.
- PostHog session replay.
- Brokerage integrations.
- Paid monetization.
- Monitoring/alerts as a product feature.
- Deep Perplexity Research Lab implementation.
- RAG/vector memory.
- Portfolio analytics.
- Mobile native app.
- Full privacy portal, automated export, automated deletion, SOC 2, DPIA-style
  documentation, or a state-law compliance matrix.
- Full `codex-security:deep-security-scan`, unless public/guest mode moves
  earlier than expected.

## Lane Report: LLM Runtime And Spanish Execution

### Verdict

Argus now has local Spanish-first runtime proof, but it still needs deployed
Render canary proof before first tester sessions. The main runtime gap has moved
from architecture risk to deployment/live-provider verification risk. The
runtime shape is correct: LangGraph is the
conversational spine, normal language reaches structured interpretation first,
and deterministic validation comes afterward. The readiness branch now has
local work for canonical interpreter metadata, natural-time normalization,
registry-backed strategy aliases, localized artifacts, structured recovery, and
a focused capital-fidelity audit that catches when the LLM preserves `100k`
only in draft prose instead of the canonical field. The local Spanish/runtime
matrix passed on 2026-06-15; the remaining gap is proving the same shape against
live provider/auth/browser conditions in the production-like Render canary.

### Evidence

- The interpreter now receives language preference and carries language,
  bounded date text, and evidence-span metadata while asking for canonical
  Argus machine values. The local tests cover this shape, and focused Codex
  browser QA now proves the messy buy-and-hold `100k` prompt in both Spanish and
  English reaches the localized confirmation-card state with `$100,000` instead
  of the default `$1,000`.
- Browser evidence captured locally:
  `language-spine-es-locale-capital-1781420400003` / conversation
  `4bd063f3-0558-4dfd-948b-39fb15565b2b` and
  `language-spine-en-locale-capital-1781420600004` / conversation
  `d95cc988-ae94-4ed0-8686-c2f09e1711d1`. This is not a production Render
  canary.
- Run-critical fields such as `strategy_type`, `asset_class`, `timeframe`,
  `cadence`, `indicator`, and `date_range` still need strict guardrails because
  they can arrive from a probabilistic model before deterministic validation.
- Date and window repair now resolves canonical `date_range_intent` from the
  interpreter first, and only sends bounded evidence spans through
  `argus.nlp.natural_time`. It no longer uses localized whole-turn phrase
  scanning as a shortcut around the LLM. Relative endpoint edits use canonical
  offset math such as `anchor=today` plus `day_offset=-1`, not localized
  relative-date strings. Timezone/data-availability behavior still needs live
  QA.
- Strategy families and DCA cadence now rely on canonical interpreter output;
  localized source wording stays in evidence spans/prose, and the capability
  registry is no longer a natural-language phrasebook in English, Spanish, or
  future languages. The secondary field-fidelity audit
  path also validates cadence through the canonical cadence set, so it cannot
  write localized cadence prose into executable state. Indicator and signal-rule
  interpretation remains the biggest Spanish-language execution risk.
- Result/card copy, compact dates, asset-class labels, and recoverable runtime
  fallback copy have local Spanish coverage. The full chat flow still needs
  live provider/auth/browser proof in the deployed Render environment.

Relevant code:

- `src/argus/agent_runtime/llm_interpreter.py`
- `src/argus/agent_runtime/llm_interpreter_types.py`
- `src/argus/agent_runtime/strategy_contract.py`
- `src/argus/agent_runtime/run_field_contract.py`
- `src/argus/domain/strategy_capabilities.py`
- `src/argus/domain/indicators.py`
- `src/argus/agent_runtime/signal_rule_repair.py`
- `src/argus/agent_runtime/llm_clarifier.py`
- `src/argus/agent_runtime/response_style.py`
- `src/argus/agent_runtime/stages/explain.py`
- `src/argus/agent_runtime/recovery_messages.py`
- `src/argus/api/chat/confirmation.py`

### Design Requirements

- Keep LLM-first interpretation. Do not add Spanish regex gates before the
  interpreter.
- Make the interpreter contract explicit:
  - user input may be Spanish or English;
  - executable fields must use canonical English/internal enum values;
  - user-facing copy must use the resolved `language_preference`;
  - unsupported ideas must be explained naturally in the user's language.
- Strengthen field descriptions or schema so raw localized values cannot become
  executable values unless normalized after interpretation.
- Extend deterministic normalization after interpretation for dates,
  timeframes, cadences, strategy families, and common indicator names without
  reintroducing language phrase gates. Relative or semantic date language should
  become canonical `date_range_intent`; bounded date spans belong behind
  `argus.nlp.natural_time`; Argus-domain capability registries should describe
  canonical/internal execution concepts, not grow English or locale phrase
  tables.
- Closed locally in the readiness branch: natural date/window interpretation now
  uses canonical temporal intent or bounded evidence through
  `argus.nlp.natural_time`, and runtime strategy canonicalization now keeps
  natural-language strategy/cadence wording out of the capability registry
  instead of growing duplicate alias tables inside runtime contracts.
- Closed locally in the readiness worktree: recoverable runtime failures now use
  typed recovery codes, normalized recovery language, centralized localized
  fallback copy, and structured `retry_last_turn` metadata. This must remain a
  fallback safety layer, not a replacement for normal LLM-owned Argus voice.
- Closed locally in the readiness worktree for the first supported messy shape:
  if a live LLM turn captures a user-stated capital amount in strategy prose but
  fails to populate `capital_amount`, the focused starting-capital audit receives
  the raw user phrasing and draft-prose evidence before deciding whether to
  restore the canonical amount. This preserves LLM-first interpretation without
  adding language phrase gates or chip-specific shortcuts.
- Keep hard constraints in schema, code, or runtime parameters instead of vague
  prose, following the same discipline described in Perplexity's prompt guide:
  focused instructions, clear formatting, grounding, JSON schema where
  machine-readable output is required, and explicit constraints.

### Spanish Execution Test Matrix

| Prompt | Expected behavior |
| --- | --- |
| `Compra y manten Tesla desde enero de 2021 hasta diciembre de 2024` | Buy-and-hold, `TSLA`, equity, ISO date range, no clarification. |
| `Quiero comprar 100 dolares de BTC cada mes durante 2024` | DCA, `BTC`, crypto, monthly cadence, recurring amount 100, 2024 range. |
| `Haz un backtest de Apple contra QQQ en 2023` | `AAPL` asset, `QQQ` benchmark, benchmark excluded from asset universe. |
| `Compra Ethereum semanalmente desde 2022 hasta hoy` | `ETH`, weekly DCA, preserve start/end, clarify missing recurring amount in Spanish. |
| `Prueba GOOG con RSI: compra debajo de 30 y vende arriba de 60 en los ultimos 6 meses` | RSI threshold rule, thresholds 30/60, relative six-month range. |
| `Compra NVDA cuando la media movil de 50 dias cruza arriba de la de 200 dias, ultimo ano` | Moving-average crossover, SMA 50/200 bullish entry, past-year range. |
| `Prueba BTC y Tesla juntos el ano pasado` | Mixed asset classes rejected or clarified in Spanish; offer separate runs. |
| `Usa velas de 1 hora para EUR/USD durante los ultimos 30 dias` | Currency pair, 1h timeframe, last 30 days, provider availability validated. |
| `Si, ejecutalo` after confirmation | Approval turn, preserve prior strategy, route to execution. |
| `Por que perdio contra SPY?` after result | Result follow-up, no new draft, answer from latest run facts. |
| `Cambia el activo a Nvidia` during pending setup | Patch asset to `NVDA`, preserve dates/cadence/capital. |
| `Compra cuando se vea barato por P/E` | Unsupported valuation idea; Spanish recovery with supported proxies, no invented execution. |

### Implementation Notes

This lane belongs to Codex/runtime work, not Jules. It touches the interpreter,
LangGraph stages, prompt/schema boundaries, and execution guardrails.

## Lane Report: Quant And Backtesting

### Verdict

Yellow, not red. The current engine is mostly the right Alpha shape: simple,
long-only, equal-weight, same-asset, beginner-readable, and honest about no
fees/slippage. Do not port `archive-v0.1` wholesale. Do run a short trust pass
before controlled alpha.

### Current Support

The current engine supports:

- allowed templates and timeframes;
- default benchmarks: equity -> `SPY`, crypto -> `BTC`, currency pairs -> the
  tested pair;
- stablecoin rejection;
- provider/date-window validation;
- long-only runs;
- equal-weight multi-symbol runs;
- 1-5 symbols;
- same-asset-class constraints;
- buy-and-hold, DCA, RSI/rule-spec, moving-average crossover, momentum
  breakout, trend follow, and buy-the-dip;
- high-level metrics such as return, benchmark delta, profit, annualized return,
  max drawdown, volatility, win rate, profit factor, Sharpe, and trade count;
- aggregate portfolio equity charts and fill-derived markers.

Relevant code:

- `src/argus/domain/backtesting/config.py`
- `src/argus/domain/backtesting/runner.py`
- `src/argus/domain/backtesting/execution.py`
- `src/argus/domain/backtesting/signals.py`
- `src/argus/domain/backtesting/metrics.py`
- `src/argus/domain/backtesting/charts.py`
- `src/argus/domain/engine_launch/adapter.py`
- `src/argus/domain/backtest_run_builder.py`

### Trust Risks

#### Explicit Asset Class Can Bypass Canonical Resolution

Launch requests can bypass provider-backed symbol classification when
`asset_class` is present and return uppercased user symbols directly. For
controlled alpha, explicit asset class should narrow validation, not replace
canonical provider-backed resolution.

Action:

- Closed locally in the readiness branch: tests now prove explicit
  `asset_class` still canonicalizes symbols and rejects provider class
  conflicts.
- Closed locally in the readiness branch: launch resolution now classifies
  symbols through the provider-backed resolver first, then treats selected or
  explicit `asset_class` as a constraint rather than a bypass.

#### Multiple Execution Truths

Metrics build a ledger, vectorbt executes from raw signals, and chart generation
can refetch/recompute. Existing ledger tests are useful, but controlled alpha
needs parity tests proving displayed fills, trade counts, and equity curves come
from one coherent execution model.

Action:

- Closed locally in the readiness branch: `tests/domain/test_engine_execution_ledger.py`
  proves exits while flat are ignored, duplicate full-position entries are not
  double-counted, same-bar exit/reentry marker order is deterministic, DCA
  accumulation records repeated buy fills, chart markers come from executed
  fills rather than raw signals, and metrics trade counts use the execution
  ledger.
- Closed locally in the readiness branch: persisted run snapshots deep-copy
  chart markers into stored `trades`, keeping stored trade facts aligned with
  the executed-fill chart payload.

#### DCA Semantics Are Overloaded

DCA currently overloads `starting_capital` as recurring contribution in the
launch adapter. This is acceptable only if DCA is visibly described as
recurring contribution only, with no starting principal or investment ceiling,
until first-class DCA semantics land.

Action:

- Closed locally in the readiness branch: DCA result cards now make recurring
  contribution, cadence, and zero starting principal explicit in English and
  Spanish assumptions, and the launch envelope reuses those card assumptions.
- Closed locally in the readiness branch: DCA total-budget, starting-principal,
  cap, and recurring-contribution roles are separated by semantic audits and
  regression coverage; unsupported total-principal context clarifies instead of
  becoming the executable recurring amount.

#### Config Snapshot Reproducibility

Workflow-built run snapshots are reduced and do not yet prove they are the exact
normalized engine config. Persisted `trades` may be chart markers rather than a
full execution ledger.

Action:

- Closed locally in the readiness branch: launch envelopes carry the normalized
  engine config used for metrics, runtime persistence freezes that
  `engine_config`, and
  `test_persisted_config_snapshot_replays_key_metrics` now proves a persisted
  run can replay key aggregate metrics from `config_snapshot.engine_config`
  against the same deterministic data.

#### Benchmark Alignment

Benchmark construction uses forward/back fill. This can hide missing benchmark
coverage at the start of a period.

Action:

- Closed locally in the readiness branch: `build_benchmark_curve` rejects late
  benchmark starts, sparse benchmark observations, and uncovered aligned
  points instead of silently future/back-filling missing benchmark coverage.
  The coverage tests live in `tests/section3/test_engine_simulation.py`.
- Closed locally on 2026-06-16: chat launch now maps
  `benchmark_data_unavailable` to the same retryable upstream dependency family
  as market-data coverage failures. `RealBacktestTool` returns a user-safe
  benchmark-data message/detail, and execute recovery preserves the visible
  setup while offering retry/date/benchmark adjustment instead of surfacing an
  internal failure.

### Archive v0.1 Findings

Salvage:

- reality-gap sensitivity as an internal audit idea;
- sparse-calendar and NaN stability tests;
- warm/cold latency discipline;
- small cross-engine sanity comparisons for zero-fee long-only cases.

Reject for Alpha:

- Execution Forge controls;
- stop-loss/take-profit;
- participation-rate sizing;
- volatility-adjusted slippage;
- fidelity scores;
- harmonic/pattern confluence;
- trading-terminal metrics.

Those features would make Argus look sophisticated while increasing false
precision and scope.

### External Context

SEC materials treat backtested performance as hypothetical and warn it can
mislead through hindsight optimization, while acknowledging it can help users
understand how a strategy might have performed historically. That supports the
Argus alpha posture: simple historical simulation is acceptable when clearly
disclosed as educational and hypothetical.

## Lane Report: Security

### Verdict

Argus is directionally close for a small named-user controlled alpha, but not
ready until several auth, quota, tenant-integrity, and feedback/privacy gaps are
fixed or explicitly accepted. This was not a formal `codex-security:deep-security-scan`;
it used the security plugin's attack-path mindset for readiness triage.

### Must Fix

#### Auth Cookie Secure Flag

Auth cookies are set with `secure=request.url.scheme == "https"`. In a Render
proxy deployment, internal scheme detection may be ambiguous unless proxy
headers are trusted or production forces secure cookies.

Action:

- Force secure cookies in production. Closed locally in the readiness branch.
- Verify deployed `Set-Cookie` contains `HttpOnly`, `Secure`, and `SameSite=Lax`.

Relevant code:

- `src/argus/api/dependencies.py`
- `render.yaml`

#### Private-Alpha Allowlist Enumeration

Login/signup could reveal differences between unlisted emails and listed emails
with wrong passwords. Signup could also return raw provider exception text.

Action:

- Closed locally: login returns the same generic `401 unauthorized` response for
  unlisted/disabled private-alpha emails and listed emails with wrong
  passwords, while still avoiding Supabase Auth calls for unlisted/disabled
  emails.
- Closed locally: signup returns the same generic `400 auth_signup_failed`
  response for unlisted/disabled private-alpha emails and provider signup
  failures, while still avoiding Supabase Auth calls for unlisted/disabled
  emails and never returning raw provider exception text.
- Closed locally: login/signup attempts now use a separate short-window limiter
  keyed by client IP and normalized email, with `429` and `Retry-After` before
  provider or allowlist work after repeated attempts.
- Keep detailed reasons in logs only.

Relevant code:

- `src/argus/api/routers/auth.py`

#### Rate Limits

The readiness branch now removes misleading static rate-limit headers and
enforces short-window plus daily Supabase usage counters for authenticated chat,
backtest, and feedback paths. `429` responses include `Retry-After`.

Action:

- Closed locally: chat messages enforce 200/day and 60/hour.
- Closed locally: direct backtests enforce 50/day and 10/hour.
- Closed locally: feedback submissions enforce 50/day and 20/hour before
  persistence.
- Closed locally: success responses no longer emit placeholder
  `X-RateLimit-*` values.
- Closed locally: login/signup attempts use a separate in-process limiter rather
  than the authenticated per-user `usage_counters` model.

Relevant code:

- `src/argus/api/dependencies.py`
- `src/argus/api/routers/agent.py`
- `src/argus/api/routers/backtest.py`
- `src/argus/api/routers/feedback.py`
- `src/argus/domain/supabase_gateway.py`

#### Service-Role Parent Ownership

The backend intentionally uses a Supabase service-role client. That makes
application ownership checks critical for write paths that accept parent IDs.

Action:

- Validate conversation ownership before backtest or strategy writes that attach
  to a conversation. Closed locally for direct backtest execution and gateway
  backtest run/job inserts.
- Validate collection ownership before collection-strategy upserts. Closed
  locally in the gateway before any upsert.
- Add cross-user IDOR tests. Closed locally for the gateway service-role parent
  boundary and direct backtest route.

Relevant code:

- `src/argus/api/routers/backtest.py`
- `src/argus/api/routers/collections.py`
- `src/argus/domain/supabase_gateway.py`

#### Feedback Payload Caps And Scrubbing

Feedback accepts client-provided context and the frontend includes the full
current URL. Query strings can include sensitive tokens or internal QA markers.

Action:

- Add message and context size caps.
- Schema allowed context keys.
- Redact URL query/hash before persistence.
- Add per-user feedback quotas.

Relevant code:

- `src/argus/api/schemas.py`
- `src/argus/api/routers/feedback.py`
- `web/components/feedback/FeedbackDialog.tsx`

#### Terms/Privacy Disclosure

Dead Terms/Privacy links are a security and trust readiness issue, even if not
a code exploit.

Action:

- Replace dead links with real pages before inviting users.

### Attack Paths To Prove Closed

- Enumerate invitees through `/auth/login`.
- Capture deployed auth cookies and inspect flags.
- Burst `/chat/stream`, `/backtests/run`, and `/feedback` from a valid alpha
  account.
- Attempt cross-tenant writes by referencing another user's conversation,
  strategy, collection, job, or run IDs.
- Verify `/api/v1/dev/reset` is unavailable in production.
- Verify admin downgrade removes `is_admin`.

### Deep Scan Recommendation

Run a formal `codex-security:deep-security-scan` before public beta, guest mode,
public excerpts, or broad PostHog activation. For named-user controlled alpha,
the focused security readiness slice is the faster path.

## Lane Report: Privacy, Legal, And Consent

### Verdict

For named, trusted, US-based controlled alpha, Argus does not need enterprise
privacy machinery before first users. It does need a real minimum posture:

- Terms;
- Privacy Policy;
- explicit alpha consent;
- adult-only use;
- clear no-advice language;
- manual deletion/support process;
- retention stance;
- PostHog kept off until intentionally configured.

This report is not legal advice.

### Repo Facts

Argus is explicitly educational and sandbox-oriented. Real brokerage trading is
out of scope. However, the sensitive data footprint is real:

- profiles;
- conversations;
- messages;
- generated titles;
- backtest configs/results/charts/trades;
- feedback;
- account deletion requests;
- usage counters;
- route receipts/model metadata;
- logs;
- cookies and session storage;
- optional analytics later.

Good controls already exist:

- private-alpha allowlist is service-role only;
- user-owned tables have RLS policies;
- LangGraph checkpoint tables are revoked from browser roles and RLS-enabled.

Current legal UX is incomplete:

- signup links point to `#`;
- profile/help terms/privacy buttons are disabled;
- settings/about rows do not route to real documents.

### Minimum Adequate Posture

Before inviting users:

- Publish Terms and Privacy Policy pages in-app and from signup/settings.
- Provide Spanish versions or Spanish plain-language summaries for Spanish-first
  testers.
- Add clickwrap consent at signup or invite acceptance:
  - agree to Terms and Privacy Policy;
  - understand Argus is educational;
  - understand historical simulations are not predictions;
  - understand Argus does not provide investment advice or brokerage services;
  - confirm adult use.
- Identify the operator. If there is no company, do not imply one. For more
  than close friends, consider forming an LLC or corporation before collecting
  real user data because business structure affects liability and legal
  protections.
- Configure a real support email and deletion intake.
- Keep PostHog disabled until privacy settings and consent are configured.

### Terms Should Cover

- educational use only;
- no investment, tax, or legal advice;
- no adviser-client or fiduciary relationship;
- no brokerage or trade execution;
- historical simulations are hypothetical and not predictions;
- data may be wrong, incomplete, delayed, or unavailable;
- no reliance for live trading;
- alpha instability;
- acceptable use;
- account termination;
- user content and product IP;
- support/deletion process.

### Privacy Policy Should Cover

- what data Argus collects;
- why it collects the data;
- how long it keeps data, at least at a high level;
- who processes data: Supabase, Render, OpenRouter/model providers, market data
  providers, and PostHog if enabled;
- manual support/deletion process;
- founder/admin access for support, debugging, and product learning;
- analytics status and opt-out/consent model;
- no sale of personal data if that is true;
- contact information.

Do not promise that prompts never leave Argus infrastructure. OpenRouter/model
providers process prompts and outputs, and provider terms can vary by model.

### What Not To Collect

Avoid collecting:

- SSNs;
- government IDs;
- date of birth;
- phone numbers;
- home addresses;
- precise geolocation;
- bank or brokerage credentials;
- account balances;
- holdings;
- net worth;
- income;
- tax facts;
- risk-tolerance questionnaires;
- suitability/profile data;
- screenshots containing brokerage or financial-account details.

Treat prompts and investing ideas as sensitive personal data even if they are
not regulated account data.

### Policy Generator Recommendation

For a founder alpha, a policy generator is acceptable as a draft starter, not as
final legal assurance. TermsFeed and PrivacyPolicies.com are practical starting
points because they provide privacy/terms generators and templates with clear
no-legal-advice caveats.

Manual Argus-specific additions are required for:

- AI prompt processing;
- historical simulations;
- no financial advice;
- no brokerage;
- OpenRouter/model provider processing;
- PostHog disabled/enabled status;
- route receipts and model metadata;
- retention and deletion;
- Spanish-first users.

## Lane Report: SRE, Performance, And Traffic

### Verdict

Argus is conditionally ready for 5-6 named users only behind a strict
real-workflow-mode plus passing-canary gate. It is not ready for public/guest
traffic.

### Current Posture

The main operational risk is not ordinary FastAPI traffic. It is:

- backtest job concurrency;
- cold-start latency;
- workflow dependency/tool load;
- provider latency;
- result-readout latency;
- workflow execution reliability;
- environment drift.

The architecture is viable if heavy backtest imports remain out of API startup
and execution goes through Render Workflows. The repo has import-boundary tests
that protect API startup from pandas/numpy/vectorbt/backtest-heavy imports.

Recorded evidence from the capacity spec is acceptable for controlled alpha:

- API `/health` around 124 MB RSS;
- API import peak around 134.4 MB;
- no forbidden heavy modules in the API readiness path;
- workflow import/backtest path around 299-412 MB RSS depending on case;
- one real workflow canary around 55s total, with roughly 14s load, 33s
  backtest, and 6.7s result readout.

Backpressure exists:

- 1 running job per user;
- 2 queued jobs per user;
- 5 running global;
- 10 queued global.

Issue 112 is resolved locally on `codex/private-alpha-readiness-clean` and
remains open on GitHub until the branch is merged. Valid confirmation actions
share one recent-message read between stale-confirmation validation and
confirmation metadata fallback, while stale confirmation actions still stop
before runtime.
Fresh local proof on 2026-06-16:
`tests/test_chat_runtime_reload_guardrails.py::test_valid_confirmation_action_reuses_recent_messages_for_metadata_fallback`,
`tests/test_chat_runtime_reload_guardrails.py::test_stale_confirmation_action_id_does_not_execute`,
and `tests/test_chat_runtime_reload_guardrails.py::test_canceled_confirmation_blocks_stale_checkpoint_run_action`
passed together.

### Must Fix Or Verify Before Testers

- Verify `ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=true` in the deployed API.
- Verify workflow dispatch is enabled and real task ID is configured.
- Run warmup and canary before every tester window.
- Fail canary if result readout falls back instead of using the LLM explain
  stage.
- Keep issue 112 focused tests green until merge, then close the GitHub issue.
- Run focused import-boundary, workflow, async job, canary, readiness, and
  runtime compatibility tests.
- Set tester expectations: backtests may take around a minute.

### Suggested Targets

- Chat first event: p95 under 3s once warm.
- Keepalive: no slower than 15s.
- Interpretation/confirmation: controlled alpha p95 under 45s, hard failure
  before 120s.
- Run-action to queued job response: p95 under 5s.
- Workflow queued-to-started: p95 under 20s.
- Golden-path workflow completion: p50 under 60s, p95 under 90s for controlled
  alpha.
- Reload/job hydration: p95 under 2-3s.
- Controlled-alpha error budget:
  - 100% canary success before sessions;
  - 0 API OOM/restarts during sessions;
  - 0 deterministic readout fallbacks on golden path;
  - supported-path job success at or above 95%.

### Pre-Alpha Commands

```bash
poetry run pytest tests/test_api_import_boundary.py tests/perf/test_backtest_infra_benchmark.py -q --no-cov
poetry run pytest tests/test_backtest_jobs_async.py tests/test_backtest_jobs_shadow.py tests/test_render_workflow_execution.py tests/test_render_workflow_proof.py tests/test_render_canary_script.py tests/test_private_alpha_readiness.py tests/test_render_runtime_compatibility.py -q --no-cov
poetry run pytest tests/perf/section3/test_engine_latency.py -q --no-cov -m slow
poetry run python scripts/benchmarks/backtest_infra_benchmark.py
.github/render-env-sync.sh api-status
.github/warmup-render.sh --expect-mode real-workflow
.github/canary-render.sh
poetry run python scripts/ops/alpha_readiness_metrics.py --json
poetry run python scripts/benchmarks/render_internet_benchmark.py --repeat 1
```

Latest local verification on 2026-06-15:

- Spanish/runtime matrix: `tests/agent_runtime/test_spanish_runtime_transcripts.py`,
  `tests/test_natural_time.py`, `tests/test_strategy_capabilities.py`,
  `tests/test_strategy_registry_i18n.py`, and
  `tests/agent_runtime/test_llm_interpreter.py` passed.
- Backtest trust matrix: engine launch/display, execution ledger, benchmark
  comparison, execute launch/recovery, and runtime confirmation-card tests
  passed.
- Workflow/readiness matrix: import boundary, backtest infra, async job,
  Render workflow proof/execution, canary script, private-alpha readiness, and
  runtime compatibility tests passed.
- Security/API matrix: alpha Supabase API, Supabase gateway, context-packet
  runtime attachment, context packets, backtest job shadow, and async job tests
  passed after auth normalization, quota, ownership, and feedback hardening.
- Web cold-start/card smoke: `alpha-frontend`, Spanish UI smoke,
  date-range-display, confirmation-display, and result-card playground tests
  passed.
- Browser launch-smoke coverage now includes
  `web/e2e/chat-action-recovery.spec.ts::private-alpha readiness smoke covers starter, Spanish edit, result, reload, retry, and feedback`,
  which exercises Spanish starter chips, the normal chat runtime, confirmation
  date edit, run/result, Quick take, reload hydration, feedback, Explain
  result, and localized retry in one deterministic Playwright path. The
  companion
  `web/e2e/chat-action-recovery.spec.ts::Spanish confirmation edit actions preserve context through asset, assumptions, and cancel`
  path proves Spanish `Cambiar activo` and `Ajustar supuestos` follow-up turns
  are sent as normal user messages without action payloads while backend-shaped
  artifacts preserve period/context, and `Cancelar` transitions the card to
  `Borrador cancelado`. The onboarding browser smoke also proves mock-auth
  login form submission enters the private-alpha chat shell, and the
  real-auth-only onboarding smoke now proves the signup form posts the entered
  invite identity to `/auth/signup` while rendering only sanitized rejection
  copy when the backend blocks the signup.

Latest local verification on 2026-06-16:

- Local QA-mode Browser smoke using the root `.env` and `web/.env.local`
  real-auth configuration passed for login -> Spanish prompt -> confirmation ->
  `Cambiar fechas` -> Spanish fallback clarification -> date answer -> updated
  confirmation -> run -> result card/readout -> Explain result -> reload
  hydration. The live edit prompt path logged upstream LLM clarification
  fallbacks before recovering with `¿Qué periodo quieres usar para AAPL?`; the
  follow-up answer still updated the active confirmation and result to
  `1 feb 2025 -> 1 may 2025`.
- Local QA-mode live-provider/date smoke on branch HEAD `20887a5` used the
  root `.env` plus `web/.env.local` with the strict QA backend and frontend
  running locally. The in-app Browser path was attempted first, but login input
  was blocked by the Browser virtual-clipboard limitation, so the same rendered
  flow was exercised with repo Playwright against `http://localhost:3000`.
  Prompt `Prueba comprar y mantener Apple con 100k durante el ultimo ano`
  reached a Spanish confirmation with provider-canonical `AAPL`, `$100,000`,
  and `16 jun 2025 -> 16 jun 2026`; executing the card produced a completed
  result with the same date window, chart, and Spanish quick summary.
- `cd web && bun run test:e2e chat-action-recovery.spec.ts onboarding.spec.ts --project=chromium`
  returned 13 passed for the affected browser recovery, readiness-smoke,
  Spanish edit-loop, and private-alpha onboarding specs.
- `cd web && PLAYWRIGHT_PORT=3112 bun run test:e2e e2e/onboarding.spec.ts --project=chromium`
  returned 7 passed and 1 skipped, with the skipped test explicitly reserved
  for real-auth mode.
- `cd web && NEXT_PUBLIC_MOCK_AUTH=false PLAYWRIGHT_PORT=3111 bun run test:e2e e2e/onboarding.spec.ts --project=chromium --grep "real-auth signup"`
  returned 1 passed, proving browser signup reaches `/auth/signup` with the
  entered display name, email, and password, then shows the sanitized
  `Signup failed. Please try again.` rejection without allowlist, invite, or
  Supabase leak copy.
- `cd web && bun run lint e2e/onboarding.spec.ts playwright.config.ts` passed.
- `poetry run ruff check src tests workflows scripts` passed.
- Focused Supabase security/API verification passed:
  `poetry run pytest tests/test_alpha_api_supabase.py tests/test_supabase_gateway.py -q --no-cov`
  returned 67 passed after adding feedback raw-context bounds.
- Broader readiness regression matrix passed:
  `poetry run pytest tests/test_environment_scripts.py tests/test_api_import_boundary.py tests/test_render_canary_script.py tests/test_render_runtime_compatibility.py tests/test_private_launch_hardening.py tests/test_checkpoint_rls_migration.py tests/test_ci_workflow.py tests/test_legacy_orchestrator_retirement.py tests/test_chat_backtest_state_machine.py tests/test_openrouter_policy.py tests/agent_runtime/test_execute_recovery.py tests/agent_runtime/test_spanish_runtime_transcripts.py tests/test_chat_runtime_reload_guardrails.py tests/section3/test_market_data_provider.py tests/test_alpha_artifacts.py tests/test_alpha_api_supabase.py tests/test_supabase_gateway.py tests/test_chat_stream_contract.py tests/agent_runtime/test_workflow.py -q --no-cov`
  returned 403 passed on the latest refresh after the result-action runtime
  ownership repair.
- Completion-audit refresh at branch HEAD `dca0d30` passed:
  `poetry run pytest tests/test_api_import_boundary.py tests/perf/test_backtest_infra_benchmark.py -q --no-cov`
  returned 9 passed;
  `poetry run pytest tests/test_backtest_jobs_async.py tests/test_backtest_jobs_shadow.py tests/test_render_workflow_execution.py tests/test_render_workflow_proof.py tests/test_render_canary_script.py tests/test_private_alpha_readiness.py tests/test_render_runtime_compatibility.py -q --no-cov`
  returned 59 passed;
  `poetry run pytest tests/test_environment_scripts.py tests/test_alpha_api_supabase.py tests/test_supabase_gateway.py tests/test_chat_runtime_reload_guardrails.py tests/test_chat_stream_contract.py tests/agent_runtime/test_spanish_runtime_transcripts.py tests/agent_runtime/test_interpret_stage.py::test_current_message_asset_grounding_clears_stale_invalid_llm_symbol -q --no-cov`
  returned 172 passed; `cd web && PLAYWRIGHT_PORT=3121 bun run test:e2e e2e/onboarding.spec.ts --project=chromium`
  returned 7 passed and 1 real-auth-only skip; and
  `cd web && NEXT_PUBLIC_MOCK_AUTH=false PLAYWRIGHT_PORT=3122 bun run test:e2e e2e/onboarding.spec.ts --project=chromium --grep "real-auth signup"`
  returned 1 passed.
- The same completion-audit refresh passed
  `poetry run ruff check src tests workflows scripts` and
  `cd web && bun run lint e2e/onboarding.spec.ts playwright.config.ts`.

Latest Render verification on 2026-06-16:

- `.github/render-env-sync.sh api-status` reported real-workflow mode:
  dispatch/shadow enabled, `ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=true`,
  real task `argus-backtests/run_backtest_job`, proof task
  `argus-backtests/workflow_proof`, backpressure limits present, and Render API
  key redacted-present.
- `.github/warmup-render.sh --expect-mode real-workflow` passed after normal
  cold-start retries for API health, product readiness, and frontend. During the
  same run, the stale queued/running backtest job scan returned
  `status=ready`, `scanned_count=0`, `stale_count=0`, and `unresolved_count=0`.
- `.github/canary-render.sh` passed against the deployed Render app/API using
  the root `.env` local aliases (`MOCK_USER_EMAIL` / `MOCK_USER_PASSWORD` plus
  Supabase verifier credentials). Canary conversation
  `b20da5d4-ba0e-404c-b275-8a4813812c0b` created async job
  `b03db203-850a-4dd3-a51d-b313b0b9b5ea`, which completed with run
  `0ca6b215-5dcb-44db-a014-48722c478311`. The script verified confirmation,
  the structured `run_backtest` action, async workflow completion, persisted
  messages, Supabase rows, result-summary route receipt, and LLM readout voice.
- Closed locally in the readiness worktree: `.github/canary-render.sh` now
  accepts `ARGUS_CANARY_LANGUAGE`, so the same strict canary harness can be
  reused for Spanish live QA instead of a one-off curl path.
- Deployment-drift finding on 2026-06-16: running the Spanish canary with
  `ARGUS_CANARY_LANGUAGE=es-419` against the live Render API reached
  confirmation, emitted the structured `run_backtest` action, and completed job
  `b78df19d-c7fa-4b37-a3d7-38ac2d865eff` with run
  `316a9db8-3990-40e7-9f65-e2d98da2ee6c`, but failed the strict readout gate
  because the deployed API is still commit `f335d7814335f8b1b330d3ee37e7125cafdbc478`
  from `codex/private-alpha-next`. Persisted metadata showed
  `result_readout_source=deterministic_fallback` and
  `result_readout_failure_mode=quick_take_draft_rejected`. Rerun this Spanish
  canary only after the readiness branch is deployed.
- Live gate refresh after pushing readiness branch HEAD `4867be1` on
  2026-06-16: `.github/render-env-sync.sh api-status` still reported
  real-workflow mode, `.github/warmup-render.sh --expect-mode real-workflow`
  passed with stale job scan `status=ready`, and Render API deploy metadata
  still showed live commit `f335d7814335f8b1b330d3ee37e7125cafdbc478`.
  The strict Spanish canary was intentionally not rerun because it would test
  the older deployed API rather than the readiness branch.
- Live gate refresh after pushing readiness branch HEAD `2434b98` on
  2026-06-16: `.github/render-env-sync.sh api-status` still reported
  real-workflow mode with dispatch and execution enabled. Render API service
  metadata showed `argus-api` deploys from `main`, auto-deploy is off, and the
  live deploy remains commit `f335d7814335f8b1b330d3ee37e7125cafdbc478`.
  The strict Spanish canary remains intentionally blocked until the readiness
  branch is merged/deployed by the founder-directed release step.
- Live gate refresh after pushing readiness branch HEAD `1e54bba` on
  2026-06-16: `.github/render-env-sync.sh api-status` still reported
  real-workflow mode with dispatch/execution enabled and `RENDER_API_KEY`
  redacted-present. `.github/warmup-render.sh --expect-mode real-workflow`
  passed after normal cold-start retries; the stale queued/running job scan
  returned `status=ready`, `scanned_count=0`, `stale_count=0`, and
  `unresolved_count=0`. `.github/canary-render.sh` passed against the currently
  deployed Render app/API: canary conversation
  `ee936843-ba95-49e1-9a03-7b10546b4416` created async job
  `e2a51251-4d58-4af1-8546-89320900a333`, which completed with run
  `4a0d75b5-4f72-4e17-8735-aa8172c18e63`; the script verified confirmation,
  structured `run_backtest`, async job/run result, LLM readout voice, and
  persisted messages. This refresh validates the live deployed path, not a
  readiness-branch deployment; strict Spanish canary remains blocked until the
  readiness branch is merged/deployed.
- Live gate refresh after pushing readiness branch HEAD `dca0d30` on
  2026-06-16: `.github/render-env-sync.sh api-status` still reported
  real-workflow mode with dispatch/execution enabled and `RENDER_API_KEY`
  redacted-present; `.github/render-env-sync.sh api-deploy-status` still showed
  live deploy commit `f335d7814335f8b1b330d3ee37e7125cafdbc478`, not the
  readiness branch. `.github/warmup-render.sh --expect-mode real-workflow`
  passed after normal Render cold-start retries; the stale queued/running job
  scan returned `status=ready`, `scanned_count=0`, `stale_count=0`, and
  `unresolved_count=0`. `poetry run python scripts/ops/alpha_readiness_metrics.py --json`
  returned `job_count=4`, `status_counts.succeeded=4`, `active_jobs=0`,
  `terminal_failures=0`, `readout.llm_explain_stage_count=3`, and
  `deterministic_readout_fallbacks=1`; the fallback remains visible because the
  24-hour aggregate still includes the earlier Spanish canary on the older
  deployed API. Strict Spanish canary remains intentionally blocked until the
  founder-directed deploy moves Render to the readiness branch.
- Closed locally in the readiness worktree: `.github/render-env-sync.sh`
  now includes `web-deploy-status`, so the private launch runbook checks both
  `argus-api` and `argus-app` deploy ids/statuses/commits/timestamps before
  strict canaries. Live 2026-06-16 checks showed both services still on
  deployed commit `f335d7814335f8b1b330d3ee37e7125cafdbc478`, so the
  release gate remains blocked on founder-directed deployment of the readiness
  branch before English/Spanish strict canaries.
- Closed locally in the readiness worktree: `.github/workflows/private-alpha-canary.yml`
  adds a manual and daily GitHub Actions gate that requires canary secrets, runs
  `.github/warmup-render.sh --expect-mode real-workflow`, then runs
  `.github/canary-render.sh`. It has read-only repository permissions and does
  not deploy or configure analytics.
- Closed locally in the readiness worktree:
  `scripts/ops/alpha_readiness_metrics.py` summarizes aggregate
  `backtest_jobs.execution_metadata` signals without emitting user ids,
  conversation ids, prompts, or analytics events. A live 2026-06-16 run after
  the authenticated canary returned `job_count=1`, `status_counts.succeeded=1`,
  `active_jobs=0`, `deterministic_readout_fallbacks=0`,
  `terminal_failures=0`, and `readout.llm_explain_stage_count=1`.
- Live metrics refresh after the 2026-06-16 canary returned `job_count=3`,
  `status_counts.succeeded=3`, `active_jobs=0`, `terminal_failures=0`,
  `readout.llm_explain_stage_count=2`, and
  `deterministic_readout_fallbacks=1`. The current English canary passed the
  strict LLM readout voice gate; the aggregate fallback remains visible because
  the 24-hour window still includes earlier deployed-path canary history.
- Independent read-only QA sidecar on 2026-06-16 audited the allowed readiness
  lanes only, excluding legal/consent implementation and PostHog analytics
  implementation. It reported `469 passed` across the Spanish/runtime,
  backtest trust, security/feedback, workflow, Supabase, and reload-guardrail
  backend matrix; `143 passed` across focused web chat/artifact/result,
  hydration, playground, and Spanish UI unit tests; and `6 passed` for
  `web/e2e/chat-action-recovery.spec.ts`. That sidecar observed an interrupted
  canary attempt, but the main-thread `.github/canary-render.sh` run completed
  afterward with the passing live result documented above.
- Closed locally in the readiness worktree: `.github/stale-backtest-jobs.sh`
  scans stale queued/running backtest jobs, reconciles terminal Render task runs
  through the existing backtest-job helper, and is invoked by
  `.github/warmup-render.sh` when service-role Supabase verifier credentials are
  present.

Latest local browser QA on 2026-06-16:

- Environment: backend on `http://127.0.0.1:8010/api/v1` with memory
  persistence, mock auth, and synthetic fixture market data; frontend on
  `http://127.0.0.1:3000` using `web/.env.local`.
- Cold-start slate: English starter chips were visible, did not reference 2024,
  did not use field-template syntax, and clicking `Test Apple vs SPY` submitted
  a normal user turn. That rolling-window starter correctly entered runtime and
  asked for an end-date clarification instead of bypassing interpretation.
- Spanish golden path: the prompt `Prueba una estrategia de comprar y mantener
  AAPL desde el 1 de enero de 2024 hasta el 31 de diciembre de 2024 con 10000
  dolares y SPY como referencia.` produced a confirmation card with AAPL, SPY,
  `$10,000`, daily data, no fees/slippage, and `Run backtest`.
- Result path: `Run backtest` completed locally, rendered the result card,
  TradingView chart attribution, benchmark comparison, Quick take, and
  `Explain result`. `Explain result` produced a separate `BREAKDOWN` while the
  Quick take remained visible. Backend logs recorded a local
  `result_breakdown` LLM timeout and deterministic fallback for that breakdown;
  this is acceptable as local UI-path evidence only. The deployed canary remains
  strict that golden-path result readout voice must come from the LLM explain
  stage without fallback.
- Reload path: reloading the conversation URL preserved the Spanish prompt,
  completed result card, Quick take, breakdown, and feedback controls.
- Feedback path: the in-app Browser click bridge timed out on the small feedback
  icon buttons, but standalone Playwright against the same local URL clicked a
  `Good response` control, opened the feedback dialog, submitted text, and
  verified `Feedback submitted.` with no console issues. The direct local API
  feedback smoke also returned `{"success":true}`.
- Scripted browser action proof: `bun run test:e2e
  e2e/chat-action-recovery.spec.ts --project=chromium` now covers confirmation
  actions (`Change dates`, `Change asset`, `Adjust assumptions`, `Cancel`),
  structured `Run backtest`, result-card reload hydration, `Explain result`,
  `Refine idea`, more-menu `Report issue` feedback submission, and retry
  recovery from a failed stream.
- Console health: in-app Browser console inspection after the run returned no
  `error` or `warn` entries and no framework overlay text.

Production-parity local QA addendum on 2026-06-16:

- Root `.env` and `web/.env.local` are present. For QA-mode browser work, the
  ignored frontend env was corrected locally from `8010`/mock auth to
  `NEXT_PUBLIC_ARGUS_API_URL=http://127.0.0.1:8000/api/v1` and
  `NEXT_PUBLIC_MOCK_AUTH=false`, matching `.github/qa.sh`.
- `.github/qa.sh` started the backend with Supabase persistence, live provider
  catalog resolution, strict fallback, and Postgres checkpoints. The frontend
  started from `web/.env.local`.
- Live browser QA initially found a real stream/render race: a first AAPL
  prompt persisted the user message and assistant confirmation metadata, and
  reload hydration showed the `Run backtest` card, but the in-session browser
  view did not render the final assistant artifact before reload.
- Closed in `fe50e1c fix(chat): render final artifacts after hydration races`.
  The frontend final-stream reducer now replaces the pending assistant when it
  exists and appends the finalized assistant artifact when route hydration has
  raced the pending placeholder away.
- Focused verification after the fix:
  `bun test __tests__/chat-send-state.test.ts`;
  `bun test __tests__/chat-send-state.test.ts __tests__/chat-final-message.test.ts __tests__/chat-artifact-history.test.ts __tests__/chat-backtest-jobs.test.ts`;
  `bun test __tests__/alpha-frontend.test.ts __tests__/chat-turn-artifact-ux.test.ts __tests__/chat-message-hydration.test.ts`;
  `bun run test:e2e e2e/chat-action-recovery.spec.ts --project=chromium`;
  `bun run lint`.
- Live QA after the fix: real-auth browser login, QA backend/frontend, and a
  fresh GOOGL prompt reached `CHECKPOINT repaired_live_confirmation_visible`
  with `unexpected_responses=0` and `console_errors=0`. Reloading the already
  completed AAPL result reached `CHECKPOINT patched_result_reload_visible` with
  `unexpected_responses=0`.

Production-parity browser QA refresh on 2026-06-16:

- Confirmed root `.env` and `web/.env.local` are present and used by QA mode:
  backend from `.github/qa.sh` on `http://127.0.0.1:8000` with Supabase
  persistence, live provider, strict fallback, and Postgres checkpoints;
  frontend from `web/.env.local` on `http://localhost:3000` with real auth.
- Local API auth smoke after `a9bb9a2` confirmed an unlisted signup returns the
  generic `400 auth_signup_failed` shape without private-alpha allowlist copy.
  The matching test coverage still proves Supabase Auth signup is not called for
  that blocked email.
- Local proxy-header cookie smoke with the configured private-alpha tester
  confirmed login sets redacted `sb-auth-token` and `sb-refresh-token` cookies
  with `HttpOnly`, `Path=/`, `SameSite=lax`, and `Secure` when
  `x-forwarded-proto: https` is present. Deployed cookie capture is still the
  final gate after the readiness branch is deployed.
- Real-auth login succeeded with the configured mock private-alpha tester
  credentials. The authenticated cold-start slate rendered current English and
  Spanish starter prompts without stale 2024 defaults.
- Spanish prompt proof: `Prueba comprar y mantener Apple con 100k durante el
  ultimo ano contra SPY` reached confirmation, preserved AAPL, SPY, `$100,000`,
  the rolling `Jun 16, 2025 -> Jun 16, 2026` window, stocks, daily data, no
  fees, and no slippage.
- `Run backtest` completed and rendered the result card, chart, Quick take, and
  `Explain result`. The result showed ending value `$149,977`, `+50.0%` total
  return, SPY comparison `+24.9%`, beat by `25.1` percentage points, and
  max drawdown `-13.8%`.
- Reloading the conversation preserved the Spanish prompt, completed
  confirmation/result card, Quick take, breakdown, and feedback controls.
- Feedback initially exposed remote schema drift: `/feedback` returned 500
  because live Supabase still had the old
  `usage_counters_resource_check` constraint with only `chat_messages` and
  `backtest_runs`. The existing local migration
  `20260616091955_expand_usage_counter_resources.sql` was applied to the QA
  database as two direct `supabase db query` statements because `db push` is
  blocked by older remote migration-history naming drift. Read-back confirmed
  `chat_messages`, `backtest_runs`, `backtest_jobs`, and `feedback`; retrying
  the same feedback path closed the dialog and backend logs showed
  `POST /api/v1/feedback` 200.
- Additional local Playwright browser smoke after the auth-hardening checkpoint
  confirmed the same QA-mode stack can log in, render the current starter slate,
  submit the Spanish AAPL/SPY prompt, reach confirmation with AAPL/SPY/100k
  preserved, run the backtest, render Quick take and `Explain result`, click
  `Explain result`, reload the conversation, and hydrate the prompt, Quick
  take, persisted breakdown, and feedback controls. After reload, feedback on
  the hydrated result/breakdown returned `/api/v1/feedback` 200.
- Debug note from that smoke: after `Explain result` is clicked, reload
  correctly hydrates the persisted breakdown while the consumed result action no
  longer needs to remain a visible button. A repeat prompt attempt later hit
  OpenRouter clarification-profile timeout/provider failures and did not reach a
  confirmation card, reinforcing that the deployed strict canary/no-fallback
  gate remains mandatory before tester sessions.
- Additional QA-mode browser smoke after the action-identity/refine-action
  checkpoints (`e5b95b3`, `6e97e2f`, `a2aa10f`, `889d6e9`) used the root
  `.env` and `web/.env.local` with `.github/qa.sh` plus
  `cd web && bun run dev`.
  The live local flow reached an AAPL buy-and-hold confirmation for `$10,000`
  over Jun 16, 2025-Jun 16, 2026, clicked the card-scoped `Run backtest`
  action, transitioned through `Running`, and rendered a completed result with
  Quick take, `Explain result`, and `Refine idea`. Clicking `Refine idea`
  consumed only that result action immediately (`Refine idea` button count
  1 -> 0), returned the backend refinement prompt, and a reload of the persisted
  conversation kept Quick take and the prompt hydrated with `Explain result`
  still available and `Refine idea` still consumed. In-app browser console
  inspection during the smoke returned no warnings or errors.
- Additional QA-mode browser smoke after the adjust-assumptions reload
  regression used the same root `.env` and `web/.env.local` stack. A fresh exact
  AAPL buy-and-hold prompt for `$10,000` over Jun 16, 2025-Jun 16, 2026 reached
  confirmation with `Run backtest`, `Change dates`, `Change asset`,
  `Adjust assumptions`, and `Cancel` scoped to the card. Clicking
  `Adjust assumptions` moved the card to `Editing`, consumed the card actions,
  and returned `Which assumption would you like to adjust?`. Reload preserved
  the editing card and prompt. Answering `use 5000 dollars starting capital
  instead` produced a new `Ready to run` confirmation with `$5,000`, restored
  card actions, and a final reload hydrated the old card as `Updated` plus the
  new `$5,000` confirmation. In-app browser console inspection returned no
  warnings or errors.
- Additional QA-mode Spanish browser smoke after the date-edit recovery
  checkpoint used the same root `.env` and `web/.env.local` stack. Live QA
  initially reproduced a Spanish `Cambiar fechas` regression where answering
  `Usa del 1 de febrero de 2025 al 1 de mayo de 2025` after reload either
  regenerated the stale Jan-Apr confirmation or asked an unrelated follow-up.
  The runtime now repairs only active pending date answers after LLM
  interpretation, using the current message's parsed date range when the LLM
  omits or echoes the stale date. Focused regressions cover stale, missing, and
  reload-thinned metadata shapes, and the final in-app browser pass regenerated
  the Spanish AAPL confirmation with `1 feb 2025 -> 1 may 2025` plus localized
  card actions, then hydrated that corrected card after reload.
- Additional QA-mode Spanish browser smoke after confirming root `.env` and
  `web/.env.local` found a provider-grounding trust regression: `Prueba comprar
  y mantener Apple con 100k durante el ultimo ano` produced Spanish copy that
  recognized `Apple (AAPL)` while also saying `APPLE` was unavailable. Closed
  locally by clearing stale invalid-symbol metadata when post-LLM provider
  grounding replaces an LLM pseudo-ticker with the provider-backed symbol from
  the current user message. Focused tests now cover this repair while preserving
  forged selected-asset rejection. Post-fix local QA against the real-auth QA
  stack reached an `AAPL` confirmation with `Ejecutar backtest`,
  `Cambiar fechas`, `Cambiar activo`, `Ajustar supuestos`, and `Cancelar`
  without unsupported `APPLE` copy.
- Follow-up Playwright QA fallback was used because the in-app Browser session
  could inspect/click but could not type into the rich composer without its
  virtual clipboard. The fallback used the same local QA backend/frontend and
  real auth. Conversation `d38a21fb-1729-4cbb-9263-3a310d9e0ac1` completed the
  `Ejecutar backtest` action and rendered an `AAPL` result with Spanish
  `Resumen rapido`, `Explicar resultado`, and `Ajustar idea`. A subsequent
  clean-console rerun timed out waiting for confirmation after live OpenRouter
  interpretation fallback/timeout warnings, so provider health remains covered
  by the deployed canary gate rather than treated as solved by this local pass.
- Fresh local readiness refresh after the same repair kept the QA backend
  running from `.github/qa.sh` and restarted the frontend from `web/.env.local`.
  The broad backend matrix above returned `348 passed` in 48.17s. The full
  frontend unit suite returned `254 pass` across 36 files. The focused
  Playwright action-recovery slice returned 4 passed after the existing dev
  server on `3000` was stopped so Playwright could own its configured `3100`
  test server:
  `bun run test:e2e e2e/chat-action-recovery.spec.ts --project=chromium --grep "private-alpha readiness smoke|Spanish confirmation edit actions|retry action recovers|Spanish action recovery"`.
  Those browser tests cover readiness smoke, Spanish edit actions, retry
  recovery without duplicate user input, and localized Spanish recovery
  controls.
- Fresh in-app Browser QA then used the same root `.env` and `web/.env.local`
  stack without Playwright fallback. Browser login reached `/chat` with Spanish
  UI and no console warnings. The prompt `Prueba comprar y mantener Apple con
  100k durante el ultimo ano` reached an `AAPL` confirmation with `$100,000`,
  `16 jun 2025 -> 16 jun 2026`, `Ejecutar backtest`, `Cambiar fechas`,
  `Cambiar activo`, `Ajustar supuestos`, and `Cancelar`; it did not show stale
  unsupported `APPLE` copy. Clicking `Ejecutar backtest` completed the result
  path with chart, `Explicar resultado`, `Ajustar idea`, and Spanish
  `Resumen rapido`. The result showed ending value `$150,685`, `+50.7%` total
  return, SPY `+24.8%`, beat by `25.9` points, and max drawdown `-13.8%`.
  Browser console inspection returned no `error` or `warn` entries for the
  live confirmation/result path.
- Result-action ownership refresh on 2026-06-16 closed the remaining
  LangGraph-boundary gap from the runtime guardian audit: `show_breakdown` and
  `save_strategy` now enter runtime as turn-scoped result-action requests before
  API transport performs canonical run lookup, breakdown composition, strategy
  saving, metadata persistence, and SSE finalization. The same slice localized
  stale/missing/lost confirmation recovery messages and added regression
  coverage that result actions enter runtime before transport handling. During
  full-matrix verification, a market-data provider test-order leak left a
  mocked asset alias cache warm for later workflow tests; the provider test file
  now clears the asset cache before and after each test. Fresh verification
  returned `403 passed` for the backend readiness matrix that includes
  `tests/test_chat_stream_contract.py`, `tests/test_chat_backtest_state_machine.py`,
  `tests/test_chat_runtime_reload_guardrails.py`, `tests/section3/test_market_data_provider.py`,
  and `tests/agent_runtime/test_workflow.py`; `poetry run ruff check src tests workflows scripts`
  and `git diff --check` also passed.
- Follow-up public-stream coverage now proves the recent `APPLE` to `AAPL`
  repair survives beyond the internal interpretation stage: the stream test
  installs a real in-memory runtime with a fake interpreter that emits
  `APPLE`, a provider resolver that rejects that LLM pseudo-ticker while
  resolving the current-message `Apple` mention to `AAPL`, then asserts the
  final SSE confirmation payload and persisted assistant metadata contain
  `AAPL` with no stale `invalid_symbols`. The focused stream-contract file
  returned `24 passed`.
- Follow-up browser coverage now prevents the Spanish readiness smoke from
  passing with English mocked backend result text. The Playwright mock API
  returns localized Spanish result summary, breakdown, and refine text when
  `language="es-419"`, and the Spanish smoke asserts the localized summary plus
  Spanish result breakdown copy after reload and `Explicar resultado`. The full
  `web/e2e/chat-action-recovery.spec.ts` Chromium run returned `6 passed`.
- Fresh in-app Browser QA after the result-action refresh restarted
  `.github/qa.sh` against the updated tree and reused the real-auth frontend.
  Login reached `/chat` with no console warnings. The same Spanish Apple prompt
  reached the corrected `AAPL` confirmation, clicking `Ejecutar backtest`
  completed an `AAPL` result with `Explicar resultado` and `Ajustar idea`, and
  clicking `Explicar resultado` rendered a Spanish `DESGLOSE` grounded in the
  stored run: AAPL buy-and-hold, SPY comparison, +50.9% return, +24.8% SPY,
  +26.1 points, -13.8% drawdown, assumptions, and supported next tests. Browser
  console inspection returned no `error` or `warn` entries. The backend logged
  an expected result-breakdown LLM timeout followed by deterministic fallback;
  the user-facing breakdown still rendered. Browser CDP screenshot capture
  timed out on the chart page, so this pass is recorded from DOM state, browser
  logs, and backend logs rather than a fresh screenshot artifact.
- Fresh in-app Browser QA after confirming the root `.env` and `web/.env.local`
  files are present restarted `.github/qa.sh` and `cd web && bun run dev` on the
  default QA ports. The real-auth browser session reached Spanish `/chat` and
  conversation `d4c4c1b8-a6a0-4f11-a881-5b48d0558af8` with no Browser console
  warnings or errors. The prompt `Prueba una estrategia de comprar y mantener
  AAPL y MSFT con pesos iguales desde el 1 de enero de 2025 hasta el 5 de junio
  de 2026 con 10000 dolares` produced a Spanish confirmation with `AAPL`,
  `MSFT`, `$10,000`, `1 ene 2025 -> 5 jun 2026`, `SPY`, `Ejecutar backtest`,
  and localized edit/cancel actions. Clicking `Ejecutar backtest` transitioned
  through `Ejecutando` to `Ejecucion completa` and rendered the result card,
  TradingView chart attribution, final value `$11,284`, `+12.8%` total return,
  SPY `+26.1%`, underperformance by `13.3` points, max drawdown `-23.8%`,
  confidence context, `Explicar resultado`, `Ajustar idea`, and Spanish
  `Resumen rapido`. Backend logs showed OpenRouter route receipts plus one
  `result_summary` primary-model timeout that recovered through the configured
  fallback model. Browser CDP screenshot capture still timed out, so this pass
  is recorded from DOM state, Browser console logs, and backend logs.
- QA observation from the adjust-assumptions smoke: a separate natural
  `past year` prompt first asked for an exact date range, then a date answer hit
  the existing strict interpreter-unavailable recovery after live OpenRouter
  interpretation fallbacks failed. This was not patched in that
  action-ownership slice because the current runtime tests intentionally refuse
  deterministic date parsing when the structured interpreter is unavailable;
  keep the deployed strict canary and provider-health gate as the release
  authority for that path.

### Daily Automation Candidates

For controlled alpha:

- real-workflow mode drift check;
- warmup plus canary;
- executed stale queued/running job scan output;
- OpenRouter credit/rate-limit check;
- Supabase error-log scan;
- aggregate metrics extractor over `backtest_jobs.execution_metadata`, using
  `poetry run python scripts/ops/alpha_readiness_metrics.py --json`.

For public mode later:

- synthetic user journey monitor;
- security scan cadence;
- dependency vulnerability scan;
- public latency dashboard;
- quota abuse alerts;
- privacy/analytics event-shape audit.

## Lane Report: Analytics And Feedback

### Verdict

Do not build a custom analytics pipeline in Supabase right now, and do not turn
PostHog on casually. Use the two systems for different jobs:

- **Supabase feedback** is durable user-reported truth.
- **Route receipts, logs, jobs, runs, and messages** are operational/product
  truth for the first controlled alpha.
- **PostHog**, when enabled, should capture only privacy-safe behavioral events
  and funnels, not raw investing ideas.

### Current Feedback Path

The feedback API exists:

- `POST /api/v1/feedback`;
- types: `bug`, `feature`, `general`, `account_deletion_request`;
- backend persists to Supabase when configured;
- in-memory fallback exists for dev mode;
- feedback logs type/source/message length;
- frontend feedback dialog supports bug, feature, general, and rating-like
  feedback;
- non-rating feedback requires consent;
- file attachments are not uploaded, only counted.

Relevant code:

- `docs/API_CONTRACT.md`
- `docs/DATA_MODEL.md`
- `src/argus/api/routers/feedback.py`
- `src/argus/domain/supabase_gateway.py`
- `web/lib/argus-api.ts`
- `web/components/feedback/FeedbackDialog.tsx`
- `web/lib/chat-message-feedback-context.ts`

### Closed Locally For Readiness Branch

- Feedback messages are capped at 5,000 characters and oversized messages are
  rejected before persistence.
- Feedback context is bounded by known keys, nesting depth, serialized size,
  and raw top-level key count.
- Browser URL/path context is reduced to origin plus pathname; query and hash
  values are dropped before persistence.
- Feedback submissions are quota-protected with daily/hourly limits and a
  `Retry-After` response when exhausted.
- Supabase feedback persistence, user ownership, URL redaction, quota handling,
  and context/message caps are covered by local API tests and QA-mode smoke
  evidence.

### Remaining Founder-Gated Gaps

- "Learn more" in the feedback footer is not wired to the Privacy Policy; this
  stays blocked by the no-touch legal/privacy slice.
- Account deletion request enriches context with email/user id, so this path
  still needs privacy disclosure and access discipline before broader use.
- No attachment upload exists, which is good for alpha, but UI wording should
  remain honest that attachments are counted rather than stored.
- PostHog remains disabled until consent/privacy event taxonomy is approved.

### Controlled Alpha Feedback Plan

Before users:

- Keep file uploads disabled.
- Verify Supabase persistence with the launch runbook count query before and
  after a feedback submission.
- Confirm founder-facing tester notes tell users the feedback dialog and thumbs
  are the primary listening channel.
- Do not enable PostHog or any product analytics capture during the readiness
  launch gate.

Founder-gated follow-up:

- Make feedback footer "Learn more" link to Privacy Policy once legal/privacy
  pages are approved.
- Decide the account deletion request disclosure and access process with the
  legal/privacy slice.

During alpha:

- Ask users to use thumbs and feedback dialog for bugs, trust issues, and
  confusion.
- Keep founder notes separately from product telemetry.
- Export or query Supabase feedback after every tester window.

### PostHog Plan

Keep `NEXT_PUBLIC_POSTHOG_KEY` empty until this is designed.

When enabling PostHog:

- use the public project token only, never a personal API key;
- require explicit analytics consent or start default opt-out;
- disable session replay;
- disable autocapture or strictly filter with `before_send`;
- add `ph-no-capture` to chat transcripts, result cards, profile/account
  surfaces, feedback forms, and any prompt/result text;
- redact URL query/hash;
- do not capture raw prompts, assistant messages, result cards, conversation
  titles, emails, full URLs, or financial-sensitive content.

### Suggested Event Taxonomy

Events should describe behavior, not content:

- `alpha_signup_completed`
- `alpha_consent_accepted`
- `chat_message_submitted`
- `interpretation_started`
- `confirmation_card_shown`
- `confirmation_action_clicked`
- `backtest_job_created`
- `backtest_job_succeeded`
- `backtest_job_failed`
- `result_card_viewed`
- `quick_take_viewed`
- `explain_result_clicked`
- `refine_idea_clicked`
- `second_experiment_started`
- `feedback_opened`
- `feedback_submitted`
- `spanish_prompt_executed`
- `spanish_prompt_failed`

Properties should be bounded and non-sensitive:

- language;
- locale;
- asset class;
- strategy family;
- stage;
- status;
- error code;
- duration bucket;
- retryable;
- has_result;
- anonymous boolean or hashed stable id.

Never include:

- raw prompt;
- assistant response;
- result text;
- symbol list if you decide symbols are sensitive;
- email;
- conversation id in public analytics;
- run id in public analytics;
- URL query params.

For controlled alpha, even event properties can start in Supabase route receipts
and founder notes. PostHog becomes useful once the event contract is stable and
the privacy configuration is proven.

## Lane Report: UX Research Readiness

### Verdict

The user study should not wait for a perfect product, but it must wait for a
trustworthy Spanish execution path and basic legal/privacy/security gates.
Otherwise we will learn that the product is broken, not whether the thesis has
pull.

Trusted-user feedback also identified a first-impression issue: the cold-start
action chips and placeholder examples include stale, exact 2024 dates. The
prompts are directionally useful, but the precision makes Argus feel brittle, as
if the user must speak in a rigid syntax for the product to work. The cold-start
slate should model the way we want users to talk: natural, current, and tolerant
of rolling windows.

### Test Goal

Prove or disprove:

> Spanish-first finance-curious users repeatedly value Argus because it turns a
> messy investing thought into a clear, executable historical test and helps
> them decide what to test next.

### Cohort

5-6 named users:

- adults;
- allowlisted;
- Spanish-first or Spanish-comfortable;
- finance-literate enthusiasts before broad beginners;
- recently had an investing idea, question, or market curiosity.

### Session Script

1. Ask what investing idea they had in the last 30 days.
2. Ask what they did with it before Argus.
3. Ask them to use Argus in Spanish without coaching.
4. Observe:
   - time to first useful confirmation card;
   - whether the card captured intent;
   - whether they understand assumptions;
   - whether they run the test;
   - whether result and Quick take make sense;
   - whether they ask for an explanation;
   - whether they run or request a second experiment;
   - whether they trust the limitations.
5. Ask them to explain Argus in one sentence.
6. Ask what they would use it for again.

### Cold-Start Prompt Slate

Original implementation facts:

- `web/components/chat/ChatInterface.tsx` renders three cold-start action chips
  with hardcoded fallback prompts.
- `web/public/locales/en/common.json` and
  `web/public/locales/es-419/common.json` contain 2024-specific starter action
  values and placeholder prompts.
- The English and Spanish examples include exact calendar boundaries such as
  January 1, 2024 through December 31, 2024.

This should be treated as UX trust debt for the readiness pass.

Readiness implementation status:

- English and Spanish starter action values now use natural rolling-window
  prompts instead of exact 2024 calendar ranges.
- English and Spanish placeholder prompt slates now mix current rolling windows
  with plain educational questions.
- The Nvidia DCA starter no longer submits a rigid field-template prompt.
- Backend regression coverage asserts the submitted starter prompts resolve
  through the shared natural-time parser, keeping frontend copy out of date
  math.
- Local browser QA on 2026-06-16 now covers the cold-start slate: current
  starter chips render without default 2024 references, and clicking
  `Test Apple vs SPY` submits a normal user turn into the chat runtime.

The desired model:

- labels stay short and useful, such as "Test Apple vs SPY" or "Weekly Nvidia
  buys";
- submitted prompts should be natural, such as "Compare Apple with SPY over the
  past year" or "What if I bought Bitcoin at the start of the year?";
- frontend prompt copy should not compute or hardcode dates;
- the backend interpreter should resolve relative windows against the current
  run date and data availability;
- Spanish starter prompts should be equally natural and should exercise the
  Spanish backend execution path;
- examples should avoid stale years unless the point is explicitly to test a
  historical calendar year.

Candidate replacements:

| Surface | Current smell | Better direction |
| --- | --- | --- |
| Apple vs SPY chip | Exact 2024 range. | "Compare Apple with SPY over the past year." |
| Bitcoin hold chip | Exact January 1 to December 31, 2024. | "What if I bought Bitcoin at the start of this year?" |
| Nvidia DCA chip | Rigid structured fields and 2024 range. | "What if I bought $250 of Nvidia every week over the past year?" |
| Placeholder prompts | Multiple 2024 examples. | Mix current rolling windows with plain educational questions. |
| Spanish prompts | Translated stale dates. | Natural Spanish prompts using `ultimo ano`, `este ano`, and `hasta hoy`. |

Acceptance criteria:

- no cold-start starter action or placeholder prompt references 2024 by default;
- all starter actions use natural language, not field-template syntax;
- rolling windows resolve in the backend, not in static frontend copy;
- English and Spanish starter actions both complete the same golden path in
  live QA;
- prompt examples make Argus feel tolerant of normal speech, not dependent on
  exact syntax.

### Success Metrics

For 5-6 controlled users:

- 3+ complete a first backtest.
- 3+ understand and can restate the assumptions.
- 3+ ask for or choose a follow-up variation.
- 2+ return within 7 days with another idea or ask to continue.
- 0 users interpret Argus as advice, brokerage, or "telling me what to buy."
- Spanish execution failures are rare enough to be product-learning noise, not
  the session headline.
- 0 users say the starter prompts make Argus feel stale, syntax-bound, or
  fragile.

### Observation Sheet

Capture:

- user language;
- prompt text category, not raw text if avoiding sensitive notes;
- whether prompt was Spanish;
- whether a cold-start starter chip was clicked;
- whether the starter slate felt current, approachable, or syntax-bound;
- strategy family;
- asset class;
- first failure point;
- trust objection;
- confusion point;
- whether confirmation was accepted, edited, or abandoned;
- whether run succeeded;
- run duration bucket;
- whether Quick take was read;
- whether Explain result was clicked;
- whether a second experiment happened;
- whether feedback was submitted;
- qualitative quote, with consent if retained.

## Sources

### Internal Sources

- `docs/PRODUCT.md`
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACT.md`
- `docs/DATA_MODEL.md`
- `.agent/designs/argus/DESIGN.md`
- `docs/CONVERSATIONAL_RUNTIME.md`
- `docs/PRIVATE_LAUNCH_RUNBOOK.md`
- `docs/specs/private-alpha-next-integration.md`
- `docs/specs/private-alpha-backtest-execution-capacity.md`
- `docs/specs/evidence-aware-idea-loop.md`
- `src/argus/agent_runtime/**`
- `src/argus/domain/backtesting/**`
- `src/argus/domain/engine_launch/**`
- `src/argus/api/routers/**`
- `src/argus/domain/supabase_gateway.py`
- GitHub issue 112:
  `https://github.com/lagarcess/argus/issues/112`
- `web/components/chat/ChatInterface.tsx`
- `web/public/locales/en/common.json`
- `web/public/locales/es-419/common.json`
- `web/components/feedback/FeedbackDialog.tsx`
- `web/lib/chat-message-feedback-context.ts`
- `archive-v0.1/**`

### External Sources

- SEC Investor.gov, Investment Adviser:
  https://www.investor.gov/introduction-investing/investing-basics/glossary/investment-adviser
- SEC Investment Adviser Marketing Rule PDF:
  https://www.sec.gov/files/rules/final/2020/ia-5653.pdf
- FTC Privacy and Security guidance:
  https://www.ftc.gov/business-guidance/privacy-security
- FTC Protecting Personal Information:
  https://www.ftc.gov/business-guidance/resources/protecting-personal-information-guide-business
- FTC Start with Security:
  https://www.ftc.gov/business-guidance/resources/start-security-guide-business
- FTC Children's Privacy:
  https://www.ftc.gov/business-guidance/privacy-security/childrens-privacy
- SBA Choose a Business Structure:
  https://www.sba.gov/business-guide/launch-your-business/choose-business-structure
- PostHog Privacy:
  https://posthog.com/docs/privacy
- PostHog Product Analytics Privacy:
  https://posthog.com/docs/product-analytics/privacy
- PostHog Session Replay Privacy:
  https://posthog.com/docs/session-replay/privacy
- Perplexity Agent API Prompt Guide:
  https://docs.perplexity.ai/docs/agent-api/prompt-guide
- Render Workflows:
  https://render.com/docs/workflows
- Render Workflow Limits:
  https://render.com/docs/workflows-limits
- Supabase Realtime Limits:
  https://supabase.com/docs/guides/realtime/limits
- OpenRouter Limits:
  https://openrouter.ai/docs/api-reference/limits
- OpenRouter Privacy:
  https://openrouter.ai/privacy
- OpenRouter Terms:
  https://openrouter.ai/terms
- TermsFeed Privacy Policy Generator:
  https://www.termsfeed.com/privacy-policy-generator/
- TermsFeed Terms and Conditions Generator:
  https://www.termsfeed.com/terms-conditions-generator/
- PrivacyPolicies.com Privacy Policy Generator:
  https://www.privacypolicies.com/privacy-policy-generator/
- Implementation risk in backtesting engines:
  https://arxiv.org/abs/2603.20319
- Backtest overfitting reference:
  https://arxiv.org/abs/1408.1159

## Final Founder Decisions Required

Before implementing the readiness slice, lock these:

1. **Alpha cohort language**
   - Operating answer: Spanish-first support is required.

2. **Company/operator**
   - Decide whether Terms/Privacy name an individual, LLC, or corporation.

3. **PostHog**
   - Recommended answer: keep disabled until privacy-first event taxonomy and
     consent are implemented.

4. **Backtest realism**
   - Recommended answer: keep simple no-fee/no-slippage alpha engine, harden
     truth and disclosure, defer realism controls.

5. **DCA**
   - Decide whether to gate DCA until semantics are cleaned up, or allow it with
     explicit recurring-contribution-only language.

6. **Security depth**
   - Recommended answer: focused security fixes now; full deep security scan
     before guest/public mode.

7. **Alpha speed promise**
   - Recommended answer: tell testers backtests may take around a minute during
     alpha.

## Recovery Checkpoint And Operating Boundary

The active recovery checkpoint for this readiness sprint is
`02da456 fix(runtime): harden localized action recovery` on
`codex/private-alpha-readiness-clean`. Continue readiness work from this clean
worktree only.

The original `codex/private-alpha-readiness` worktree is quarantined after dirty
cross-slice WIP and should be treated as read-only evidence, not as a source of
implementation truth. Do not salvage code or docs from that worktree without a
fresh, focused review against this clean branch.

`docs/specs/private-alpha-next-decision-memo.md` is future-context for the next
horizon. It can inform sequencing after readiness exits, but it must not start
Idea/Evidence/Decision memory, broker/export, voice, PostHog, iOS, or engine
abstraction implementation inside this readiness sprint.

## No-Touch Boundaries For Current Solo Execution

The current Codex-owned readiness pass must not implement or configure:

- Governance, legal, privacy-policy, Terms, consent, company-operator, or safety
  gate work.
- PostHog instrumentation, session replay, event capture, or product analytics
  activation; this includes the currently available PostHog environment
  variables.
- New analytics vendor wiring of any kind, including use of available
  `POSTHOG_*` environment variables.

Those remain founder-gated follow-up slices. This pass may keep documentation
accurate, verify existing feedback paths, and preserve privacy-safe route
receipts, but it should not add new analytics vendors or legal/consent
surfaces.

## Proposed Implementation Backlog

### Slice 1: Spanish Backend Execution

- Add multilingual interpreter contract.
- Tighten canonical field descriptions.
- Add post-LLM normalization through canonical temporal intent, the natural-time
  wrapper for bounded evidence, and machine compatibility aliases only, not
  hardcoded runtime language tables. Closed locally for date/window
  normalization and canonical strategy/cadence execution fields in a
  language-agnostic shape that should let Portuguese start from schema/prompt/
  test coverage instead of refactoring the runtime spine.
- Keep structured localized recovery as the fallback contract. Closed locally in
  the readiness worktree for interpreter-unavailable, runtime-failure, and
  pre-stream initialization failure paths.
- Spanish prompt matrix coverage now passes locally for DCA, missing DCA amount
  clarification, mixed-asset clarification, currency pairs, unsupported
  valuation requests, setup edits, approval turns, and result follow-ups.
- Local browser QA now covers the main Spanish confirmation/run/result/refine/
  cancel action chain and one unsupported-valuation recovery path that re-enters
  the normal confirmation funnel. The latest pass also covers localized
  quick-take optional-field labels and Spanish structured RSI rule rendering in
  confirmation cards.
- Local browser QA on 2026-06-16 caught and closed an active-confirmation date
  edit regression: a starter flow followed by `Use Jan 1 2025 to Apr 1 2025`
  now regenerates the confirmation and completed result with the explicit
  Jan 1-Apr 1, 2025 window instead of reusing the prior rolling default.
- Local QA on 2026-06-16 caught and closed a Spanish company-name grounding
  regression: `Apple` can now repair an LLM pseudo-ticker `APPLE` into provider
  `AAPL` without leaving stale unsupported-symbol metadata that blocks the
  confirmation.
- Spanish live QA is now scriptable through
  `ARGUS_CANARY_LANGUAGE=es-419 .github/canary-render.sh`, but the live Render
  API must first move past deployed commit
  `f335d7814335f8b1b330d3ee37e7125cafdbc478`; the 2026-06-16 Spanish canary
  failed the strict LLM readout gate on that older deployment.

### Slice 2: Alpha Trust And Legal Shell

- Add Terms page.
- Add Privacy Policy page.
- Add Spanish summaries or translated pages.
- Wire signup/settings/profile links.
- Add alpha clickwrap consent.
- Configure support email and deletion request copy.

### Slice 3: Security And Feedback Hardening

- Force secure cookies in production.
- Normalize allowlist auth errors. Closed locally for login enumeration, signup
  allowlist/provider response normalization, and login/signup attempt
  throttling.
- Add short-window quotas. Closed locally for authenticated chat, direct
  backtest, and feedback paths; auth attempts use their own non-user-id keyed
  limiter.
- Add parent ownership checks. Closed locally in the readiness branch: service
  role writes now validate owned parent conversations/strategies/runs/context
  packets before inserting or upserting child records; direct `/backtests/run`
  and `/strategies` return `404` for an explicit unowned conversation parent.
- Add feedback caps/context allowlist/url redaction. Closed locally in the
  readiness branch: `/feedback` now caps messages at 5,000 characters, keeps
  only known feedback context keys, converts browser URL/legacy path context to
  safe `page_path`, drops arbitrary nested browser blobs, and rejects raw
  context payloads with too many top-level keys, excessive serialized size, or
  deep nesting before quota checks or persistence.
- Verify Supabase feedback persistence. Closed for the QA database on
  2026-06-16 after syncing the existing `usage_counters` resource constraint to
  include `feedback`; production-parity browser retry returned `/feedback` 200.
- Add focused tests for each.

### Slice 4: Backtest Trust Hardening

- Fix explicit asset class resolution bypass. Closed locally in the readiness
  branch.
- Add execution/chart/metric parity tests. Closed locally in the readiness
  branch.
- Add benchmark sparse coverage tests. Closed locally in the readiness branch.
- Add chat launch/recovery mapping for benchmark coverage failures. Closed
  locally in the readiness branch.
- Add config snapshot reproducibility tests. Closed locally in the readiness
  branch.
- Clarify DCA result assumptions. Closed locally in the readiness branch.
- Gate unsupported DCA total-budget/starting-principal requests where the
  interpreter has not already done so. Covered locally by the existing DCA
  semantic-role audit and clarification matrix.

### Slice 5: Workflow And Observability Gate

- Verify Render env status command. Closed for the current deployed config on
  2026-06-16: `api-status` reported real-workflow mode with dispatch/execution
  enabled, proof and real task IDs configured, backpressure limits present, and
  Render API key redacted-present.
- Verify deployed API/app commits before strict canaries. Closed locally:
  `.github/render-env-sync.sh api-deploy-status` and `web-deploy-status` print
  the latest `argus-api` and `argus-app` deploy ids/statuses/commits/timestamps
  without mutating Render, and the launch runbook now requires API deploy-status,
  app deploy-status, warmup, English canary, and Spanish canary to pass against
  the intended readiness commit before tester invites.
- Run warmup/canary. Closed live on 2026-06-16: warmup passed with API health,
  `/internal/readiness?force=true`, stale-job scan, frontend, and real-workflow
  mode verification; the authenticated canary then passed confirmation,
  structured `run_backtest`, async workflow completion, persisted messages,
  Supabase verifier checks, result-summary route receipt, and LLM readout voice.
- Keep issue 112 duplicate-read regression tests green until merge. Closed
  locally on 2026-06-16 for valid confirmation reuse, stale confirmation ID,
  and canceled stale-checkpoint run guardrails.
- Add or document daily canary automation. Closed locally:
  `.github/workflows/private-alpha-canary.yml` runs the real-workflow warmup and
  authenticated canary manually or on a daily schedule once GitHub secrets are
  configured.
- Add stale job scan. Closed locally in the readiness branch:
  `.github/stale-backtest-jobs.sh` checks stale queued/running jobs before
  tester warmup when Supabase verifier credentials are present.
- Add minimal alpha metrics extraction. Closed locally:
  `scripts/ops/alpha_readiness_metrics.py` emits aggregate-only backtest job
  health, readout provenance, and latency summaries from existing
  `backtest_jobs.execution_metadata`; it does not add analytics vendor
  instrumentation or emit user/conversation/prompt identifiers.

### Slice 6: Product Analytics Plan

- Postpone PostHog for the current solo readiness pass. Keep it disabled until
  event taxonomy, redaction, consent posture, and founder approval land.
- Implement consent-aware product analytics only if needed after first sessions
  and after the no-touch boundary is lifted.
- Use Supabase feedback, route receipts, and founder notes for the first
  observed alpha cohort.

### Slice 7: Cold Start And UX Research Readiness

- Replace exact-date 2024 starter actions with natural rolling-window examples.
  Closed locally in the readiness branch.
- Update English and Spanish placeholder prompts together. Closed locally in
  the readiness branch.
- Verify clicked starter chips still enter the normal interpreter path. Covered
  by backend natural-time regression tests and the 2026-06-16 local browser QA
  pass.
- Add cold-start prompt slate to the browser QA checklist. Closed locally in the
  launch runbook smoke test: the final checklist now requires visible current
  starter chips, no default 2024 references, and a clicked starter entering the
  normal chat runtime.
- Tighten the founder/operator smoke checklist for exposed artifact actions.
  Closed locally: the private launch runbook now requires `Run backtest`,
  `Change dates`, `Change asset`, `Adjust assumptions`, `Cancel`, result
  `Quick take`, `Explain result`, structured retry, reload, and feedback checks.
- Update founder observation sheet to track whether starters feel current and
  approachable. Closed locally in this readiness panel.

## Readiness Exit Criteria

Argus is ready for the first controlled alpha tester when:

- Spanish direct backtest, DCA, approval, mixed-asset clarification, and result
  follow-up tests pass locally.
- Spanish recovery/failure copy is localized and retryable through structured
  metadata, not prose matching.
- Focused backtest trust tests pass.
- Focused security tests pass.
- Terms/Privacy/consent are live and linked.
- Feedback submission persists to Supabase with redacted context.
- Render env check, warmup, and canary pass.
- Issue 112 has merged or remains explicitly tracked with passing duplicate-read
  and stale-confirmation guardrail coverage.
- Cold-start starter actions and placeholder prompts are natural, current,
  bilingual, and free of stale default 2024 examples.
- Active confirmation edits preserve explicit user date changes before
  execution.
- Manual/live smoke plus scripted Playwright verify login, chat, Spanish prompt,
  confirmation actions, run, result, Quick take, Explain result, reload, retry,
  and feedback.
- Known caveats are written in founder-facing tester notes.
