# Subtract the guardrails, round one: what each gate tests

Board item: "Subtract the guardrails" in
[argus-grounded-finance-roadmap.md](../specs/argus-grounded-finance-roadmap.md),
ships in The spine. Baseline: PR #563, 68 real turns on the deployed product,
ordinary chat first token 33.14s p50, with 15.60s of 30.13s of provider time
spent outside the interpretation and the composer. This round changed no code.
Line numbers are at integration `aca53c03`.

## The turn, as the receipts show it

Every ordinary-chat turn in the cohort ran the asset-mention preflight and the
primary interpretation. What ran after the interpretation, per turn:

| Call | Fired | p50 | What happened on the turns it fired |
| --- | ---: | ---: | --- |
| `FocusedAssetDiscoveryRead` | 7 of 10 | 4.01s | recovered a payload 0 times |
| `CapabilitySideQuestionAudit` | 4 of 10 | 11.49s | 2 misses; 2 turns exited on the capability-focus return, both concept questions |
| `ContextQuestionAudit` | 7 of 10 | 5.11s | at least 1 hit, and it was wrong (below) |
| `FocusedStrategyExtraction` | 8 of 10, always twice | 2.60s | 16 calls, 0 material fields |

The four calls sum to 14.83s median per turn; with the 0.83s preflight that is
the board's 15.60s. The preflight is not one of the four and is out of scope.

Two turns then lost their composer. `DEFAULT_TURN_CALL_ALLOWANCE` is 7 and its
comment names what it was calibrated for: preflight and interpretation with
their fallbacks, one focused repair, and the clarifier. The audits were never
in that budget. On turn 10 ("¿Qué significa inflación?") the chain consumed all
seven calls, the composer was skipped with `turn_call_allowance_exhausted`,
and the user received a 154-character answer after 39 seconds. That length is
exactly the `macro_context` recovery text the context composer returns when its
chat call is refused, so the reconstruction is: the context audit relabeled a
definition question as macro curiosity, the repair ladder burned the last two
calls, and the canned text, which is English on a Spanish turn, shipped as the
answer. Turn 01 also spent all seven calls; the primary's own prose answered, so
nothing was visibly lost.

Why a conversation turn walks the gauntlet at all: the fast exit in
`_audited_response_ready_for_runtime` is `_optional_runtime_readiness_audit_blocker`,
whose first check returns `unsupported_intent` for anything but
`strategy_drafting` or `backtest_execution`. The exit exists for clean strategy
drafts; a conversation turn runs every audit whose own gate admits it.

The last committed live scorecard
([411/live-measurement.json](evidence/411/live-measurement.json), 61 cases with
receipts) never fired the first three calls and ran the repair 15 times over 12
cases. The measurement suite has no concept-question turn, which matters for
round two and is taken up at the end.

## 1. CapabilitySideQuestionAudit

**What it catches.** `_capability_side_question_audited_response`
(`llm_interpreter.py:1694`) asks a second model whether the message is a
question about what Argus supports. On a yes with a focus and confidence at
least 0.6 it rewrites the turn to `conversation_followup` /
`educational_question`, sets `capability_question_focus`, clears the draft and
the clarification, and adds the reason code. Downstream,
`_capability_answer_if_applicable` (`stages/interpret.py:1797`) answers from
the capability fact packet for `supported_indicators`, `assets` and `limits`,
and for `general` or `supported_strategies` only when the primary wrote no
prose. The pinned catches are "Can I use Bollinger Bands?" typed as an answer
to a pending field with a signal draft, rerouted to capability Q&A
(`test_llm_interpreter_artifact_capability_repairs.py:663`), and the same
question typed as education with the prose "Yes, Bollinger Bands are
supported", given a focus so the registry answers instead of the model
(`test_llm_interpreter_date_window_repairs.py:620`). The job is capability
truth: what Argus can run comes from the registry, not from prose.

**Why the gate admitted a plain turn.**
`_response_needs_capability_side_question_audit` (`llm_interpreter.py:1764`)
has five vetoes (a focus already set, a context focus set, the approval, retry
and result acts, a draft with a concrete execution target, a pending
material-evidence repair) and four admits: asset grounding removed a symbol; a
non-refinement field is pending; `conversation_followup` plus
`educational_question` plus a non-empty `assistant_response`; a vague strategy
start. The third admit is the exact shape of every answered concept question.
The primary is already instructed to set the focus on capability questions and
to leave it unset for concept education (`llm_interpreter.py:1070`), so an
unset focus is either a correct no or a miss, and nothing typed distinguishes
the two. The gate therefore reads every time the primary wrote an answer. The
six turns it skipped had no prose or a different intent, not a tighter gate.

