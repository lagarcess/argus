# Listing enrichment reuse map (code)

Read at `f0a90763b` on `origin/codex/private-alpha-next`. Paths are relative to the repository root. The audit was read only. Four read-only explorer agents located candidates. Every path:line cited here was then opened in this session. Nothing ran except grep, sed, git show, and one local Node `Intl` check (area 5).

Three corrections to the audit's starting premises:

- `tests/research/test_research_truth_boundary.py` does not test cache scope. It locks a different rule: research figures never reach the simulation (lines 1-14). The public-only cache rule lives in `src/argus/domain/research/cache.py:1-6`, `tests/research/test_research_cache_isolation.py`, and `docs/API_CONTRACT.md:4568`.
- FX conversion exists, but narrowly. `dollar_rate` converts eight major currencies to USD and returns None for DOP.
- No financial-records UI sketch exists in `web/` at this commit. The docs place it in an unmerged `money-view/` pilot on other branches (area 8).

Doc drift found in passing. `docs/API_CONTRACT.md:4575-4577` says discovery cache eligibility reads existing runtime provenance "without additional resolver calls". Since `f0a90763b`, `src/argus/agent_runtime/research_find.py:32-63` resolves every anchor through the asset catalog instead. That commit touched four files and none of them was the contract.

## 1. Provider adapters and outbound HTTP

There is no shared HTTP client or transport. Grepping for `httpx.Client`, `httpx.get/post`, `urlopen`, and `smtplib` finds 18 construction sites in 11 modules. Almost every site opens a fresh client per call. The long-lived clients are the Supabase gateway's `httpx.Client(timeout=120)` and the `lru_cache`d alpaca-py SDK clients.

Timeouts are one number per call site, and httpx applies it to each phase (connect, read, write, pool), not to the whole request. Values: 0.75 s for PostHog, 8 s for FRED and Alpaca context, 10 s for Kraken and SMTP, and 15 s for Render dispatch.

Exactly one client retries: the Perplexity agent client. OpenRouter moves to the next configured model instead of retrying. Everything else makes a single attempt.

Error shapes differ by provider:

- Closed-reason typed exceptions on the research paths.
- `ValueError` string codes in market data.
- Raw httpx exceptions for FRED, Alpaca context, and Render.

Provider modes exist only for market data. Other adapters stay hermetic in tests through an injectable `transport`. Budgets sit in callers, not in a transport: a per-turn call permit, an atomic Supabase ceiling claim, and a wall-clock budget for context fan-out.

Every httpx call sends the default User-Agent `python-httpx/0.28.1` (httpx 0.28.1, `httpx/_client.py:119`). Only the Kraken helpers send `Argus/1.0`.

Nothing fetches or parses an HTML page, reads robots.txt, throttles per host, sets a redirect policy, caps response size, or mentions SuperCarros or SuperCasas.

| path:line | symbol | what it does | verdict |
|---|---|---|---|
| `src/argus/domain/research/search/http_post.py:10` | `post_json` | One POST on a new `httpx.Client`. Maps each failure to a typed reason: timeout, 401/403, other status, transport error, or bad JSON. No retry. | **reusable pattern**. The failure map fits, but the helper handles POST with JSON only. An HTML GET needs its own owner: an HTML body would land in `malformed_response` and any 3xx in `http_error`. |
| `src/argus/domain/research/search/contracts.py:32` | `SearchUnavailableError` (reasons at :13) | Closed five-reason failure. An unknown reason raises. | **reusable pattern**. A listing-source contract needs `not_found`, `blocked` and `rate_limited` added. |
| `src/argus/domain/research/search/contracts.py:93` | `sanitize_search_result` | Drops non-https and over-long URLs, strips control characters, caps title and snippet, ISO-normalizes the date. | **reusable pattern**. Bound every scraped field at the boundary the same way. |
| `src/argus/domain/research/search/perplexity_direct.py:24` | `PerplexityDirectProvider` | Single-attempt adapter with an injectable `transport`. `require_configured` (:65) fails before admission. | **reusable pattern** for the adapter shape. As a data source it is paid search snippets, not listings. |
| `src/argus/domain/research/search/selection.py:17` | `search_provider_for_config` | Maps a provider id to its adapter. Unknown ids fail closed as `not_configured`. | **reusable pattern**. |
| `src/argus/domain/research/perplexity_agent.py:329` | `PerplexityAgentClient._post`, `_retry_delay` (:451), `_retry_after_seconds` (:486) | The only transport retry. At most 3 attempts (:447), 1 s backoff doubling (:448) or the server's Retry-After. Retries only on 429, 5xx, or a connect error before sending (`_UNSENT_ERRORS` :478), and only while half the deadline remains. | **reusable pattern**. Lift it into a shared owner. For a public site, honor Retry-After and never re-request a page the site already served. |
| `src/argus/domain/research/contracts.py:167` | `ResearchUnavailableError` (`paid_work_ruled_out` :202, `transient` :213) | Typed failure carrying status, retry-after and `sent`. | **reusable pattern**. |
| `src/argus/domain/market_data/provider.py:114`, `src/argus/domain/market_data/assets.py:119` | `_kraken_public_get` (two copies) | The only unauthenticated public GETs. `urlopen(timeout=10)`, User-Agent `Argus/1.0`, JSON only. urllib errors are not mapped. | **merely similar**. A duplicated helper with no status map, which also shows no transport owner exists. |
| `src/argus/domain/market_data/assets.py:96` | `_asset_provider_mode` | Reads `ARGUS_ASSET_PROVIDER_MODE`, then `ARGUS_MARKET_DATA_PROVIDER_MODE`. Modes: `live_provider`, `recorded_provider_fixture`, `synthetic_unit_fixture`. Unknown values raise. Recorded mode reads `ARGUS_ASSET_FIXTURE_PATH` (:367). | **reusable pattern**. Copy this fail-closed live/recorded/synthetic switch for listing sources. |
| `src/argus/domain/market_data/provider.py:309` | `fetch_ohlcv` | Only the exact string `synthetic_unit_fixture` is offline. Anything else goes live, including `recorded_provider_fixture` or a typo. | **merely similar**. Do not copy this mode check. |
| `src/argus/domain/market_data/tradability.py:176` | `_run_budgeted` | Pool of 4 workers, at most 16 pending, one in-flight probe per key, bounded wait. An `unknown` result is never cached (:33-36). | **reusable pattern**. The template for an active/gone/unknown listing probe where an outage is never stored as "gone". |
| `src/argus/context/providers.py:41` | `fetch_fred_macro_packet` and siblings | `httpx.get(timeout=8.0)`, no retry, raw exceptions. The FRED key rides the query string (:55). Pure `build_*_packet` normalizers are kept separate. | **reusable pattern**. Keep the split between fetching and pure normalizing. The fetch half is too bare to reuse. |
| `src/argus/api/chat/context_packets.py:208` | `_collect_packets_with_budget` | Thread-pool fan-out under one wall-clock budget. Records a typed status per source: attached, stale, skipped or timed_out. | **reusable pattern** for a two-site sweep. |
| `src/argus/api/chat/research_evidence.py:109` | `claim_research_provider_attempt` | Atomic Supabase RPC `claim_research_usage` enforcing a global daily ceiling. Fails closed. | **reusable pattern**. The only cap that holds across instances. A fetch budget needs its own resource key. |
| `src/argus/domain/research/admission.py:88` | `admitted_provider_work` | Claims capacity per turn. Releases the claim on error; keeps it on success or cancel. | **merely similar**. Held in a turn-scoped context var, and a periodic job has no turn. |
| `src/argus/api/rate_limits.py:8` | `SlidingWindowLimiter` | In-process sliding window that returns a retry-after value. | **reusable pattern**. Works as a per-host throttle inside one process only. |
| `src/argus/llm/openrouter.py:421` | `invoke_openrouter_json_schema` | New `AsyncClient` for each candidate model (:475), total cap via `wait_for`, moves to the next model on failure. | **reusable pattern**, but only if an LLM normalizes listing text. That prompt would be measured model-facing text. |
| `tests/research/conftest.py:155` | `RecordingTransport` | An `httpx.BaseTransport` that serves recorded documents and records each request. | **direct reuse** as the test seam. New adapters should accept `transport`. |

