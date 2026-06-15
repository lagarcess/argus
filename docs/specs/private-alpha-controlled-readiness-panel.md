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
     rolling range. Spanish browser QA still has an open over-clarification gap:
     a messy `ultimos 12 meses` answer can ask the user to restate the rolling
     window instead of accepting it as canonical temporal intent. This is a
     local runtime-spine proof, not the full Spanish release gate.

2. **Backtest trust hardening**
   - Provider-backed symbol validation even when `asset_class` is explicit.
   - Execution/chart/metric parity tests.
   - DCA wording and config clarity.
   - Persisted `config_snapshot` reproducibility.
   - Benchmark coverage and missing-data tests.

3. **Security and tenant hardening**
   - Production secure cookies.
   - Allowlist/auth response normalization.
   - Short-window quotas and accurate rate-limit behavior.
   - Parent ownership checks for service-role write paths.
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
| Spanish execution | Spanish natural language must reach the same executable interpreter and backtest path as English. Focused local proof now exists for messy buy-and-hold prompts with shorthand capital; the broader Spanish matrix still must pass. | Most controlled users prefer Spanish; static UI translation without execution breaks the core promise. |
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
| Confirmation action I/O | Resolved locally on `codex/private-alpha-readiness`; [GitHub issue 112](https://github.com/lagarcess/argus/issues/112) should close after merge. Valid confirmation actions now reuse one recent-message read before entering runtime. | This remains a latency-sensitive action path that owns stale-confirmation guardrails, so the focused regression coverage must stay green. |
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

Argus is not ready for Spanish-first controlled-alpha execution yet, but the
main runtime gap has moved from architecture risk to matrix coverage risk for
the first supported shape. The runtime shape is correct: LangGraph is the
conversational spine, normal language reaches structured interpretation first,
and deterministic validation comes afterward. The readiness branch now has
local work for canonical interpreter metadata, natural-time normalization,
registry-backed strategy aliases, localized artifacts, structured recovery, and
a focused capital-fidelity audit that catches when the LLM preserves `100k`
only in draft prose instead of the canonical field. The remaining gap is proving
that those pieces hold across the full Spanish execution matrix and live
production-like Render canary.

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
  fallback copy have local Spanish coverage, but the full chat flow still needs
  live provider/auth/browser proof.

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

- Add parity tests for duplicate entries, exits while flat, same-bar entry/exit,
  and DCA accumulation.
- Assert metrics, chart markers, and stored trades agree.

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

- Persist enough normalized config and data assumptions to reproduce the run.
- Add a persistence test that rebuilds a run from `config_snapshot` and gets the
  same key metrics.

#### Benchmark Alignment

Benchmark construction uses forward/back fill. This can hide missing benchmark
coverage at the start of a period.

Action:

- Add tests where the benchmark starts late or has sparse data.
- Reject or disclose missing benchmark coverage instead of silent backfill.

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

- Force secure cookies in production.
- Verify deployed `Set-Cookie` contains `HttpOnly`, `Secure`, and `SameSite=Lax`.

Relevant code:

- `src/argus/api/dependencies.py`
- `render.yaml`

#### Private-Alpha Allowlist Enumeration

Login/signup can reveal differences between unlisted emails and listed emails
with wrong passwords. Signup may also return raw provider exception text.

Action:

- Normalize public auth errors.
- Add auth endpoint throttling.
- Keep detailed reasons in logs only.

Relevant code:

- `src/argus/api/routers/auth.py`

#### Incomplete Rate Limits

The API emits static rate-limit headers, while chat primarily enforces a daily
quota. The documented short-window limits are not clearly enforced on every
expensive path.

Action:

- Add short-window limits for chat, auth, backtests, and feedback.
- Ensure `429` responses include accurate `Retry-After`.
- Avoid misleading `X-RateLimit-*` headers.

Relevant code:

- `src/argus/api/dependencies.py`
- `src/argus/api/routers/agent.py`
- `src/argus/domain/supabase_gateway.py`

#### Service-Role Parent Ownership

The backend intentionally uses a Supabase service-role client. That makes
application ownership checks critical for write paths that accept parent IDs.

Action:

- Validate conversation ownership before backtest or strategy writes that attach
  to a conversation.
- Validate collection ownership before collection-strategy upserts.
- Add cross-user IDOR tests.

Relevant code:

- `src/argus/api/routers/backtest.py`
- `src/argus/api/routers/strategies.py`
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

Issue 112 is resolved locally on `codex/private-alpha-readiness` and remains
open on GitHub until the branch is merged. Valid confirmation actions share one
recent-message read between stale-confirmation validation and confirmation
metadata fallback, while stale confirmation actions still stop before runtime.

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
poetry run python scripts/benchmarks/render_internet_benchmark.py --repeat 1
```

### Daily Automation Candidates

For controlled alpha:

- real-workflow mode drift check;
- warmup plus canary;
- stale queued/running job reconciler;
- OpenRouter credit/rate-limit check;
- Supabase error-log scan;
- small metrics extractor over `backtest_jobs.execution_metadata`.

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

### Gaps

- Feedback payload lacks hard backend length caps.
- Feedback context accepts arbitrary client keys.
- Frontend sends full `window.location.href`, including query/hash.
- "Learn more" in the feedback footer is not wired to the Privacy Policy.
- Account deletion request enriches context with email/user id, so this path
  needs privacy disclosure and access discipline.
- No attachment upload exists, which is good for alpha, but UI wording should
  not imply attachments are stored if they are only counted.

### Controlled Alpha Feedback Plan

Before users:

- Add backend caps:
  - message length;
  - context JSON byte size;
  - context key allowlist;
  - per-user feedback rate limit.
- Redact feedback URLs:
  - origin + pathname is enough;
  - drop query and hash.
- Keep file uploads disabled.
- Make feedback footer "Learn more" link to Privacy Policy.
- Verify Supabase persistence with the launch runbook count query before and
  after a feedback submission.

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
- Browser QA remains part of the final readiness batch because the copy change
  is only locally verified in this slice.

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

## No-Touch Boundaries For Current Solo Execution

The current Codex-owned readiness pass must not implement or configure:

- Governance, legal, privacy-policy, Terms, consent, company-operator, or safety
  gate work.
- PostHog instrumentation, session replay, event capture, or product analytics
  activation.

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
- Add or finish Spanish prompt matrix coverage for indicator/signal-rule
  prompts, currency pairs, unsupported valuation requests, setup edits, approval
  turns, and result follow-ups.
- Local QA with Spanish prompts across the whole matrix, including at least one
  error/recovery path.
- Live QA with at least one Spanish prompt in Render staging.

### Slice 2: Alpha Trust And Legal Shell

- Add Terms page.
- Add Privacy Policy page.
- Add Spanish summaries or translated pages.
- Wire signup/settings/profile links.
- Add alpha clickwrap consent.
- Configure support email and deletion request copy.

### Slice 3: Security And Feedback Hardening

- Force secure cookies in production.
- Normalize allowlist auth errors.
- Add short-window quotas.
- Add parent ownership checks.
- Add feedback caps/context allowlist/url redaction.
- Add focused tests for each.

### Slice 4: Backtest Trust Hardening

- Fix explicit asset class resolution bypass. Closed locally in the readiness
  branch.
- Add execution/chart/metric parity tests.
- Add benchmark sparse coverage tests.
- Add config snapshot reproducibility tests.
- Clarify DCA result assumptions. Closed locally in the readiness branch.
- Gate unsupported DCA total-budget/starting-principal requests where the
  interpreter has not already done so. Covered locally by the existing DCA
  semantic-role audit and clarification matrix.

### Slice 5: Workflow And Observability Gate

- Verify Render env status command.
- Run warmup/canary.
- Keep issue 112 duplicate-read regression tests green until merge.
- Add or document daily canary automation.
- Add stale job scan.
- Add minimal alpha metrics extraction.

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
  by backend natural-time regression tests; live browser QA remains in the final
  readiness batch.
- Add cold-start prompt slate to the browser QA checklist.
- Update founder observation sheet to track whether starters feel current and
  approachable.

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
- A manual smoke test verifies login, chat, Spanish prompt, confirmation, run,
  result, Quick take, Explain result, reload, and feedback.
- Known caveats are written in founder-facing tester notes.
