# Jev integration assessment

Status: investigation only. Published information observed **2026-09-21**.
No live Jev calls were made. No Argus latency improvement has been verified.

## Decision

Keep Jev outside the application until a bounded comparison demonstrates useful
work saved without losing interpretation quality. Jev answers multiple-choice
questions quickly; the finance planner must also extract previously unknown
values and preserve artifact context. Those are different jobs.

The current local design uses one LangGraph interpretation node and one
structured planner read, with typed actions avoiding unnecessary interpretation
and existing data/query cache owners reused. It adds no second intent owner.
The planner explicitly disables model-response caching and automatic retries.
These are implementation choices, not measured speed claims. See
[architecture](ARCHITECTURE.md), [graph](../../server/platform/chat_graph.py),
and [planner](../../server/platform/chat_model.py).

An always-on classifier followed by the same required planner adds a network
hop. A useful Jev path must eliminate an existing model call or enough downstream
work to exceed its own latency and fallback cost. It must not recreate keyword,
regex, or language-table routing.

## Published integration contract

| Access | Contract |
| --- | --- |
| TypeSafe native | `POST https://api.typesafe.ai/v1/systemone`, Bearer authentication, JSON `{model, state, questions}`. Current documented version: `jev-1.13.0`. |
| OpenRouter | `POST https://openrouter.ai/api/alpha/decisions`, Bearer authentication, JSON `{model, state, questions}`. Documented request model: `typesafe/jev-1.13`. This is separate from chat completions. |
| LangChain | `langchain-typesafe` provides the `TypeSafeClassifier` Runnable accepting `state` and `questions`; it is not a chat-model substitution. |

Sources: [TypeSafe API](https://docs.typesafe.ai/api),
[OpenRouter Decisions reference](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-questions-and-answers-request),
[LangChain integration](https://docs.langchain.com/oss/python/integrations/providers/typesafe).

Questions produce a `Choice` distribution, a `Noul` yes-probability, or a `Score`
over ordered criteria. Choice supports up to 255 candidates. Question identifiers
do not communicate semantics to the underlying model: instructions must state
the decision. Native responses include answers, resolved model and token usage.
[TypeSafe API](https://docs.typesafe.ai/api)

The [linked latest alias](https://openrouter.ai/~typesafe/jev-latest) redirects.
Pin the requested version and record the resolved response version separately.
OpenRouter's documented response example reports
`typesafe/jev-1.13-20260917`, plus request ID, provider and usage cost. A versioned
request alone does not establish immutable weights. OpenRouter labels the
Decisions API alpha; its shapes may change.
[Response contract](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-questions-and-answers-request),
[OpenRouter SDK status](https://github.com/OpenRouterTeam/ai-sdk-provider#evaluation-jev-with-ai-sdk-through-openrouter)

## Fit and limits

Jev can select among canonical actions or existing record candidates. It cannot
generate arbitrary text or reliably recover arbitrary numeric magnitudes through
scores. Bounded date-component choices are possible; exact date comparison and
arithmetic belong in code. Unknown asset names, amounts, compound edits and
unbounded strategy arguments still require extraction or an existing candidate
set. Its vendor documents weak counting, distracting context, indirection and
susceptibility to adversarial state. Schema conformity does not establish
semantic correctness.
[Documented failure modes](https://docs.typesafe.ai/model-jaggedness/jev-1.13)

English is its strongest documented language; other-language performance is
uneven. Argus needs comparable English and `es-419` evidence, including follow-ups
whose meaning depends on the current artifact. Send only relevant canonical
state. Native limits distinguish 64k aggregate request tokens from 32k for state
plus the longest question; OpenRouter lists 32k context. Do not transfer limits
between transports without checking their contract.
[TypeSafe models](https://docs.typesafe.ai/models),
[OpenRouter model](https://openrouter.ai/typesafe/jev-1.13)

The experimental LangChain model-router middleware selects from the latest
human message and applies that selection across a run. It should not replace
Argus's artifact-aware planner ownership.
[LangChain integration](https://docs.langchain.com/oss/python/integrations/providers/typesafe)

## Price and latency evidence

On the observation date, OpenRouter lists **$0.042 per million input tokens**,
**$0 output**, and approximately **0.24 seconds median latency**. At that rate,
100,000 classifications with 1,000 input tokens each cost about $4.20 before
remaining model work or fallbacks. The median is platform telemetry, not an
Argus measurement or a tail-latency guarantee.
[OpenRouter model](https://openrouter.ai/typesafe/jev-1.13)

The [LangChain article](https://www.langchain.com/blog/building-a-harness-with-jev)
repeats vendor speed and cost claims. Vendor benchmarks use vendor-built tasks,
model-ensemble reference judgments and generative comparisons producing
probabilities. Their advertised multipliers do not establish improvement over
Argus's current path.
[Vendor methodology](https://typesafe.ai/blog/introducing-system-one-models-and-jev)

## Bounded future measurement

1. Select one existing semantic decision within the current interpreter owner.
   Derive options from its canonical catalog and supply relevant artifact
   context. Add explicit uncertainty handling without duplicating intent rules.
2. Build local mocked transport/contract tests first. Freeze the questions,
   requested model, dataset and expected complete-turn outcomes. Split calibration
   and held-out cases; pair English/Spanish examples, ambiguous references,
   compound edits, numeric/date inputs, missing information and adversarial text.
3. Run paid comparisons only after explicit authorization, with a fixed call
   and spend cap, no automatic retries, bounded concurrency and a total deadline.
   Permit one fallback to the current planner; include both calls in accounting.
4. Compare correct full-turn outcomes, preserved fields, fallback coverage,
   end-to-end p50/p95/p99 latency and cost per correct full turn. Calibrate
   thresholds on held-out behavior; never treat an arbitrary confidence number
   as an accuracy grade. [Confidence semantics](https://docs.typesafe.ai/confidence)
5. Keep any later adapter default-off, inside the existing planner boundary.
   Record requested/resolved versions, correlation IDs, usage, latency and
   fallback reason without raw private text. Authorization and financial writes
   remain with existing deterministic owners.

Actual bilingual accuracy, Argus speed, account access, provider retention terms
and latency under application load remain unverified.