## 2. Evidence and source provenance

A source and its retrieval date are stored in three places:

1. **Research sidecar.** Research turns write it into assistant `messages.metadata.research`, with a closed key set. Its `sources` entries have the shape `{title, domain, url, source_date}`, beside a `retrieved_at` stamp. Each typed row carries `as_of` and `source_url`.
2. **Tool result cards.** They carry per-fact provenance in `ToolFactSource`: a kind, plus title, url and date for a page.
3. **Durable tables.** `evidence_artifacts` holds backtests only. `context_packets` holds provider, `retrieved_at`, `source_ids`, freshness and `not_for = 'simulation_truth'`, and it is user-owned. `decision_notes` holds decisions.

Provider identity is scrubbed from user output. Route receipts and the cost ledger own provider provenance. The web renders one citation list, `domain · date`, and formats a date-only value in UTC so a publisher's calendar date never shifts.

The "provenance dict convention" is mostly untyped dict sidecars. Typed provenance exists only for asset resolution (`ResolutionProvenance`, `src/argus/agent_runtime/state/models.py:204`) and memory.

| path:line | symbol | what it does | verdict |
|---|---|---|---|
| `src/argus/agent_runtime/research_grounded.py:93` | `RESEARCH_SIDECAR_KEYS`, `build_research_sidecar` (:2317) | Closed sidecar keys, asserted at :2362. Read back from message metadata, for example at `src/argus/api/chat/confirmation_research_peers.py:83`. | **merely similar**. This is the research-turn surface; an estimate should not ride it. |
| `src/argus/agent_runtime/research_grounded.py:2214` | `typed_sources` | Builds `{title or domain, domain, url, source_date}` from the pages the answer cites. | **reusable pattern**. The one source shape the web already renders. |
| `src/argus/domain/research/contracts.py:315` | `ResearchSource` | url, title, source_date. | **reusable pattern**. |
| `src/argus/domain/research/contracts.py:65` | `RetrievedRow` | A cited figure: subject, label, float `value`, kind, ISO `unit`, `as_of`, `source_url`. Its attribute docstrings are the provider's schema, frozen by a recorded probe (:57-63). | **merely similar**. Provider-facing and float-valued. A listing observation needs its own model. |
| `src/argus/domain/research/contracts.py:48` | `PROVIDER_HOSTS` (:50) | Provider hosts never reach user output. Receipts and the ledger own provider provenance. | **reusable pattern**, used as a rule. |
| `src/argus/domain/research/source_selection.py:59` | `select_public_sources`, `_publisher_key` (:130) | Keeps period-plausible sources, one page per publisher, at most five. | **merely similar**. It would collapse every SuperCarros comparable into one citation. |
| `src/argus/domain/tool_contracts.py:91` | `ToolFactSource` (kinds at :34) | Kinds are user, page, market_data, assumption, computed, not_found. Only `page` carries title and url; `page` and `market_data` carry a date. | **direct reuse**. A comparable's asking price is a `page` fact with URL and date; the range is `computed`. |
| `src/argus/context/packets.py:30` | `ContextPacket`, `ContextPacketFact` (:20) | provider, packet_type, scope, source_ids, retrieved_at, coverage window, freshness, facts with `observed_at` and `source_id`, limitations, and `not_for` (:46). | **reusable pattern**. The closest observation-packet shape, but its providers are a closed `fred`/`alpaca` Literal. |
| `supabase/migrations/20260519000001_add_context_packets_route_receipts.sql:4` | `context_packets` | The same columns, with `user_id` NOT NULL, a provider check `('fred','alpaca')` (:7) and a `not_for` check (:17). | **merely similar** as storage. Public listings are not user-owned. |
| `src/argus/api/schemas.py:489` | `EvidenceArtifact`, `EvidenceArtifactType` (:78) | Bound to an idea and idea version. The only type is `backtest`. | **merely similar**. |
| `src/argus/domain/evidence.py:308` | `_data_window_provenance` | Records the requested window against the effective window, plus the dataset id. | **reusable pattern**. Record the requested period against the observed period of an observation set. |
| `src/argus/memory/contracts.py:94` | `MemoryProvenance` | A source_kind, source_id, source_version pointer. | **reusable pattern**. |
| `web/components/chat/ResearchSourcesList.tsx:26` | `ResearchSourcesList`, `formattedSourceDate` (:12) | Renders `domain · date` links, with a date-only value formatted in UTC. Takes `DiscoverySource` (`web/components/chat/types.ts:388`). | **direct reuse** for listing citations once the backend supplies the four fields. |
| `web/lib/receipt-copy.ts:85` | `formatReceiptDay` | A frozen calendar day in en-US or es-419, formatted in UTC. | **direct reuse**. |

## 3. Caching and freshness

The shared research cache is a module-level dict (`src/argus/domain/research/cache.py:154`) in each API worker. It holds at most 512 entries and is never persisted.

**Keying.** Only direct Perplexity Search discovery packets get a key. The key is `public-discovery-packet/v2:` followed by the sha256 of the JSON list `[contract, query, provider_id, max_results]`. The query is the deterministic string `_search_query` builds from uppercased anchors, so no user prose enters it.

**Isolation happens in four layers:**

- Eligibility is checked before any key exists. `_public_anchor_search` shares a search only when it has no category and the catalog resolves every anchor to the requested class.
- Grounded answers never read or write the cache. They contain unrestricted text and the asker's country and currency.
- The storage boundary rejects any value that is not a `SearchResultPacket`, and any key with an old prefix.
- Extraction and voicing stay per turn.

**Expiry.** Each entry stores a monotonic `stored_at` and a TTL. Every put uses the 300 s movers TTL. An expired entry is deleted on read. At 512 entries the oldest is evicted. No background sweep or hosted purge exists (`docs/API_CONTRACT.md:4585-4586`).

