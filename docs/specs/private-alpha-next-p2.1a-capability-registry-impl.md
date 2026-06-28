# P2.1.a — Capability Registry Consolidation (Implementation Spec)

Status: Spec → implementation on slice branch `codex/p2.1a-capability-registry`
Date: 2026-06-27
Parent: `codex/private-alpha-next` (integration trunk — do not merge/promote here)
Grounding: `docs/specs/private-alpha-next-p2.1-capability-audit.md` (inventory + design
direction), `docs/specs/private-alpha-next-roadmap.md` (P2.1 milestone, P2.0 guardrails),
`tests/test_spine_guardrails.py` (tripwires that must stay green), `AGENTS.md` runtime
principles.

## 1. Goal and non-goals

Consolidate Argus's scattered capability truth into **one canonical, typed source** that
every other allow-list derives from, add **typed status** per entry, and make draft
strategies / draft-or-discovery indicators **structurally unreachable** (containment by
construction, not convention). Close four known gaps. Stay narrow.

Non-goals (explicitly deferred to P2.1.b/c/d):

- No interpreter context/tools wiring (feeding the registry to the LLM). Only the
  `capability_fact_packet` *inputs* are re-pointed at the registry; the answer stays
  LLM-voiced.
- No post-LLM capability validation rework, no new typed-field extraction.
- No model-voiced-copy / per-language work.
- No widening of the supported set. (Narrowing for honesty/containment is allowed.)

## 2. Inherited guardrails (P2.0 — non-negotiable)

Typed-in, typed-out. Post-LLM reads only typed enums the LLM emits (`strategy_type`,
`indicator.key`). No re-scan of `current_user_message`, no `*_text_guardrail_response`,
no substring/alias matching over prose for capability, no literal-text grounding, no
per-language copy tables. `tests/test_spine_guardrails.py` must stay green. This slice
adds **only data + derivations + containment**, no new post-LLM text analysis.

## 3. Canonical home

New module **`src/argus/domain/capability_registry.py`** is the single consumption
surface for derived capability truth. The typed *data* continues to live in its existing
homes (so this is consolidation, not a rebuild):

- Strategy data: `src/argus/domain/strategy_capabilities.py` (`STRATEGY_CAPABILITIES`,
  enriched with `status` + `fixed_parameters`).
- Indicator data: `src/argus/domain/indicators.py` (`EXECUTABLE_INDICATORS` execution
  specs + the catalog `IndicatorInfo`s, with `support_status` now *derived* from
  execution-spec membership instead of hand-maintained).

Shared status type lives in **`src/argus/domain/capability_status.py`**
(`CapabilityStatus = Literal["executable", "draft", "future"]`) to keep imports acyclic
(`strategy_capabilities`, `indicators`, and `capability_registry` all import it; none
import each other in a cycle).

Import direction (acyclic): `capability_status` → (used by) `strategy_capabilities`,
`indicators`, `capability_registry`; `capability_registry` → imports
`strategy_capabilities` + `indicators`; agent_runtime/api/backtesting consumers →
import `capability_registry`.

## 4. Registry data shape

### 4.1 Strategy (`StrategyCapability`, extended)

Add two typed fields:

- `status: CapabilityStatus` — `executable` for the five real templates; `draft` for
  `momentum_breakout` and `trend_follow`.
- `fixed_parameters: bool = False` — `True` for `buy_the_dip` (hardcoded −3%, empty
  `parameters`) so copy never implies tunability.

| Template | execution_strategy_type | status | fixed_parameters |
|---|---|---|---|
| `buy_and_hold` | `buy_and_hold` | executable | false |
| `dca_accumulation` | `dca_accumulation` | executable | false |
| `rsi_mean_reversion` | `indicator_threshold` | executable | false |
| `moving_average_crossover` | `signal_strategy` | executable | false |
| `buy_the_dip` | `indicator_threshold` | executable | **true** |
| `momentum_breakout` | `None` | **draft** | false |
| `trend_follow` | `None` | **draft** | false |

### 4.2 Indicator — two explicit axes

