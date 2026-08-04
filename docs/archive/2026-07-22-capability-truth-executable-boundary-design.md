# Capability Truth And Executable-Boundary Design

> [!NOTE]
> Archived 2026-07-23 after issue #241 / PR #266 completed and landed on
> `codex/private-alpha-next` as `bbd1d2b`. Retained as the locked design and
> acceptance record. Current execution source:
> `docs/specs/private-alpha-interim-roadmap.md`.

Status: **COMPLETE — merged through PR #266; historical design record**

Date: 2026-07-22

Authoritative roadmap outcome: **Argus knows what it can and cannot do**

Tracking issue: [#241](https://github.com/lagarcess/argus/issues/241)

Verified integration baseline: `codex/private-alpha-next` at
`854e441155b530730515317e7db4396310f454fc`

Final implementation candidate:
`e10bdd2fc51dd744fb4186edc21f04ef74558b83`

Integration merge:
`bbd1d2bb44a298de2f048e361c92d5851e4c38d1`

## Outcome

Argus gives an honest and useful response when a user asks for something it can
run, something it recognizes but cannot run, or something outside historical
backtesting. A non-executable idea never becomes a runnable-looking draft,
confirmation card, saved strategy, or Run action.

When the user explicitly chooses a supported historical test, Argus creates a
new executable draft and carries forward only facts that remain compatible with
that test. It never silently substitutes a strategy, converts a future horizon
into a historical period, or makes the user repeat compatible asset and capital
facts.

This is a thin trust-boundary slice. It does not add strategies, forecasting,
news Search, asset discovery, or a second capability system.

## Founder-Approved Product Decisions

1. Future-performance requests are a general capability class. The contract
   applies to any asset or basket the user names, any strategy, amount,
   language, or future horizon; it is not specific to Bitcoin or buy and hold.
   Provider resolution affects whether Argus can offer a historical test, not
   whether the no-prediction boundary applies.
2. Argus must clearly say that it cannot predict future performance.
3. Argus may separately offer a supported historical backtest, but it must not
   present that test as a forecast or choose it for the user.
4. The historical test begins only after an explicit typed user selection.
5. Compatible asset and capital facts carry forward into the selected test.
6. A future horizon is not a compatible historical date range. It remains
   original-intent context, while Argus asks for a historical period.
7. Supported requests should remain direct. A fully specified golden-cross
   request must not incur an unnecessary capability clarification.
8. Recognized non-executable strategies and external-data rules remain honest
   recoveries with no runnable artifact.

## Current Product Truth

The baseline already contains the structural foundation:

- `src/argus/domain/capability_registry.py` derives executable strategy and
  indicator truth.
- `src/argus/domain/strategy_capabilities.py` records whether a recognized
  strategy has an execution type.
- API, save, and engine execution paths structurally exclude
  `momentum_breakout` and `trend_follow` after PR #129.
- `src/argus/agent_runtime/interpreter/unsupported_admission.py` fails closed
  when unsupported typed intent conflicts with an executable-looking draft.
- #159/PR #263 closed the options-specific contradiction in which a model could
  pair an unsupported verdict with a supported substitute draft.
- Golden-cross shorthand is a supported moving-average crossover and resolves
  to a bullish fast-SMA-above-slow-SMA entry with the opposite crossover as the
  default exit.

The remaining issue is not proven current at this baseline. Internal
`draft_only` recovery concepts still exist, and a historical production journey
showed an allowlisted user asking about future performance being pushed through
strategy recovery. The journey later lost already supplied asset and capital
facts before reaching a supported card. That evidence justifies exact-head
reproduction; it does not authorize assuming the old defect still exists.

If the current exact head already satisfies this design, implementation is
test-and-evidence alignment only. Do not manufacture a runtime diff.

## Definitions

- **Executable capability**: a typed strategy and rule combination that the
  current canonical registry, confirmation boundary, launch contract, and
  engine can run end to end.
- **Recognized non-executable capability**: a named idea Argus understands but
  cannot currently launch, such as momentum breakout or trend follow.
- **Unsupported external rule**: a rule requiring an unimplemented fact or
  trigger source, such as entering when news sentiment turns positive.
- **Future-performance request**: a request asking what an asset, basket,
  strategy, or amount will return, become worth, or do in a future period.
- **Original intent**: the user's request and typed semantic meaning, retained
  for conversational continuity but never treated as execution authority.
- **Compatible reusable facts**: canonical facts whose meaning is unchanged in
  the explicitly selected supported alternative, such as asset identity and
  starting capital.
- **Incompatible facts**: facts whose meaning would change under the
  alternative, such as converting “the next ten years” into “the last ten
  years.” These remain provenance and must be re-requested or explicitly
  replaced.
- **Runnable artifact**: any pending strategy represented as executable, a
  confirmation card, Run action, saved strategy, or launchable request.

## End-To-End Product Contract

```text
user request
  -> LLM emits typed interpretation and extracted facts
  -> deterministic validation reads typed fields and canonical capability truth
       -> executable
            -> ordinary missing-field or confirmation path
       -> non-executable or outside historical backtesting
            -> honest model-voiced recovery
            -> preserve original intent and compatible facts
            -> emit no runnable artifact
            -> wait for explicit typed supported-alternative selection
                 -> construct a new executable draft
                 -> reuse only compatible facts
                 -> ask for any missing or incompatible required fields
                 -> confirmation only when the new draft is complete
```

The LLM owns semantic interpretation. Deterministic code owns facts the model
cannot declare true: registry status, asset resolution, engine reachability,
field validity, provider availability, and confirmation admission.

Deterministic validation may reject a typed non-executable shape. It may not
rescan user prose, infer a different intent from keywords, or promote an
unsupported request into an executable alternative.

## Required Journey Matrix

### 1. Supported control: golden cross

Input characteristics:

- any provider-resolvable supported asset;
- explicit starting capital;
- valid historical dates;
- golden-cross or equivalent typed moving-average-crossover meaning.

Required behavior:

- resolves to the supported moving-average-crossover contract;
- preserves the supplied asset, capital, and dates;
- proceeds through the ordinary confirmation path without an unsupported or
  capability clarification;
- displays no raw registry enum or internal capability label;
- remains identical after persistence and reload.

### 2. Recognized non-executable strategy: momentum breakout

Input characteristics:

- a fully specified momentum-breakout idea with asset, capital, and valid
  historical dates.

Required behavior:

- says that Argus cannot currently run that strategy;
- may offer typed supported alternatives;
- emits no runnable momentum-breakout draft, confirmation, Run action, or saved
  strategy;
- preserves the supplied run facts as non-executable context;
- creates a new executable draft only after an explicit alternative selection.

`trend_follow` must retain the same structural rejection as regression
coverage. The browser journey need not duplicate it.

### 3. Unsupported external rule: news sentiment

Input characteristics:

- a fully specified historical strategy whose entry or exit depends on news
  sentiment or another unavailable external event signal.

Required behavior:

- says that Argus cannot currently execute that trigger;
- does not pretend Search, sentiment data, or an event engine ran;
- does not route into grounded discovery; #244 owns that later capability;
- may offer supported price/indicator-based alternatives without selecting one;
- emits no runnable artifact until the user explicitly chooses an alternative.

### 4. General future-performance request

Input characteristics:

- any asset or basket the user names, whether or not the current providers can
  resolve it;
- any strategy description or capital amount;
- any explicit or implicit future horizon;
- wording in English, Spanish, or ordinary paraphrase.

Required behavior:

- clearly states that Argus cannot predict future performance;
- does not frame a historical result as a forecast, expected return, target, or
  likely outcome;
- separately offers a supported historical test when one is available;
- preserves compatible canonical asset and capital facts and retains an
  unresolved asset reference only as original intent, never as executable
  identity;
- preserves the future request as original-intent context;
- does not convert the future horizon into a historical date range;
- emits no confirmation card before explicit selection of the historical path;
- after selection, asks only for missing or incompatible required facts, such
  as the historical period;
- remains truthful when the original request includes an otherwise supported
  strategy. A supported strategy does not make its requested future result
  executable.

The BTC/$10,000 production journey is one regression fixture for this macro
contract, not the definition of the contract.

## Capability And Admission Invariants

1. Positive capability claims derive from the canonical executable registry.
2. A typed unsupported verdict cannot coexist at final admission with a
   runnable artifact.
3. A recognized strategy with no execution type cannot reach confirmation,
   save, or launch through chat or direct API paths.
4. A supported substitute draft is not evidence that the user chose it.
5. An alternative-selection transition requires typed action identity or a
   newly interpreted explicit user choice. Display-label or phrase matching is
   not authority.
6. Original unsupported intent remains distinguishable from the newly selected
   executable draft.
7. Defaults fill genuinely absent executable fields only. They never overwrite
   or reinterpret explicit incompatible intent.
8. No frontend component infers capability status or repairs semantic state.

## State, Persistence, And Reload

Unsupported recovery must preserve enough typed state to continue without
pretending it is executable:

- original typed intent and unsupported constraint;
- compatible canonical asset identity, asset class, and capital role/value;
- supplied historical dates when they remain semantically compatible;
- future horizon as original-intent evidence only;
- typed supported alternatives, when offered;
- exact model-authored recovery prose when the normal LLM path succeeds.

The existing message and pending-strategy contracts should be reused. No new
public API or database shape is expected. A pending recovery may carry strategy
facts, but it must not claim executable approval or expose a Run action.

Reload must reproduce the same visible recovery, compatible facts, and typed
options. Selecting an alternative before or after reload must create the same
new executable draft. If this cannot be expressed by the existing internal
state, stop for a separate contract decision instead of adding an ad hoc public
field.

## Response Voice And Localization

Normal capability responses are LLM-authored from canonical typed facts. The
contract is semantic, not byte-exact prose.

A future-performance response should communicate two separate facts:

1. Argus cannot predict future performance.
2. Argus can help test a supported historical alternative, if the user wants.

For example only:

> I cannot predict how that investment will perform in the future. I can test
> how the same asset and amount performed historically. What historical period
> would you like to examine?

English and Spanish must preserve the same meaning without raw enums,
provider names, blame, or language-specific routing logic. Existing localized
deterministic copy remains degraded fallback only when model-authored recovery
is unavailable.

## Error And Recovery Behavior

- Ambiguous requests follow ordinary typed clarification; ambiguity alone is
  not an unsupported verdict.
- Missing run fields are requested only after a supported historical path is
  selected.
- A failed capability arbiter or invalid audit payload fails closed: no
  runnable artifact escapes.
- A model that pairs unsupported intent with an executable-looking draft is
  arbitrated through the existing typed audit and admission invariant.
- If no supported alternative is appropriate, Argus gives a clear stopping
  point rather than manufacturing one.
- Infrastructure failure follows existing durable lifecycle recovery and is not
  reclassified as capability truth.

## Ownership Boundaries

Issue #241 owns:

- supported-versus-non-executable capability truth;
- future-performance versus historical-backtest truth;
- the explicit-selection boundary;
- conservation of compatible facts through unsupported recovery;
- prevention of runnable artifacts before explicit selection.

Existing issue #238 owns a generic fact-continuity defect if exact-head testing
shows the same asset/capital loss outside unsupported recovery.

Issue #244 owns asset discovery, peer/category lookup, Search, citations,
Perplexity, news retrieval, and grounded suggestions.

Progress/reconciliation issues own post-admission execution, retry, and terminal
lifecycle behavior. They are not reopened by this design unless a distinct
current regression is reproduced.

## Allowed Implementation Surfaces

- canonical capability registry and its existing typed consumers;
- LLM interpreter schema/context for typed capability meaning;
- typed capability audits and unsupported admission;
- unsupported recovery and explicit alternative-selection continuation;
- focused persistence/reload plumbing only where existing internal state is
  insufficient;
- mocked and sanctioned live eval fixtures;
- English/Spanish browser and trajectory tests;
- documentation directly describing the proven contract.

## Forbidden Scope

- a forecasting, projection, valuation, expected-return, or scenario engine;
- new strategies, indicators, market-data providers, or model tiers;
- news sentiment, Search, citations, Perplexity, or discovery routing;
- regex, keyword, alias, localized phrase, or raw-text rescanning gates;
- post-LLM intent rewriting from deterministic prose analysis;
- frontend semantic inference;
- a second capability registry, chat brain, or intent taxonomy;
- broad continuity, runtime, persistence, or confirmation refactors;
- options-specific reimplementation already closed by #159/PR #263;
- public API or database changes without a separate founder-approved contract
  gate.

## Implementation Sequence

1. Reproduce all four journeys at the exact integration baseline before editing.
2. Inspect visible response, typed interpretation, audits, pending state,
   confirmation/action output, persisted message metadata, and reload.
3. Classify each observed gap against #241, #238, #244, or an existing lifecycle
   owner before changing code.
4. Write the smallest red tests for confirmed #241 gaps.
5. Correct the narrowest typed boundary. Reuse existing registry, audits,
   recovery state, and alternative-selection machinery.
6. Reassess the diff against finding severity and remove speculative machinery.
7. Run deterministic gates, then founder-guided production-parity browser QA.
8. Run one sanctioned exact-head live eval only after deterministic and browser
   gates pass.
9. Request independent review and merge only when the complete acceptance
   matrix is evidenced at the candidate SHA.

## Verification Matrix

### Deterministic

- registry tests prove executable and non-executable status is canonical;
- interpreter semantic-contract tests cover the four journeys without raw-text
  matching;
- admission matrix proves unsupported intent/turn-act combinations fail closed;
- supported golden cross reaches confirmation directly;
- momentum breakout and trend follow cannot confirm, save, or launch;
- news-sentiment rules cannot produce runnable artifacts;
- future-performance variants across assets, strategies, and amounts remain
  non-executable until explicit historical selection;
- compatible facts survive selection; incompatible future horizons do not
  become historical dates;
- persistence and reload preserve exact typed recovery and normal LLM prose;
- English and Spanish tests assert semantic parity, not phrase routing;
- existing options-substitution and unsupported-admission regressions remain
  green;
- mocked eval harness and spine/modularity guardrails pass.

### Founder-guided production-parity browser QA

Run on the exact candidate with real auth, durable persistence, and the ordinary
chat surface:

1. fully specified golden cross reaches confirmation without extra capability
   recovery;
2. momentum breakout produces honest recovery, no runnable artifact, survives
   reload, and creates a supported draft only after explicit selection;
3. news-sentiment trigger produces honest recovery without claiming Search or
   sentiment execution;
4. a future-performance request for an asset other than the regression BTC
   example states the prediction boundary, preserves asset/capital, and asks for
   a historical period only after explicit selection;
5. repeat representative unsupported and future-performance journeys in
   Spanish;
6. inspect persisted metadata and reload after each unsupported turn and after
   alternative selection;
7. confirm no hidden saved strategy, confirmation, Run action, provider call,
   or backtest is created before explicit selection.

### Sanctioned exact-head live eval

Because this slice changes or validates interpreter-facing behavior, run one
sanctioned live scorecard at the exact candidate SHA after the deterministic and
browser gates pass. It must include the four acceptance classes and record:

- visible response quality;
- typed intent and semantic turn act;
- capability/audit receipts;
- preserved facts and pending state;
- runnable-artifact absence or presence;
- model/provider provenance, cost, and latency through the existing eval
  envelope.

Do not loop paid review. One exact-head run is the release gate; a failed case
gets one bounded diagnosis before any implementation decision.

## Acceptance Criteria

- [ ] The fully specified golden-cross request reaches ordinary confirmation
      without unnecessary capability clarification.
- [ ] Momentum breakout and trend follow remain structurally non-executable.
- [ ] A news-sentiment rule receives honest unsupported recovery and no runnable
      artifact.
- [ ] Any future-performance request clearly receives the no-prediction boundary
      regardless of asset, strategy, capital, wording, or language.
- [ ] Historical backtesting is offered separately and never represented as a
      forecast.
- [ ] No supported alternative is silently selected.
- [ ] Compatible asset and capital facts survive explicit alternative selection.
- [ ] A future horizon never silently becomes a historical date range.
- [ ] Unsupported recovery persists and reloads without confirmation, Run,
      save, or executable-draft leakage.
- [ ] English and Spanish behavior is semantically equivalent and model-voiced
      on the normal path.
- [ ] Founder-guided exact-head browser QA passes all four journeys.
- [ ] The single sanctioned exact-head live eval passes after deterministic and
      browser gates.
- [ ] Independent review finds no release-blocking contradiction or regression.

## Stop Conditions

Stop and return to the founder before implementation expands into:

- a new public request, response, action, or persistence contract;
- a forecasting or scenario-analysis product decision;
- Search, discovery, citation, or external-event retrieval;
- a new strategy or indicator;
- generic continuity repair outside unsupported recovery;
- raw-text or language-specific semantic routing;
- a second capability authority;
- a protected-spine refactor larger than the reproduced defect justifies.

## Rollback And Completion

The implementation must remain one independently revertible capability-boundary
slice. Rollback restores the pre-slice runtime and removes only its focused tests
and evidence; it must not require schema rollback or discard durable user data.

Issue #241 closes only after the exact candidate passes deterministic checks,
founder-guided browser QA, persistence/reload verification, the one sanctioned
live eval, independent review, and clean integration landing. Tests alone do not
close the outcome. The interim-roadmap outcome becomes complete only after the
founder accepts the user-visible behavior on the integration checkpoint.