**Observed.** Four fires. Control flow shows two hits: turns 05 and 06 ("What
does diversification mean?", English and Spanish) exited through the
capability-focus return at `llm_interpreter.py:2561` without reaching the
repair, which only happens when the audit set a focus. Both are concept
questions the prompt says are not capability questions. The verdicts
themselves are not persisted anywhere; the audits add a reason code to a
response that no table keeps, so this is inferred from the call chain.

**Smallest change.** Delete the third admit. The other three stay; they are
strategy-flow shapes where a capability question can hide inside a draft. The
turn then trusts the primary's typed focus, which is what the prompt already
asks for, and the deterministic honesty pass on educational prose
(`_supported_strategy_education_repair_if_needed`, which recomposes from the
contract when prose contradicts a supported family) remains as the post-hoc
backstop. One unit test pins the deleted branch
(`test_llm_interpreter_repairs_unfocused_capability_answer`) and moves to a
surviving shape. The edge traded: a capability question the primary answers in
prose without a focus keeps that prose unless the deterministic scan objects.
No cheaper check exists without a model read, and "no change" keeps 11.5
seconds on four turns in ten for a catch that has never been observed.

## 2. ContextQuestionAudit

**What it catches.** `_context_question_audited_response`
(`llm_interpreter.py:1843`) asks whether the message is standalone macro,
corporate-event or movers curiosity. On a yes it sets
`context_question_focus`, wipes `assistant_response`, and adds the reason
code. Downstream `_context_curiosity_answer_if_applicable`
(`stages/interpret.py:1828`) composes a bounded context answer from a fact
packet, with a live movers packet for `market_movers`. The pinned catch is a
standalone movers question relabeled to `market_movers`
(`test_llm_interpreter_repairs_standalone_movers_to_context_focus`). A second
entry, `_unsupported_context_question_audited_response` (`:1909`), forces the
audit on `unsupported_or_out_of_scope` turns after a failed testable-idea
repair, for the "we can't do that" mislabel that is really a market question.

**Why the gate admitted a plain turn.** `_response_needs_context_question_audit`
(`interpreter/capability_context_audits.py:68`) admits two shapes:
`strategy_drafting` plus `unsupported_request` plus a clarification with no
missing fields, and `conversation_followup` plus `educational_question`, with
no prose requirement, which is why it fired on three turns the capability
audit skipped. The primary is instructed to set this focus itself
(`llm_interpreter.py:1080`). More to the point, with the research rail on,
which it is in production and in the release profile, the primary's
`research_query.question_kind` (`market_pulse`, `sector_radar`, `screening`,
`current_external`, and the rest) claims market and macro questions before any
audit runs: `_response_ready_for_runtime` returns at its first statement when
`primary_research_query` is set. The audit therefore only ever sees turns the
primary judged, in one richer read, to be neither research nor context.

**Observed.** Seven fires, at least one hit, and the hit was turn 10, described
above. In the 411 scorecard it never fired.

**Smallest change.** Delete the `conversation_followup` plus
`educational_question` admit. The strategy-drafting admit and the forced
unsupported entry stay. One unit test pins the deleted branch and moves to the
unsupported shape. An alternative is to gate the audit on the rail flag, since
the rail's primary read now owns these questions; rejected because a branch
removal is smaller and does not couple a gate to a flag.

## 3. FocusedAssetDiscoveryRead

**What it catches.** `focused_discovery_payload_response`
(`interpreter/discovery_focused_read.py:86`) asks one narrow question, does
this turn ask Argus to find assets, and on a yes with a coherent target
attaches an `asset_discovery` payload under
`discovery_payload_recovered_by_focused_read`; the caller re-runs the discovery
guard on the result. It was added in `9586a78d` for #344, when the primary
"sometimes" answered a discovery request as plain education with the payload
empty. The same commit rewrote the primary's schema so the payload is an
act-independent question answered on every turn.

**Why the gate admitted a plain turn.** `focused_discovery_read_applicable`
(`:76`): payload is None, act is None or `educational_question`, and
`response_shape_open_to_discovery` (intent `conversation_followup`, no
clarification, no extractable draft field, no other surface claim). That is the
shape of every concept question. A null payload is not an unanswered question;
it is the primary's no to a question it was asked. The read exists to
second-guess that no, and no typed signal makes one no more suspect than
another.

**Observed.** Seven fires, zero recoveries; all seven were concept questions.
In the 411 scorecard the twelve discovery cases, including the five #344
shapes, all passed with the read firing zero times: the primary filled the
payload or the act itself every time. With the rail on, the `find_assets`,
`screening` and `sector_radar` kinds also route discovery phrasing at the
primary read.

**Smallest change.** Stop calling it: the recovery block in
`_response_ready_for_runtime` (`llm_interpreter.py:2288`). The module and its
guidance text stay untouched, because removing fingerprinted text is a
model-facing change this lane does not make; deleting the module is a
follow-up once this lane's live scorecard exists. The regression guard is the
twelve discovery cases, which passed without the read at `9fec4bf7`.

## 4. FocusedStrategyExtraction, trigger required_strategy_shape_missing

**What it catches.** `_repair_incomplete_strategy_extraction`
(`llm_interpreter.py:3253`) is a strategy-only second read of the current
message. When it returns material fields (a strategy family, assets, a window,
capital, cadence, rules), the turn is rebuilt from them. The cohort shows one
real catch: confirmation-08, one of ten confirmation turns, reached its card
only after this repair. It also shows two mis-catches: compute probes 03 and 04
("Calculate the value of 1000 after two years at 5 percent…") became backtest
clarifications. That belongs to the calculations lane and is noted, not
touched.

**Why it fires on plain turns.** Two reasons.

Entry. There are fifteen call sites. Every entry on the strategy path requires
`_request_current_turn_has_material_execution_evidence(request)`, a number or
a provider-resolved asset mention in the current message; the predicate's
docstring is "whether focused strategy repair has current-turn facts to work
with". Two entries on the conversation path do not require it:
`_response_needs_artifact_context_repair`
(`interpreter/strategy_repair_predicates.py:22`, admitting
`conversation_followup` plus `educational_question` plus prose plus
`raw_user_phrasing` or `strategy_thesis`, or `unsupported_or_out_of_scope`
plus prose) at `:2661`, and the `_response_needs_testable_idea_repair`
catch-all (`:3849`), whose last branches admit any `beginner_guidance` or
`conversation_followup` turn with act None, `educational_question` or
`new_idea`, at `:2676`. Behind both, `strategy_extraction_repair_is_allowed`
(`interpreter/focused_extraction.py:646`) returns True unconditionally for
`educational_question` on its last line, while for `unsupported_request` it
requires evidence or a thesis that differs from the message, and the model
writes a paraphrased thesis on most turns. Since the primary fills
`raw_user_phrasing` on most turns, every concept question reaches one of
these.

Ladder. `_unique_repair_models(task="interpretation_repair")` is the
structured tier's primary and fallback, `x-ai/grok-4.3` then
`anthropic/claude-haiku-4.5`. The loop at `:3268` treats `no_material_fields`
exactly like a provider exception and continues to the next model, so a
well-formed "there is no strategy here" from the first model is asked again of
the second. Cohort: 16 fallback calls, none changed an outcome; every chat
ladder and eight of ten compute ladders were two calls for nothing. The
`repair_effect` receipts added in `2bbb8fad` record `no_material_fields` on
both rows.

**Smallest change.** Two edits, one owner each. First, make
`strategy_extraction_repair_is_allowed` require current-turn execution
evidence for `educational_question`, and require evidence or draft execution
evidence for the unsupported thesis clause, so the two conversation entries
inherit the precondition every strategy entry already has, instead of gating
two call sites. The pinned tests use messages with resolvable assets ("Apple",
"Tesla") and keep their repairs. Second, a well-formed empty extraction ends
the ladder; provider failures and malformed results still fall through. The
edges traded: a strategy described with no number and no resolvable asset
("trade on Reddit sentiment") keeps the primary's prose refusal instead of a
typed unsupported recovery, which `test_unsupported_capability_question_without_run_facts_stays_prose`
already names as the intended honest shape; and a first-model under-read is no
longer retried on the second model. Both need live evidence.

## What the receipts project, and what round two must show

Subtracting the four calls' latency from each turn's measured first token:

| Turn type | TTFT p50 before | projected | p95 before | projected |
| --- | ---: | ---: | ---: | ---: |
| Ordinary chat | 33.21s | 17.97s | 48.21s | 27.48s |
| Compute-intent probe | 26.02s | 12.58s | 36.35s | 24.64s |

The ladder stop alone moves ordinary chat only to 31.31s; the entry gates are
where the time is. The projection ignores the allowance effect, so turn 10
would additionally regain its composer. What remains on an ordinary turn is
the preflight, the interpretation and the composer, about 17 to 20 seconds.
Decision 3's one-second target is not reachable by this lane; the interpretation
call and the composer are the next levers and are separate measurements.

The live measurement suite has 62 cases and no concept-question turn, so a
rerun proves the repair change on strategy shapes and proves nothing about the
three audits at their edges. Round two adds live cases for exactly those edges,
in both languages: a capability question phrased as education, a macro or
movers curiosity question, a discovery request phrased as a question, and a
strategy described as a question with no asset and no number. Adding cases is
test work, not model-facing text.

## Found on the way, not this lane's

- The recovery texts `interpreter_unavailable` and the three context-curiosity
  fallbacks are English on `es-419`.
- The compute probes show the repair inventing backtest shapes from arithmetic
  questions; the calculations lane owns that.
- The three second reads persist no verdict; only the repair annotates its
  receipt. Their hit rates are unknowable today. Annotating the surviving
  audits through the existing `annotate_latest_openrouter_route_receipt` seam
  is a follow-up, not part of this lane.

## Round two: what changed

The changes that survived round one, each a post-hoc gate narrowed so a turn
with nothing to check runs no second read. Nothing decides ahead of the
interpreter, no model-facing text moved (`tests/test_interpreter_prompt_freeze.py`
passes unchanged), and `llm_interpreter.py` shrank by two lines.

| Call | Change | Owner |
| --- | --- | --- |
| `CapabilitySideQuestionAudit` | the educational-prose admit is gone; pending-field, removed-asset and vague-start admits stay | `_response_needs_capability_side_question_audit` |
| `ContextQuestionAudit` | the educational admit is gone; the unsupported strategy shape and the forced unsupported path stay | `_response_needs_context_question_audit` |
| `FocusedAssetDiscoveryRead` | triggers only on a typed contradiction: the primary typed a fact-kind `research_query` but left the payload empty | `focused_discovery_read_applicable`, over `research_routing.primary_read_asks_a_fact_question`, which `primary_research_query` now shares |
| `FocusedStrategyExtraction` | `educational_question` needs current-turn execution evidence, the precondition every strategy entry already had; a well-formed empty extraction ends the model ladder | `strategy_extraction_repair_is_allowed`; the ladder in `_repair_incomplete_strategy_extraction` |

Two proposals from round one did not survive. The unsupported-path thesis
clause stays: `test_extraction_cannot_invent_a_strategy_from_an_echo` pins
that a model-asserted thesis distinct from the message is an idea to extract,
a graded-routing decision this lane does not reopen. And the discovery read
was narrowed rather than unplugged, because the typed contradiction it should
resolve does exist, it just is not a concept question; the read stays wired,
observable, and dead on plain turns.

Tests: `tests/agent_runtime/test_ordinary_turn_runs_no_audits.py` proves a
concept question reaches the runtime with zero provider calls after the
primary read, that the strategy-flow shapes still earn their reads, that the
evidence predicate sees a named asset but not a concept, and that the ladder
stops on an empty extraction while still moving past a provider failure. The
three tests that pinned the deleted admits became trust tests on the same
shapes. The hermetic sweep (`tests/agent_runtime`, `tests/test_spine_guardrails.py`,
`tests/perf`) passes 2056.

## Round two: before and after

The deployed API runs `main`, so the #563 HTTP harness cannot measure a
branch before promotion, and the local QA backend needs a `DATABASE_URL` the
canonical environment does not carry. `scripts/benchmarks/interpret_stage_ab.py`
runs the same interpret node the API runs, in-process, under the same
seven-call allowance, on the #563 cohort messages, and records wall time plus
every receipt. It measures the #563 "interpret start to first outcome"
interval, which is where the four calls live; the roughly 1.7s of HTTP,
admission, persistence and SSE around it is untouched by this lane. Runs were
interleaved head, base, head, base and pooled per label
([evidence/565](evidence/565/README.md)).

RESULTS_TABLE

## Round two: the live scorecard

LIVE_EVAL_PARAGRAPH