The registry must distinguish **"computes"** from **"reachable via a template"** (audit
gap #4). These are different truths and drive different surfaces:

- **computes** = has an `IndicatorExecutionSpec` in `EXECUTABLE_INDICATORS` (the engine
  can produce the series). Drives the `@` discovery picker and the `support_status`
  field. Today: RSI, SMA, EMA, MACD, Bollinger.
- **reachable_via_template** = a *named supported template* consumes the indicator
  end-to-end. Today: RSI → `rsi_mean_reversion`, SMA → `moving_average_crossover`.
  EMA/MACD/Bollinger compute but no named template consumes them (they remain usable
  inside a generic `signal_strategy` rule, which is why they stay pickable/answerable).

Derived 3-state indicator `status`:

- `executable` ⟺ reachable_via_template is set (RSI, SMA)
- `draft` ⟺ computes but not reachable (EMA, MACD, Bollinger)
- `future` ⟺ does not compute (ATR, VWAP, OBV, Stochastic, ~100 `pandas_ta` catalog)

`INDICATOR_TEMPLATE_REACHABILITY = {"rsi": "rsi_mean_reversion", "sma": "moving_average_crossover"}`
is declared explicitly in the registry with a comment on its derivation source.

> Design note (judgment call): the picker keeps offering all *computing* indicators
> (no regression — VERIFY says it "still offers only executable indicators", and the
> Bollinger capability test pins them as executable). Reachability is recorded as
> registry truth and is available to honest capability answers, but EMA/MACD/Bollinger
> are not removed from the picker because they genuinely run inside `signal_strategy`
> rules. Removing them is a user-facing surface change left for a later, founder-gated
> slice.

## 5. Derivations (each reads FROM the registry)

| Consumer (today) | Becomes |
|---|---|
| `strategy_contract.SUPPORTED_STRATEGY_TYPES` (literal set) | re-exported from `capability_registry.SUPPORTED_STRATEGY_TYPES` (derived: execution types of `status==executable` strategies) |
| `backtesting/config.ALLOWED_TEMPLATES` (`keys() \| {signal_strategy}`) | `capability_registry.ALLOWED_TEMPLATES` = `EXECUTABLE_TEMPLATES \| {"signal_strategy"}` (drops the 2 drafts) |
| `api/schemas.StrategyTemplate` (Literal incl. 2 drafts) | Literal of the 5 executable templates only; guardrail test asserts `== EXECUTABLE_TEMPLATES` |
| `api/chat/strategies.supported_templates` (hardcoded set incl. drafts) | uses `capability_registry.EXECUTABLE_TEMPLATES` |
| `engine_launch/models.LaunchStrategyType` (Literal of 4 exec types) | unchanged Literal; guardrail test asserts `== SUPPORTED_STRATEGY_TYPES` |
| `indicators._KNOWN_INDICATORS[*].support_status` (hand-set) | derived: `executable` if key in `EXECUTABLE_INDICATORS` else `draft_only` |
| `discovery.discovery_support_status` | unchanged mapping, but now consumes registry-derived `support_status` |
| `capabilities/answers.capability_fact_packet` inputs | executable strategy/indicator lists sourced from the registry (voice preserved; no per-language tables; no interpreter tooling) |

`Literal`s (`StrategyTemplate`, `LaunchStrategyType`) cannot be built from a runtime set
while preserving static typing + OpenAPI enums, so they stay declared but are pinned to
the registry by **sync guardrail tests** — that is the enforced "derivation".

## 6. Containment map (draft strategies → NO path)

`momentum_breakout` / `trend_follow` today have FOUR latent reaches; close each:

1. **API allow-list (config):** dropped from `ALLOWED_TEMPLATES` → `validate_backtest_config`
   raises `unsupported_template`.
2. **API schema (`StrategyTemplate`):** removed from the Literal → `BacktestConfig`,
   `BacktestRun`, `Strategy`, `StrategyCreate` reject them at the pydantic boundary
   (this also blocks `POST /api/v1/strategies`, which accepts `momentum_breakout` today
   — see `tests/test_alpha_api.py:898`).
3. **Save passthrough:** `strategy_template_from_run` derives from `EXECUTABLE_TEMPLATES`;
   an unknown/draft template falls back to `buy_and_hold` (existing fallback).
4. **Orphaned signal handlers:** remove the `momentum_breakout` / `trend_follow` blocks
   in `backtesting/signals.py::_build_signals`; they then hit the existing
   `raise ValueError("unsupported_template")`.

Draft/discovery indicators: already filtered from the picker by the discovery endpoint
(`support_status != supported`) and by the frontend `isSupportedDiscoveryItem` guard
(kept — it is active, tested containment). The registry now *derives* that status.

Frontend latent `draft_only` token plumbing (nothing emits it; a draft can never become
a token because the picker filters it): remove the token-carried `support_status` so a
draft token cannot be constructed or sent as a mention. Keep the picker-level filter.

- `web/components/chat/types.ts`: drop `support_status` from `ChatMention`.
- `web/components/chat/composer-model.ts`: stop copying `support_status` into the mention.
- `web/components/chat/ChatInput.tsx`: drop the `tokenSupportStatus` dataset write/read
  and the dead `draft`/`unavailable` badge branches (keep the asset/indicator badge and
  the `isSupportedDiscoveryItem` picker filter).
- `web/lib/argus-api.ts`: make `DiscoveryItem.support_status` optional (picker items from
  the API still carry it; DOM-reconstructed tokens no longer need it).
- Backend keeps `support_status` on `DiscoveryItem` / `ChatMentionPayload` (API contract)
  and the defensive `resolution.mention_to_provenance` read; the discovery endpoint still
  emits `supported`. Frontend simply stops echoing it back.

## 7. Gap fixes (audit §"Gaps and overpromise risks")

1. **Orphaned drafts** — closed by the containment map above.
2. **Silent `normalize_template_name` fallback** (`engine_launch/strategies.py`): replace
   the catch-all `return "rsi_mean_reversion"` with an explicit map
   (`indicator_threshold → rsi_mean_reversion`) that raises `unsupported_strategy_type`
   for anything unmapped. No behavior change for the four valid `LaunchStrategyType`
   values; it just stops silently rewriting. (The `slot_normalizer.normalize_template_name`
   already returns `None` for unknown — left as is.)
3. **`buy_the_dip` fixed-parameter** — recorded via `fixed_parameters=True`.
4. **Indicator computes-vs-reachable** — made explicit (§4.2).

## 7a. Typed-validation contract (unchanged mechanism, now registry-sourced)

Validation continues to read typed enums only:

- `confirm`: `strategy_can_be_approved` → `executable_strategy_type` ∈
  `SUPPORTED_STRATEGY_TYPES` (now registry-derived).
- `execute`: `LaunchBacktestRequest.strategy_type` ∈ `LaunchStrategyType`;
  `validate_backtest_config` template ∈ `ALLOWED_TEMPLATES` (now registry-derived).
- indicator params: `normalize_indicator_parameters` keys off `executable_indicator_spec`
  (registry execution specs). No prose scanning is added anywhere.

## 8. Tests

New: `tests/domain/test_capability_registry.py`

- `STRATEGY_CAPABILITIES` status assignments are exactly as §4.1.
- `EXECUTABLE_TEMPLATES` == the 5; drafts excluded.
- `SUPPORTED_STRATEGY_TYPES` == `{buy_and_hold, dca_accumulation, indicator_threshold, signal_strategy}` and equals the executable execution types.
- `ALLOWED_TEMPLATES` == `EXECUTABLE_TEMPLATES | {signal_strategy}` and excludes drafts.
- `set(get_args(StrategyTemplate)) == EXECUTABLE_TEMPLATES` (schema sync).
- `set(get_args(LaunchStrategyType)) == SUPPORTED_STRATEGY_TYPES` (launch sync).
- `api/chat/strategies.supported set == EXECUTABLE_TEMPLATES`.
- indicator: `indicator_status` for RSI/SMA=executable, EMA/MACD/Bollinger=draft,
  ATR=future; `computes` vs `reachable_via_template` correct.
- containment: `validate_backtest_config({template: momentum_breakout...})` raises
  `unsupported_template`; `_build_signals` raises `unsupported_template` for the drafts.
- `normalize_template_name` explicit mapping + raise.

Update: `tests/test_alpha_api.py:898` (use a valid template — draft is now rejected;
assert rejection separately if useful); `tests/test_strategy_capabilities.py` (registry
keys unchanged — all 7 still present, only status added); frontend composer tests as
needed.

Static: `poetry run ruff check src tests workflows scripts`; `tests/test_spine_guardrails.py`
green; focused backend suite; `cd web && bun test` for composer.

## 9. Rollback

Single revertable slice: the registry module, the enrichment of two data modules, the
derivation edits, the containment edits, the frontend token cleanup, the spec, and the
tests. Reverting restores the prior scattered constants with no schema debt.
