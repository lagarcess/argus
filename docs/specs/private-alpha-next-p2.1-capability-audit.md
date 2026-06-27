# P2.1 Capability Audit (Slice D)

Status: Complete — read-only audit; grounds the P2.1 Capability Registry design
Date: 2026-06-27
Branch: `codex/private-alpha-next` (audited against the clean, promoted P0/P1 state)
Owner: P2.1 lane
Source order: `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/specs/private-alpha-next-roadmap.md`
(P2 board), `docs/specs/private-alpha-next-decision-memo.md` (Slice D, credibility ladder)

## Purpose

The P2 board's P2.1 milestone ("Capability truth, done right") needs a ground-truth
inventory of what Argus can *actually* execute today before a Capability Registry is
designed. Both quarantine branches died building capability truth as a deterministic
post-LLM text gate; this audit establishes what already exists so P2.1 consolidates and
extends it rather than rebuilding or regressing it.

This is a read-only audit. No runtime, schema, or behavior was changed.

## Method

Three independent read-only passes over the current branch, each grounded in file/symbol
evidence: (1) strategy capability truth, (2) indicator capability truth, (3) capability
enforcement path and English/Spanish handling.

## Headline findings

1. **A typed capability spine already exists.** `STRATEGY_CAPABILITIES` (a typed
   `dict[str, StrategyCapability]`) and `EXECUTABLE_INDICATORS` are canonical, typed
   sources. Gating is on typed fields the LLM emits, not on prose. P2.1 is consolidation
   and gap-closing, not a from-scratch build.
2. **The current branch is clean of every quarantine anti-pattern.** No post-LLM intent
   override, no per-language capability copy tables (`capability_response_voice.py` does
   not exist), no literal-text threshold grounding, no pre-LLM routing gate. All
   deterministic text helpers run *post-LLM* as typed-fact validation. This is the
   baseline P2.1 must preserve.
3. **Capability copy is LLM-voiced.** Unsupported/clarification answers are composed by
   the LLM from a deterministic `capability_fact_packet()`; per-language `es-419`/`en`
   strings exist only as recovery *fallbacks*, not as routing or primary copy.
4. **Truth is scattered across several modules.** The single highest-leverage P2.1 move is
   to make one canonical Capability Registry the source the interpreter is *given* and the
   post-LLM validators *read*, so the same truth feeds the model and the gate.

## Strategy capability inventory

Canonical source: `src/argus/domain/strategy_capabilities.py` (`STRATEGY_CAPABILITIES`,
typed `StrategyCapability`). Execution-type gate: `execution_strategy_type:
ExecutionStrategyType | None` (None = not executable). Runtime allow-list:
`SUPPORTED_STRATEGY_TYPES` in `src/argus/agent_runtime/strategy_contract.py`. Engine
dispatch boundary: `LaunchStrategyType` in `src/argus/domain/engine_launch/models.py`.

| Template | Execution type | Executable end-to-end? | Required fields | Notes |
|---|---|---|---|---|
| `buy_and_hold` | `buy_and_hold` | Yes | asset_universe, date_range | — |
| `dca_accumulation` | `dca_accumulation` | Yes | + capital_amount, cadence | cadence ∈ {daily, weekly, biweekly, monthly, quarterly} |
| `rsi_mean_reversion` | `indicator_threshold` | Yes | + entry/exit logic + thresholds | RSI only; typed thresholds |
| `moving_average_crossover` | `signal_strategy` | Yes | + rule_spec | SMA fast/slow crossover |
| `buy_the_dip` | `indicator_threshold` | Yes | asset_universe, date_range | threshold hardcoded -3%, not user-parameterized |
| `momentum_breakout` | `None` | **No (draft/blocked)** | undefined | orphaned signal handler exists in `signals.py` |
| `trend_follow` | `None` | **No (draft/blocked)** | undefined | orphaned signal handler exists in `signals.py` |

Four execution types are real: `buy_and_hold`, `dca_accumulation`, `indicator_threshold`,
`signal_strategy`. The execution ground truth is `_build_signals()` in
`src/argus/domain/backtesting/signals.py`; per-strategy required fields live in
`src/argus/agent_runtime/strategy_requirements.py`; the base contract is in
`src/argus/agent_runtime/capabilities/contract.py`.

## Indicator capability inventory

Canonical source: `EXECUTABLE_INDICATORS` in `src/argus/domain/indicators.py`; dispatch in
`src/argus/domain/indicator_execution.py`; rule compilation in
`src/argus/domain/backtesting/rules/`.

| Indicator | Executable? | Params (typed, bounds-validated) |
|---|---|---|
| RSI | Yes | period (2–100, def 14), entry_threshold (def 30), exit_threshold (def 55) |
| SMA | Yes | period (2–300, def 20) |
| EMA | Yes | period (2–300, def 20) |
| MACD | Yes | fast (def 12), slow (def 26), signal (def 9); requires fast < slow |
| Bollinger | Yes | length (def 20), std (def 2.0) |
| ATR, VWAP, OBV, Stochastic, ~100+ `pandas_ta` | **No (discovery/draft only)** | recognized in catalog; `compute_indicator_output()` raises `unsupported_indicator` |

Threshold handling is **typed**: the LLM emits `indicator_period`/`entry_threshold`/
`exit_threshold` (see `llm_interpreter_types.py`), which `normalize_indicator_parameters()`
validates against spec bounds. There is **no** literal-text grounding of numbers against
the raw message on this branch (the quarantine anti-pattern is absent).