**Market data** uses two other caches:

- A joblib disk memo keyed by the time bin `int(time)//ttl`. Nothing is ever evicted.
- An in-process asset catalog that reloads on TTL or when the provider mode changes.

Both caches read `MARKET_DATA_CACHE_TTL`, in two duplicate functions. A declarative freshness registry exists in `src/argus/context/freshness.py`.

| path:line | symbol | what it does | verdict |
|---|---|---|---|
| `src/argus/domain/research/cache.py:1` | module contract | Holds public-market discovery packets only. Free-form questions, categories, criteria and personalized answers bypass it. | **merely similar**. Nothing derived from a user's vehicle or property may enter it. |
| `src/argus/domain/research/cache.py:163` | `research_cache_key`, `CACHE_CONTRACT` (:160) | Versioned identity. `cache_get` rejects other prefixes (:205). | **reusable pattern**. Bumping the contract invalidates every old key. |
| `src/argus/domain/research/cache.py:176` | `SearchPacketCache` | Keys only `perplexity_direct` (:182-188). Every put uses the movers TTL (:199). | **merely similar**. Per worker and in memory only. |
| `src/argus/domain/research/cache.py:221` | `cache_put` | Rejects non-`SearchResultPacket` values. Evicts the oldest entry at 512 (:229-231). | **merely similar**. |
| `src/argus/domain/research/cache.py:46` | `DATA_CLASS_TTL_SECONDS`, `WITHHELD_TTL_SECONDS` (:58) | TTL per market data class, from 120 s to 90 days. A withheld packet is capped at one day. | **reusable pattern**. A TTL table keyed by data class. |
| `src/argus/agent_runtime/research_find.py:32` | `_public_anchor_search` | Shares a search only when the catalog resolves every anchor. Runs off the event loop (:93-95). | **reusable pattern**. Check eligibility before building an identity. |
| `src/argus/agent_runtime/discovery/composer.py:532` | `_search_query` | Deterministic machine query built from typed fields, never user prose. | **reusable pattern**. Build listing search URLs from typed facets only. |
| `src/argus/domain/research/config.py:287` | retrieval `location` | Sends the asker's declared country as the search location. | **merely similar**. It shows why grounded answers are personal and never shared. |
| `tests/research/test_research_cache_isolation.py:84` | `test_private_context_never_enters_shared_storage` | Private balance text generated with Faker never reaches the cache. | **reusable pattern**. Copy this test for any listing cache. |
| `tests/research/test_research_truth_boundary.py:168` | `FORBIDDEN_IN_RESEARCH` | A source scan proving research code never calls simulation entry points. | **reusable pattern**. Estimates come from stored observations computed in code, never from model prose. |
| `src/argus/domain/market_data/provider.py:289` | `_fetch_bars_with_ttl`, `_memory` (:38) | joblib disk memo keyed by the time bin. Nothing is evicted. | **merely similar**. |
| `src/argus/domain/market_data/provider.py:41`, `src/argus/domain/market_data/assets.py:78` | `_cache_ttl_seconds` (two copies) | Reads `MARKET_DATA_CACHE_TTL` with default 900 and floor 60. Production sets 43200 (`render.yaml:25-26`). | **merely similar**. Two owners for one setting. |
| `src/argus/domain/market_data/assets.py:511` | `_refresh_asset_cache_if_needed` | Double-checked lock. Reloads on TTL or when the provider mode changes. | **reusable pattern** for an in-process reference catalog, such as makes and models. |
| `src/argus/context/freshness.py:33` | `_POLICIES`, `FreshnessPolicy` (:24) | Maps each subject to a TTL plus `cacheable` and `durable` flags. | **reusable pattern**. A freshness registry, though its subjects are a closed market Literal. |
| `src/argus/context/freshness.py:65` | `context_packet_freshness` | Decides fresh or stale from `retrieved_at` and the subject's TTL. | **reusable pattern**. |

## 4. Background jobs and scheduling

No scheduler runs product work. `render.yaml` declares two web services. It has no cron and no worker, the migrations have no `pg_cron`, and the API lifespan starts no periodic loop.

A Render cron named `argus-maintenance` (`*/15`, running `scripts/ops/scheduled_maintenance.py`) was removed in `9513fa37a` as never created. A test now keeps it absent. The runbook and `.env.example` say maintenance is operator-run from a laptop, and they forbid a scheduled service or copying its credentials into CI. `docs/DATA_MODEL.md:426` still says the maintenance script "runs it daily", which is stale.

Background execution uses Render Workflows (`argus-backtests`). The API dispatches a task run inside a user request, after admitting a job row. Render Blueprints cannot declare workflow services (`docs/specs/private-alpha-ci-cd-sota.md:147-148`).

Jobs share `backtest_jobs`, which is user-owned. Idempotency rests on the unique index `(user_id, operation_scope, idempotency_key)` (`supabase/migrations/20260722000002_atomic_backtest_admission.sql:18-20`), taken under a global advisory lock (:72). The admission RPC admits only `chat.run_backtest` and `backtests.run` (`supabase/migrations/20260724102309_add_guest_session_allowances.sql:295-296`). Its capacity counts rows of every scope (:392-399). Thorough research reuses the table and finishes in an in-process poller. The only schedules are GitHub Actions: a daily canary and a nightly test sweep.

**Answer.** A periodic listing refresh cannot run on existing machinery without a new trigger and a founder decision. The execution half is reusable: a Workflows task plus the dispatcher. The archived roadmap already set a rule for Dominican sources: load once a day into the database and never call them while a person waits (`docs/archive/2026-09-26-argus-answers-that-stay-true-roadmap.md:80-82`).