Capability-truth nuance to make crisp in the registry: the five indicators *compute*, but
only two strategy templates *consume* indicators end-to-end (`rsi_mean_reversion` →
`indicator_threshold`, `moving_average_crossover` → `signal_strategy`). MACD/Bollinger are
executable as rule-spec series but have no dedicated user-facing template. "Indicator
computes" and "indicator is reachable via a supported strategy" are different truths and
the registry should express both.

## Current enforcement path (the spine-clean baseline to preserve)

```text
user turn
  -> [interpret] LLM emits typed intent + semantic_turn_act + strategy fields
       intent "unsupported_or_out_of_scope" / semantic_turn_act "unsupported_request"
       are LLM-owned (llm_interpreter.py)
  -> post-LLM audits validate TYPED facts only (asset resolution, contract limits,
       answer-vs-contract consistency) — never re-scan prose to flip intent
  -> [confirm] strategy_can_be_approved() gates on SUPPORTED_STRATEGY_TYPES (typed)
  -> [execute] LaunchBacktestRequest validates strategy_type against LaunchStrategyType
  -> _build_signals() executes; unknown template raises unsupported_template
```

Capability copy: `_compose_natural_capability_answer()` (interpret stage) builds a system
prompt from `capability_fact_packet()` (`capabilities/answers.py`) and the LLM composes the
answer in the user's language. `recovery_messages.py` holds `en`/`es-419` fallback strings
used only when LLM composition fails.

## English/Spanish (i18n) inventory

All runtime locale handling is presentation-layer and legitimate. No risky per-language
branching exists in the interpretation/capability path.

| Location | Type | Verdict |
|---|---|---|
| `presentation_i18n.py` | RuntimeLocale type, rule/clarification display formatting | Legit (display) |
| `recovery_messages.py` | `en`/`es-419` fallback templates | Legit (fallback only) |
| `artifact_action_recovery.py` | per-language artifact recovery strings | Legit (fallback) |
| `response_language.py` | LLM system instruction to answer in user's language | Legit (delegates to LLM) |

Confirmed absent (present on quarantine branches): `capability_response_voice.py` with
`if locale == "es-419": <es> else: <en>` capability copy tables.

## Gaps and overpromise risks

1. **Orphaned draft templates.** `momentum_breakout` and `trend_follow` appear in the
   `StrategyTemplate` enum (`api/schemas.py`) and `ALLOWED_TEMPLATES`
   (`backtesting/config.py`) and have signal handlers in `signals.py`, but have no
   `execution_strategy_type` and are blocked at confirm. Agent path is safe; a direct API
   call is the only theoretical reach. The registry should mark these `future`/`draft`
   explicitly and the API allow-list should derive from the registry, not a parallel set.
2. **Silent normalization fallback.** `normalize_template_name()`
   (`engine_launch/strategies.py`) maps unknown templates to `rsi_mean_reversion`. A silent
   default that changes user intent; should fail explicit or route to clarify, never
   silently rewrite.
3. **`buy_the_dip` is unparameterized.** Hardcoded -3% with empty `parameters`. Honest
   today, but the registry should record it as fixed-parameter so copy does not imply
   tunability.
4. **Indicator-vs-template truth is implicit.** See nuance above; make it explicit so the
   model never implies MACD/Bollinger are runnable as a standalone strategy when no
   template consumes them.

## Recommended first trusted set (executable truth only)

- Strategies: `buy_and_hold`, `dca_accumulation`, `rsi_mean_reversion`,
  `moving_average_crossover` (and `buy_the_dip` as a fixed-parameter variant).
- Indicators reachable via a supported strategy: RSI (via `rsi_mean_reversion`), SMA (via
  `moving_average_crossover`). MACD/Bollinger/EMA compute but are not yet exposed through a
  dedicated template — keep as `draft`/`future` in user-facing capability truth until a
  template consumes them.

## Implications for P2.1 Capability Registry design

1. **Consolidate, do not rebuild.** Make one canonical registry the single source that
   (a) the interpreter is given as context, and (b) post-LLM validators, `confirm`,
   `execute`, and the API allow-list all read. Today truth is split across
   `strategy_capabilities.py`, `indicators.py`, `strategy_contract.py`,
   `engine_launch/models.py`, `capabilities/contract.py`, and `backtesting/config.py`.
2. **Status as typed data.** Each strategy/indicator carries a typed status
   (`executable` / `draft` / `future`) and, for indicators, a separate
   "reachable-via-template" flag. Derive `SUPPORTED_STRATEGY_TYPES`, `ALLOWED_TEMPLATES`,
   and discovery `support_status` from this one source.
3. **Feed truth to the model.** Extend `capability_fact_packet()` from the registry so the
   LLM voices honest capability answers in-language. Do not add post-LLM intent overrides.
4. **Close the gaps above** (orphaned drafts, silent normalize fallback, fixed-parameter
   labeling, indicator-vs-template clarity).
5. **Blast radius (~10 files):** `capabilities/contract.py`, `capabilities/answers.py`,
   `llm_interpreter_types.py`, `extraction/structured.py`, `strategy_contract.py`,
   `strategy_capabilities.py`, `indicators.py`, plus derived consumers. Avoid touching
   `presentation_i18n.py`/`recovery_messages.py` logic unless capability messaging changes.

## What P2.1 must not do (inherits the P2.0 guardrail gate)

- No deterministic re-scan of `current_user_message` to drive routing or grounding.
- No post-LLM override of `intent`/`semantic_turn_act` (no `*_text_guardrail_response`).
- No substring/keyword/alias matching over prose or LLM free-text for capability.
- No grounding by literal text presence.
- No per-language capability/clarification copy tables.

See `docs/specs/private-alpha-next-roadmap.md` (P2 board, P2.0) for the full guardrail
contract and the quarantine root-cause lesson.