| path:line | symbol | what it does | verdict |
|---|---|---|---|
| `render.yaml:2` | `argus-api`, `argus-app` (:158) | Two `type: web` services. Nothing here can hold a schedule. | **merely similar**. |
| `render.yaml` in commit `9513fa37a` (diff) | removed `argus-maintenance` | `type: cron`, `schedule: "*/15 * * * *"`, secrets declared `sync: false`. | **reusable pattern**. The exact entry shape, if the no-cron rule is reversed. |
| `tests/test_render_release_profile_contract.py:41` | `test_phantom_maintenance_surface_is_absent_but_operator_job_remains` | Asserts `argus-maintenance` is absent from `render.yaml`. | **merely similar**. A guard that a new schedule must change on purpose. |
| `scripts/ops/scheduled_maintenance.py:36` | `maintenance_jobs`, `run_job` (:63) | One operator pass. Each job runs as its own subprocess: retention, stale scan, welcome-claim release. | **reusable pattern**. Append a job here; it still has no clock (`docs/PRIVATE_LAUNCH_RUNBOOK.md:786-799`, `.env.example:268-271`). |
| `workflows/main.py:51` | `Workflows` app, `run_backtest_job` (:69) | Default retry 0. The backtest task retries once, with its timeout from env. | **reusable pattern**. Add a refresh task; it still needs a trigger. |
| `src/argus/api/chat/backtest_jobs.py:336` | `RenderWorkflowDispatcher.dispatch` | POSTs `{task, input}` to `RENDER_TASK_RUNS_URL` (:49) with timeout 15. | **direct reuse** to start a task run. |
| `supabase/migrations/20260606000001_add_backtest_jobs.sql:5` | `backtest_jobs` | Status, attempts, `idempotency_key`, `payload_hash`, `execution_metadata`. `user_id` is NOT NULL (:7). | **merely similar** for a global refresh: a system job must invent a user, as `workflows/proof.py:27` does. It stays usable for per-user enrichment jobs under a new scope. |
| `src/argus/domain/backtest_job_scopes.py:30` | `OPERATION_SCOPES` | The one owner of scope values. The SQL check constraint is rendered from it. | **reusable pattern**. A new scope needs the tuple entry plus a rendered migration. |
| `src/argus/domain/job_settlement.py:1` | settlement rule, `SQL_FUNCTION_NAME` (:155) | One lifecycle rule rendered to both Python and SQL. A test pins that they match. | **reusable pattern**. |
| `src/argus/api/chat/research_jobs.py:60` | `retain_research_work` | An in-process poller task. If the process dies, the stale scan settles the row. | **merely similar**. It dies on deploy and is not a scheduler. |
| `src/argus/api/chat/research_job_reconciliation.py:10` | module docstring | A janitor must not spend provider money or persist messages outside a request. | **reusable pattern**. A policy constraint that applies to any refresh job. |
| `src/argus/api/chat/backtest_jobs.py:244` | `_backpressure_reason` | Counts running and queued jobs in the database, per user and globally. | **reusable pattern**. |
| `src/argus/domain/guest_cleanup.py:77` | `cleanup_expired_guest_workspaces` | Bounded claim-then-purge batch with a dry-run flag. | **reusable pattern** for an observation retention janitor. |
| `.github/workflows/private-alpha-canary.yml:23` | cron `30 14 * * *` | The only schedule that touches production. | **merely similar**. It runs from GitHub runner IPs with CI-held secrets, which `.env.example` forbids for maintenance. |

## 5. Money and currency

There is no single money type or owner.

- `Money` stores a float amount and has no production caller.
- Calculations carry one ISO currency and emit float money facts.
- Research rows validate currency codes against Babel's CLDR list.
- Backtests, result cards and readouts are USD-only. `format_result_money` prints `$`, and the readout guard drops any non-USD money row.
- `Decimal` appears only at edges: half-up display rounding for results, and provider-cost reconciliation.
- The only money column in the schema is `cost_ledger_entries.cost_amount numeric(18, 8)` with `cost_currency` defaulting to `'USD'` (`supabase/migrations/20260702000001_add_cost_ledger_entries.sql:52-53`).

**DOP support.** DOP is valid as a profile currency (DO resolves to DOP through CLDR) and as a calculation currency. It does not render as `RD$`. `Locale` allows only `en-US` and `es-419` (`src/argus/api/schemas.py:63`), and in local Node `Intl` those locales render DOP as "DOP" or "$". Only es-DO renders "RD$". Wave-1 R2 requires `RD$` and `US$` and forbids a combined peso-plus-dollar total until a dated rate source exists (`docs/specs/wave-1/00-shared-rules.md:30`).

**Guests** carry no country or currency (`src/argus/api/schemas.py:204`).

**Storage recommendation on file.** The ledger assessment recommends integer minor units, Decimal FX with a named rounding mode, and balancing each currency on its own (`docs/reports/payment-ledger-reuse-assessment.md:11-17`).

| path:line | symbol | what it does | verdict |
|---|---|---|---|
| `src/argus/domain/finance/money.py:13` | `Money` | Float amount with a `[A-Z]{3}` shape check. Add and subtract only within one currency. | **reusable pattern**. Keep the refuse-to-mix rule, and store recorded values as Decimal or integer minor units. |
| `src/argus/domain/result_money.py:60` | `rounded_result_money` | `Decimal(str(value)).quantize(..., ROUND_HALF_UP)`. | **reusable pattern**. The one half-up helper. Its digits are per run, not per currency. |
| `src/argus/domain/result_money.py:42` | `stored_currency_fraction_digits` | Reads the digits stored once on a result card (the PR #621 owner) and clamps them to 0-2. | **merely similar**. Precision for one backtest run. |
| `src/argus/domain/result_money.py:66` | `format_result_money` | f-string with a hardcoded `$` (:69). | **merely similar**. USD only. |
| `web/argus_display_contract/result_display_policy.json:1` | shared display policy | One JSON file read by Python (packaged via `pyproject.toml:10`) and by the web (`web/lib/result-money.ts:9`). | **reusable pattern**. Share a listing display rule the same way. |
| `src/argus/domain/home_country.py:71` | `resolved_currency`, `country_currency` (:52), `CurrencyCode` and `TenderCurrencyCode` (:106-111) | CLDR-derived currency. The profile override wins. | **direct reuse** for the user's home currency and for code validation. |
| `supabase/migrations/20260911120000_add_profile_home_country.sql:15` | `profiles.country`, `currency_override` | Stored settings. | **direct reuse**. |
| `src/argus/domain/research/contracts.py:25` | `CURRENCY_CODES` | Babel's maintained ISO 4217 list, DOP included. | **direct reuse**. |
| `src/argus/domain/calculations/_shared.py:64` | `CalculationArguments.currency`, `money_fact` (:103) | One currency per calculation. A money fact carries a currency unit and is rounded with float `round(x, 2)` (`MONEY_DECIMALS` :32). | **direct reuse** to present a range card. Not the stored value. |
| `web/lib/tool-result-card.ts:169` | `currencyText` | `Intl.NumberFormat` with `currencyDisplay: "code"`, which renders "DOP 1,250,000.00". | **direct reuse**. |
| `web/lib/result-card-display.ts:669` | `formatCurrency` | Uses `narrowSymbol`, default USD. Local Node 26.8.2 (ICU 78.3) renders DOP and USD both as `$1,250,000.00` in en-US and es-419. | **merely similar**. A peso reads as a dollar. |
| `src/argus/agent_runtime/calculation_rows.py:168` | `dollar_rate` | Converts the 8 majors in `FIAT_CODES` (`src/argus/domain/market_data/assets.py:74`) to USD from Argus's latest close. Returns None for DOP. | **merely similar**. No DOP rate. Its rule of stating the rate and its date carries over. |
| `src/argus/agent_runtime/answer_calculation.py:762` | `_calculation_currency` | Currency order: stated amount, stated code, profile, then USD (`DEFAULT_CURRENCY` :58). Notes when the fallback fires (:822). | **reusable pattern** for recording when a default fires. The USD fallback conflicts with MVEE :260, "Do not infer dollars or pesos". |
| `src/argus/domain/result_readout_display_values.py:68` | readout currency guard | Returns None for a non-USD money row. | **merely similar**. |
| `tests/synthetic_ingestion/harness.py:15` | `field_issues` | Amounts must be decimal text with at most 2 places. Only `DOP` or `USD` are accepted (:34); a bare `$` stays unresolved. | **reusable pattern**. The currency must be explicit. No `RD$`/`US$` parser exists anywhere (`docs/reports/synthetic-ingestion-evaluation.md:47,57`). |

## 6. Account ownership and permissions

`auth.users` maps to `profiles.id`, and product tables carry `user_id` referencing profiles with `on delete cascade`. Owner tables use `for all` policies with `user_id = auth.uid()`. Shared, unowned tables use RLS with no policies plus a service_role grant.

**RLS is defense in depth only.** The backend reaches Supabase with the service-role key, which bypasses RLS. Each gateway method scopes rows in code with `.eq("user_id", ...)`.

**Guests** are anonymous profiles with a fixed 7-day `guest_workspaces` row. The API blocks them through capabilities. At signup their rows move only for tables the handoff function lists explicitly.

**No household, team, or sharing model** exists. The MVEE approves households, and `docs/DATA_MODEL.md:7` says financial records and household permissions still need schema and access-control design. Public receipts are owner-created frozen snapshots. The research cache is the only cross-user store, and it lives in process memory.

| path:line | symbol | what it does | verdict |
|---|---|---|---|
| `supabase/migrations/20260619000001_p1_evidence_decision_spine.sql:53` | `decision_notes` (RLS :100, policy :120-121) | `user_id` NOT NULL, cascades from profiles, owner `for all` policy. | **reusable pattern**. The best owner and RLS precedent for a new user-owned asset table. |
| `supabase/migrations/20260519000001_add_context_packets_route_receipts.sql:65` | `context_packets_owner_all` | `using` and `with check (user_id = auth.uid())`. | **reusable pattern**. |
| `supabase/migrations/20260911120000_add_profile_home_country.sql:35` | restrictive registered-only policies | `as restrictive` policies requiring `is_anonymous is distinct from 'true'` (:42), plus column grants (:60). | **reusable pattern**. Enforces registered-only access at the database layer. |
| `src/argus/domain/supabase_gateway.py:163` | `SupabaseGateway.from_env` | Builds the client from `SUPABASE_SERVICE_ROLE_KEY` (:165). | **direct reuse** as the write path, which requires explicit owner filters. |
| `src/argus/domain/supabase_decisions.py:35` | `.eq("user_id", user_id)` | Owner scoping in application code. | **reusable pattern**, and mandatory. |
| `src/argus/api/guest_access.py:91` | `guest_capabilities`, `registered_capabilities` (:106) | Guests get `can_save_decision=False`. | **reusable pattern**. Add a capability for recording assets. |
| `src/argus/api/dependencies.py:297` | `require_account_capability` | Returns 403 `account_conversion_required`. | **direct reuse**. |
| `supabase/migrations/20260724101324_add_guest_workspaces.sql:64` | `guest_workspaces` | Guests are profiles with a fixed 7-day expiry (:75-76). | **merely similar**. It sets guest policy, not storage. |
| `supabase/migrations/20260726185021_harden_guest_lifecycle_ownership.sql:18` | `argus_private.claim_guest_workspace_handoff` | Transfers ownership table by table; the first transfer update is at :165. | **reusable pattern**. Add every guest-writable table here and to cleanup, or keep guests out. |
| `supabase/migrations/20260727230000_add_visitor_usage_counters.sql:21` | `visitor_usage_counters` | Not bound to a user. RLS on with no policies; `revoke all`, then service_role only (:46-47). | **reusable pattern**. The deny-all shape for a shared public-observation table. |
| `supabase/migrations/20260702000001_add_cost_ledger_entries.sql:97` | append-only grants | Revokes everything, then grants back insert and select only (:99). | **reusable pattern**. Makes observations append-only by construction. |
| `supabase/migrations/20260807190000_add_public_excerpt_snapshots.sql:15` | `public_excerpt_snapshots` | Owner-created frozen public copies with a digest. | **merely similar**. A receipt, not a household share. |
| `src/argus/domain/tool_declaration.py:101` | `ToolPolicy.public_receipt` (values :85) | Defaults to `disabled`. | **direct reuse**. An estimate card stays unpublishable by default. |

## 7. Notifications and saved-answer tracking

Two emails exist, both sent through one Resend SMTP transport:

- **Access welcome.** Triggered from an ops-token route. It claims first, sends, then records completion, with a claim-derived idempotency key.
- **Feedback notice.** Goes to the support inbox only.

None of these exist: a notification table, an in-app inbox, push, a watchlist, saved-answer tracking, or a scheduled re-check. Four constraints bound any future notice:

- `docs/PRODUCT.md:99` lists notifications as hidden.
- The MVEE plans an Updates inbox that includes "records needing review or refresh". It forbids amounts in push or email previews (`docs/specs/argus-minimum-viable-ecosystem-experience.md:155-163`).
- Wave-1 R4 keeps amounts out of emails, push, analytics and logs (`docs/specs/wave-1/00-shared-rules.md:32`).
- The "stays true" roadmap is an archived pointer (`docs/specs/argus-answers-that-stay-true-roadmap.md:3`).

What does exist is user-initiated re-checking. A computed answer can be refreshed beside the stored one, and a saved decision re-runs its stored computation when opened.

| path:line | symbol | what it does | verdict |
|---|---|---|---|
| `src/argus/domain/resend_email.py:30` | `send_resend_email` | SMTP over SSL with a 10 s timeout (:20). Optional `Resend-Idempotency-Key` header (:48-49). | **direct reuse** as the transport. The content must carry no amount. |
| `src/argus/domain/access_approval_email.py:132` | `_idempotency_key`, `send_access_welcome_email` (:140) | sha256 of a namespace plus the claim token. | **reusable pattern**. |
| `supabase/migrations/20260812173805_claim_access_welcome_delivery.sql:1` | claims table, claim function (:21), complete function (:116) | Durable claim, then send, then completion with the provider receipt. | **reusable pattern** for exactly-once delivery. The docs accept one duplicate welcome after a lost completion (`docs/DATA_MODEL.md:427-429`), so a notice ledger must own exactly-once itself. |
| `src/argus/api/routers/ops.py:229` | `approve_access_request` | Ops-token route: claim (:259), send (:277), then complete. | **merely similar**. Operator-triggered. |
| `src/argus/api/feedback_notification.py:68` | `notify_feedback_submitted` | Support-only email. Failures are logged and dropped. | **merely similar**. |
| `src/argus/api/chat/computed_answers.py:315` | `refresh_computed_answer` | Re-reads the answer's cited page inputs through the research allowance and computes a new card beside it. "The stored answer never moves." | **reusable pattern**. Propose beside the recorded value and never overwrite it. Its lookup is paid research, not a listing fetch. |
| `src/argus/api/routers/computations.py:104` | refresh route | Errors: 409 `nothing_to_refresh`, 429 capacity exhausted, 503 unavailable. | **reusable pattern** for the route and error vocabulary of a user-triggered re-check. |
| `src/argus/api/routers/decisions.py:101` | `rerun_decision_route` | Reopens a saved decision and re-runs its stored computation. | **reusable pattern**. Re-checks on open, without diffing against a stored baseline. |
| `src/argus/observability/analytics_events.py:177` | `RemindersOptedIn`, `RemindersOptedOut` (:183) | Analytics events only. No reminder storage or sender exists. | **merely similar**. |

## 8. Financial records

**Plainly, nothing exists.** This tree has no backend table, model, route or API for a user's accounts, assets, vehicles, real estate, debts, balances, net worth or valuations. It has no web UI sketch either.

**Database.** The 81 migration files create 43 tables. None holds a user's own finances:

argus_memory_vectors, backtest_jobs, backtest_runs, chat_turn_lifecycles, checkpoint_blobs, checkpoint_migrations, checkpoint_writes, checkpoints, collection_strategies, collections, context_packets, conversation_read_states, conversations, cost_ledger_entries, decision_notes, evidence_artifacts, feedback, guest_funnel_milestones, guest_workspace_handoffs, guest_workspaces, idea_versions, ideas, memory_candidates, memory_consent_actions, memory_prompt_history, memory_provenance, memory_provider_cleanup, memory_provider_projections, memory_reconciliations, memory_records, memory_settings, messages, private_alpha_access_welcome_claims, private_alpha_access_welcome_deliveries, private_alpha_allowlist, profiles, public_excerpt_snapshots, refusal_observations, route_receipts, run_context_packets, strategies, usage_counters, visitor_usage_counters.

**Backend terms mean something else:**

- "asset" is a tradable ticker, crypto or currency pair.
- "portfolio" is a backtest portfolio.
- "debt" is a stateless calculator.
- "vehicle" appears once in `src`, as an ETF "exposure vehicle".

**Web.** Grepping `web/` (excluding `node_modules` and `.next`) for vehicle, vehículo, propiedad, inmueble, real estate, net worth, patrimonio, pasivos and deudas finds only calculator labels in `web/public/locales/en/common.json` and the word "debt" inside two test files. The app routes are `account`, `api`, `auth`, `chat`, `dev`, `login`, `privacy`, `r`, `signup` and `terms`.

**Where the plans live:**

- The MVEE defines Accounts, "recorded assets and debts, separated by currency", and households as the approved direction (`docs/specs/argus-minimum-viable-ecosystem-experience.md:90,99-111`).
- Wave 1 hides net worth and accounts. It says those UIs "exist only in the unmerged `money-view/` pilot app" (`docs/specs/wave-1/00-shared-rules.md:34,505-510`), on branches `codex/money-placement-pilot` and `codex/money-placement-pilot-impl`. That pilot is a separate React/Vite app with FastAPI and local SQLite (`docs/archive/2026-09-26-argus-pivot-strategy.md:287`). Its rule is to port pure engine functions and never its UI, store or sessions (`docs/specs/wave-1/00-shared-rules.md:536-555`). I did not open those branches; they are outside the assigned commit.
- `docs/PRODUCT.md:182-186` forbids building financial records "as an assumed extension of legacy Strategy rows or generic memory".
- Archived decision 8 kept stated personal figures ephemeral, with "No new storage, no new retention surface" (`docs/archive/2026-09-17-argus-grounded-finance-roadmap.md:1791-1797`). Storing a vehicle or property value therefore needs an explicit founder decision.

| path:line | symbol | what it does | verdict |
|---|---|---|---|
| `src/argus/domain/market_data/assets.py:74` | `FIAT_CODES` and the asset catalog | "Asset" means a tradable instrument. | **merely similar**. |
| `src/argus/domain/calculations/debt_to_income.py:31` | `DebtToIncomeArguments`, declaration (:119) | Stateless per-turn calculator. Stores nothing. | **merely similar** as a record. It is a **reusable pattern** as a declared tool. |
| `web/public/locales/en/common.json:2016` | calculator labels | "Monthly debt payments" (:2016) and "Assets" (:2019) are calculator field labels. | **merely similar**. |

## 9. Proposal then confirmation patterns

Four families exist.

1. **The synthetic ingestion kit is test-only.**
   - Proposal ids are content-addressed.
   - Confirm and reject are explicit.
   - A correction requires a reason and keeps its revision.
   - An exact re-ingest is idempotent.
   - State is a local JSON file, "not an Argus database or an authorization model".
2. **Chat confirmation cards are backtest-specific.**
   - The proposal lives in assistant message metadata, with a content-independent pending-artifact state.
   - Run requires an Idempotency-Key bound to the confirmation.
   - Any edit re-runs every gate and mints a new confirmation id.
   - Only the backtest tool uses `confirmation="required"`.
3. **Personalization memory records consent.** A candidate becomes a consent receipt carrying `recorded_at` and an idempotency key, and then a record. It is admin-only and off-limits as a records store.
4. **`decision_notes` holds one mutable row per message or artifact.** Its states are `watching`, `promising`, `rejected` and `revisit_later`. It keeps no history.

No production store keeps an approver, a timestamp and prior values on the proposal itself.

| path:line | symbol | what it does | verdict |
|---|---|---|---|
| `tests/synthetic_ingestion/harness.py:114` | `Harness.ingest` | Proposal id is the sha256 of `digest:row` (plus any stub digest), cut to 24 characters. An exact re-ingest reuses it. | **reusable pattern**. Derive an observation id from the canonical listing URL plus a content digest. |
| `tests/synthetic_ingestion/harness.py:163` | `confirm` | Batch confirm. Skips rows already confirmed, which makes it idempotent. Rechecks issues at confirm time. | **reusable pattern**. |
| `tests/synthetic_ingestion/harness.py:197` | `correct` | Requires a reason. Appends `{before, after, reason}` revisions. | **reusable pattern**. Keep every estimate revision, adding who and when. |
| `tests/synthetic_ingestion/harness.py:189` | `reject` | Moves `proposed` to `rejected` with no reason and no date. | **merely similar**. Fails "recorded with source and date". |
| `tests/synthetic_ingestion/README.md:29` | scope statement | Simulated decisions over local state that is "not an Argus database or an authorization model" (:31-32). | **merely similar** as code. Test scaffolding with no owner. |
| `src/argus/domain/tool_declaration.py:92` | `ToolPolicy` (`confirmation` :95), `prepare_confirmation` (:455) | A tool can require confirmation, and then must supply a `confirmation_handler` (:290-291). | **reusable pattern**. An estimate-revision tool with `confirmation="required"`. |
| `src/argus/agent_runtime/tools/registered_backtest.py:58` | `get_backtest_declaration` | The only tool that requires confirmation. Runs as a workflow. | **merely similar**. The approval wiring is backtest-only. |
| `src/argus/api/routers/tool_results.py:40` | `ToolResultRecomputeRequest` (`input_revision` :44) | Optimistic `input_revision` check (:113-114). Liveness comes from a `tool_result_cards` layout (:92). Increments the revision (:145) and rewrites `metadata.computation`. | **direct reuse** for editing an estimate card in place. |
| `src/argus/domain/pending_artifacts.py:23` | `PendingArtifactLayout`, `stamp_pending_artifact` (:84) | States active, consumed, cancelled or superseded, stamped on message metadata. | **reusable pattern** through a new layout. Has no confirmed or rejected state and no timestamp. |
| `src/argus/domain/supabase_conversation_messages.py:94` | `update_message_artifact` | Owner-scoped compare-and-set rewrite of one message. | **direct reuse**. |
| `src/argus/api/chat/run_action_identity.py:32` | `require_run_action_identity`, `validated_optional_idempotency_key` (:11) | Run needs an Idempotency-Key of 1-128 visible ASCII characters, bound to the confirmation. | **reusable pattern**. The approval id equals the proposal id. |
| `src/argus/agent_runtime/confirmation_revalidation.py:28` | `revalidated_confirmation_candidate` | Re-runs every gate, then mints a new confirmation id (:63-69). | **merely similar**, because the gates are backtest gates. The rule that an edit mints a new identity carries over. |
| `src/argus/memory/contracts.py:245` | `MemoryConsentActionReceipt` (`MemoryCandidate` :210) | Owner, `recorded_at` (:259), `idempotency_key` (:260). Confirm keys on the candidate id (`src/argus/memory/postgres_store.py:787`). | **reusable pattern**. The closest proposal-receipt-record shape. Memory itself is admin-only (`src/argus/api/personalization_memory.py:6-8`) and not a records store. |
| `supabase/migrations/20260908120000_decision_notes_attach_to_computations.sql:33` | `computation`, `source_message_id` (:31) | Stores the decided computation. `unique (user_id, source_message_id)` (:48). | **merely similar**. The state vocabulary is about investing ideas (spine :60), and a decision keeps no history. |

## 10. Privacy guards

**Logs have no redaction processor.** One loguru sink runs with `diagnose` and `backtrace` off, and privacy is kept at each call site. 78 call sites pass `error=str(exc)` as a loguru extra. Those values stay out of production output only because the default sink format renders the message and not the extras.

**Analytics is a closed registry.** Its fields can hold no amount. The sink suppresses anything the registry did not build. Nothing in `src/` emits a registry event yet.

**The observability attribute sanitizer is a key-substring denylist.** It covers capital, holdings and account_balance. It has no entry for price, amount, value, estimate, address, plate, VIN or mileage.

**Memory** runs an LLM sensitivity classifier and fails closed.

Two written rules apply: wave-1 R4 keeps amounts out of emails, push, analytics and logs (`docs/specs/wave-1/00-shared-rules.md:32`), and the MVEE keeps amounts out of notification previews.

| path:line | symbol | what it does | verdict |
|---|---|---|---|
| `src/argus/log_sink.py:10` | `configure_logging` | One sink with `diagnose=False` and `backtrace=False`. | **direct reuse**. No local variable values reach tracebacks. |
| `src/argus/llm/openrouter.py:1016` | `log_openrouter_failure` | Logs task, model, error type and origin only. States that the default sink renders only the message. | **direct reuse**. |
| `tests/agent_runtime/test_private_log_content.py:42` (line 48 after #721) | `assert_safe` | Private sentinel text must not reach a serialized sink. | **reusable pattern**. Extend it to fetch and estimate call sites. |
| `src/argus/observability/analytics_events.py:116` | `AnalyticsEvent` registry (contract :1-12) | Fields are Literal, bool or a bounded int, so an amount cannot be represented. | **direct reuse**. A new event needs its own registry model. |
| `src/argus/observability/envelope.py:247` | `capture_event` | Suppresses any envelope the registry did not build. | **direct reuse**. |
| `src/argus/observability/envelope.py:111` | `_BLOCKED_KEY_PARTS`, `sanitize_observability_attributes` (:344), `_blocked_key` (:375) | Key-substring denylist. Strings pass through at up to 500 characters. | **reusable pattern**. Needs price, amount, value, estimate, address, plate, VIN and mileage entries. |
| `src/argus/api/feedback_context.py:17` | `_SCALAR_CONTEXT_KEYS`, `sanitize_feedback_context` (:47) | Key allowlist. | **direct reuse**. Listing fields drop automatically. |
| `src/argus/llm/memory_sensitivity.py:16` | `SensitivityFlagName` | Nine flags, including account_balance, exact_holdings and identifying_financial_detail. Fails closed. | **reusable pattern**. No flag names vehicles, plates, VINs or property. The prompt is measured text. |
| `src/argus/domain/tool_contracts.py:133` | `ToolInputFact.visibility` | Tool inputs default to `private`. | **direct reuse**. |
| `src/argus/api/chat/refusal_evidence.py:51` | `record_http_rejection` | Stores the raw `asked` text and action payload of a rejected action (:62-68). | **merely similar**. Needs an explicit exclusion before an estimate action ships. |

## 11. Scraping and parsing dependencies

- **Python pin.** `.python-version:1` pins 3.10.20. `.github/setup.sh:49-51` enforces that pin as "what CI and Render run".
  - `pyproject.toml:14` declares `python = "^3.10"`.
  - CI workflows install `"3.10"` (`.github/workflows/ci.yml:51`).
  - `poetry.lock` was generated by Poetry 2.4.1 (`poetry.lock:1`), lock-version 2.1 (`poetry.lock:8424`).
- **Scraping stack.** None of beautifulsoup4, lxml, selectolax, parsel, Python playwright, curl_cffi, scrapling, html5lib, soupsieve or aiolimiter appears in `poetry.lock`.
- **Unused declaration.** `litellm` is declared (`pyproject.toml:42`) but imported nowhere under `src`, `workflows`, `scripts` or `tests`.

| path:line | symbol | what it does | verdict |
|---|---|---|---|
| `poetry.lock:2084` | `httpx` 0.28.1 | Groups main, dev and workflows. Arrives through supabase, openai, postgrest and others, and is declared directly only as a dev dependency (`pyproject.toml:61`). | **direct reuse** as the fetch client. Declare it in main before relying on it. |
| `poetry.lock:2009` | `httpcore` 1.0.9 | httpx's transport. | **direct reuse**, implicitly through httpx. |
| `poetry.lock:1942` | `h2` 4.3.0 | HTTP/2 support, pulled in by the postgrest and storage3 extras. | **merely similar**. Listing pages do not need it. |
| `poetry.lock:6088` | `requests` 2.32.5 | Main group, transitive only (alpaca-py, posthog, langsmith, tiktoken, vectorbt). | **merely similar**. Undeclared, so do not build on it. |
| `poetry.lock:16` | `aiohttp` 3.13.5 | Main and workflows groups, transitive via litellm and render-sdk. | **merely similar**. Undeclared. |
| `poetry.lock:7229` | `tenacity` 9.1.4 | Transitive, never imported. | **merely similar**. |
| `poetry.lock:315` | `backoff` 2.2.1 | Transitive, never imported. | **merely similar**. |
| `poetry.lock:6125` | `respx` 0.23.1 (dev, `pyproject.toml:67`) | httpx request mocking. | **direct reuse** for adapter tests. |
| `web/package.json:34` | `@playwright/test` 1.59.1 | Web end-to-end tests against Argus's own app. | **merely similar**. Not a backend dependency. |

## (a) The five most valuable reuse points

1. **Typed tool cards carry provenance and confirmation.** Together they deliver a cited comparables card, an indicative range card, and a "confirm this revision" step inside the existing chat and card surfaces.
   - `ToolDeclaration` with `ToolPolicy(confirmation="required")` (`src/argus/domain/tool_declaration.py:92`).
   - Per-fact `ToolFactSource` page citations with URL and date (`src/argus/domain/tool_contracts.py:91`).
   - Money facts in the profile currency (`src/argus/domain/calculations/_shared.py:103`), rendered by code on web (`web/lib/tool-result-card.ts:169`).
   - In-place edits guarded by `input_revision` (`src/argus/api/routers/tool_results.py:40`).
2. **Search contracts give the shape for a SuperCarros or SuperCasas adapter, plus hermetic tests.**
   - A closed failure vocabulary, a boundary sanitizer and a packet stamped with `retrieved_at` (`src/argus/domain/research/search/contracts.py`).
   - An injectable `transport` with `RecordingTransport` (`tests/research/conftest.py:155`).
   - The fail-closed live/recorded/synthetic mode switch (`src/argus/domain/market_data/assets.py:96`).
3. **Observation packets.** `ContextPacket` holds provider, `retrieved_at`, coverage window, freshness, limitations and the `not_for` guard (`src/argus/context/packets.py:30`). The `FreshnessPolicy` registry (`src/argus/context/freshness.py:33`), the budgeted collector (`src/argus/api/chat/context_packets.py:208`) and the single-flight tradability probe (`src/argus/domain/market_data/tradability.py:176`) complete it. Together they give dated observations, a stale packet never attached, and an outage never recorded as "listing gone".
4. **The ownership spine.** It covers a private asset table and a public observation table.
   - For the asset table: the `decision_notes` owner and RLS shape, service-role writes with explicit `.eq("user_id")`, the `require_account_capability` gate, and restrictive registered-only policies (`supabase/migrations/20260911120000_add_profile_home_country.sql:35`).
   - For the observation table: the deny-all shape (`supabase/migrations/20260727230000_add_visitor_usage_counters.sql:46-47`) and the append-only grants (`supabase/migrations/20260702000001_add_cost_ledger_entries.sql:97-99`).
5. **Revision semantics.** Together these give "a proposed estimate beside the recorded one, confirm or reject, history kept".
   - Computing beside the stored answer without moving it (`src/argus/api/chat/computed_answers.py:315`).
   - The consent receipt with `recorded_at` and an idempotency key (`src/argus/memory/contracts.py:245`).
   - The kit's content-addressed proposal ids and `{before, after, reason}` revisions (`tests/synthetic_ingestion/harness.py:114,197`).

## (b) The three most dangerous false-reuse traps

1. **Putting user-scoped asset details into the shared research cache, or routing listing lookups through the research rail.**
   - `SearchPacketCache` is cross-user, public-market discovery only, and per worker (`src/argus/domain/research/cache.py:1-6`).
   - A key built from a user's make, model, year, mileage or sector would leak one user's asset to another through a cache hit.
   - The research path also sends the asker's country (`src/argus/domain/research/config.py:287`).
   - Its source selection keeps one page per publisher and at most five (`src/argus/domain/research/source_selection.py:59`), and search packets truncate to five results (`src/argus/domain/research/search/contracts.py:61-65`).
   - `RetrievedRow` is float-valued, provider-facing schema text.

   The fix: key public observations by public listing facts only, and keep the link from a user's asset to those observations in owner-scoped rows.
2. **Trusting RLS or reusing existing tables for asset records.**
   - The backend writes with the service-role key (`src/argus/domain/supabase_gateway.py:165`), so RLS never stops a missing `.eq("user_id")`.
   - A guest-writable table left out of `claim_guest_workspace_handoff` (`supabase/migrations/20260726185021_harden_guest_lifecycle_ownership.sql:18`) is lost at signup. It is deleted when cleanup removes the anonymous user.
   - `backtest_jobs` needs a user and counts against backtest capacity (`supabase/migrations/20260724102309_add_guest_session_allowances.sql:392-399`).
   - `decision_notes` states mean investing ideas.
   - Memory is admin-only, and PRODUCT.md forbids building records on it (`docs/PRODUCT.md:182-186`).
3. **Money display and arithmetic that silently turns pesos into dollars.**
   - `format_result_money` prints `$` (`src/argus/domain/result_money.py:69`).
   - The web's `formatCurrency` uses `narrowSymbol`, which renders DOP as `$` (`web/lib/result-card-display.ts:669`).
   - The calculation currency falls back to USD (`src/argus/agent_runtime/answer_calculation.py:58`).
   - `dollar_rate` has no DOP rate (`src/argus/agent_runtime/calculation_rows.py:168`).
   - `Money` and `money_fact` are floats.

   A range that mixes RD$ and US$ listings breaks wave-1 R2 until a dated DOP rate source exists (`docs/specs/wave-1/00-shared-rules.md:30`).

## (c) What does not exist and would be new

- **Fetching public web pages.** A GET/HTML client and an HTML parser dependency. Robots.txt handling, per-host crawl delay across instances, a redirect policy, response-size caps, conditional GET, and a User-Agent with contact details. A host allowlist, and any SuperCarros or SuperCasas reference. The archived rule also requires written reuse permission for Dominican sources before anything is shown (`docs/archive/2026-09-26-argus-answers-that-stay-true-roadmap.md:80-82`).
- **A durable, shared, non-user public-observation table** and its retention janitor.
- **Listing logic.** Listing identity and repost dedup. Normalization vocabularies: make, model, trim, year and mileage for vehicles; type, sector, area and rooms for property. Matching to a user's asset, comparable selection, and range statistics.
- **Financial records.** Any model for a user's vehicles, property, accounts, debts, balances or valuations, in the backend or in this web tree, and any household model.
- **Money.** A Decimal or minor-unit money type, an `RD$`/`US$` price parser, es-DO formatting, and a dated DOP exchange-rate source.
- **Scheduling.** A clock for product work. The Render cron was removed, the runbook forbids a scheduled service, and no workflow task starts on a timer.
- **Notifications.** A table, preferences, an inbox, push, and an "estimate changed" notice.
- **An estimate-revision record** that stores the proposal, the approver, the decision time, the sources, and the prior values. Production has no revision-history table; the only history table is `memory_prompt_history`.
