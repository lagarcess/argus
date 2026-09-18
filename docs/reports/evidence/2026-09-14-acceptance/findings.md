# Failures grouped by observed cause

Product under test: `039189128ea6ffcf59be73f3564fd936f191f662`.
These are observed reproductions, not promises of deterministic model behavior.
No product fixes or extra paid reproduction attempts were made.

## A fallback creates an unrequested backtest requirement

Smallest reproduction: registered user, Spanish, home country DO; new chat;
`¿DOP$1 millón en un bono del Banco Popular?` (Q4).

The phone answer says Argus cannot execute that rule and offers a supported
stock or crypto symbol. The question requests neither a rule nor a backtest.
The stored clarification is `unsupported_symbol`, and its payload invents a
`buy_and_hold` strategy for the bond.

The trace establishes the path: Grok interpretation timed out, Haiku fallback
failed with `ConnectError`, and focused strategy repair ran. In
`src/argus/agent_runtime/llm_interpreter.py`,
`_focused_strategy_repair_after_candidate_failures` seeds `strategy_drafting`
before the repair. The recovered bond then encounters asset validation.
This is the specific split between the money-question contract and the
strategy-only rescue path. The same English smoke question computed coupon
income; the language comparison is evidence, not proof that language alone
caused the failures upstream.

Evidence: [phone](screenshots/registered-q4-es-419.png),
[stored turn and route receipts](turns/registered-q4-es-419.json).

## Research exceeds the turn deadline and yields no money answer

Smallest reproduction: registered user, Spanish, home country DO; new chat;
`¿Cuánto necesito ganar para comprarme un Porsche?` (Q2).

The stream entered research and terminated after 180 seconds with
`agent_runtime_failure`; the API log identifies `RuntimeEventTimeoutError` /
`agent_runtime_event_timeout`. The phone renders a generic Spanish error twice.
It offers neither a computation nor an informative bound on the money question.
The specific cause of provider latency was not isolated. An absent research
invoice is reserved separately in the meter, not counted as zero.

Evidence: [phone](screenshots/registered-q2-es-419.png),
[stored turn](turns/registered-q2-es-419.json).

## The answer omits the required historical drawdown

Smallest reproduction: registered user, English, home country US; new chat;
`Should I put my emergency fund in crypto?` (Q10).

The answer is a sourced risk essay with no computation, historical tool card,
confirmation or displayed drawdown. The active smoke table explicitly says to
compute the drawdown, show it, and stop. Earlier committed evidence accepted a
generic boundary answer; that older verdict does not satisfy this explicit bar.
The missing artifact is proven; the exact routing or answer-generation change
needed to produce it is outside this audit.

Evidence: [phone](screenshots/registered-q10-en.png),
[stored turn](turns/registered-q10-en.json).

## Product comparison becomes a personal selection without inputs

Smallest reproduction: registered user, English, home country US; new chat;
`Which credit card should I get?` (Q5).

The response acknowledges missing credit/spending context, then names Citi
Double Cash as the closest general-purpose fit. That selects a product without
the facts the answer itself says it needs. The committed answer explicitly
withheld a selection. Spanish Q5 instead offers an option to compare and
withholds a best/cheapest choice. This is an observed answer-generation failure;
a deterministic root cause was not isolated.

Evidence: [phone](screenshots/registered-q5-en.png),
[stored turn](turns/registered-q5-en.json).

## Follow-up context loses inputs or stays on the wrong primitive

Smallest reproduction for lost card facts: registered English Q2, then change
only the Macan income share from 10% to 15%, retaining the quoted lease payment.
The prior card stores USD 1,129; the reply says it does not have that payment.
See [the two-turn reproduction](turns/followups-q2-en.json) and
[phone](screenshots/followups-q2-en.png). Expected arithmetic is 1,129 / 0.15.

Other instances lose a just-supplied period (English Q3), monthly spend
(Spanish Q5), or exchange amount and direction (Spanish Q7). These are observed
context/interpretation failures; this audit does not claim one implementation
cause for all of them. Spanish Q4 retains the mistaken bond backtest state from
its initial answer. Spanish Q8 also asks for a backtest window after an inflation
calculation input changes. Each exact pair is linked in the report.

## Arithmetic does not reach an executed calculation

Smallest reproduction: registered English Q4, then halve only the invested face
value. The response gives the correct DOP 52,500 as model prose, but has no
computation artifact. English Q5 acknowledges the inputs to a 2% reward
calculation yet supplies neither its USD 20 answer nor an informative bound.
These fail the primitive/computation clause even though neither names an
unasked capability. See [Q4 follow-up](turns/followups-q4-en.json) and
[Q5 follow-up](turns/followups-q5-en.json).

## Prose and the computed artifact disagree

Smallest reproduction: registered Spanish Q3 with home country DO, then supply
48 monthly payments. The card uses periods=48 and computes 4,918.77 while the
prose still asks for periods. It displays USD although the profile is DOP and
the user supplied no USD currency. See [phone](screenshots/followups-q3-es-419.png)
and [stored result](turns/followups-q3-es-419.json).

## Currency advice reverses the risk after the goal changes

Smallest reproduction: registered English Q7, then change the goal from dollar
expenses to a fixed peso expense, without a new lookup. The answer says matching
pesos removes peso-depreciation risk. For dollar savings funding that fixed peso
bill, peso appreciation is the adverse direction. See
[the answer](turns/followups-q7-en.json). The initial answer described the
mismatch correctly; the goal change is where the answer fails.

## Recovery prose names a test on a savings conversation

Smallest reproduction: registered Spanish Q1, then supply a 12-month deadline.
The recovery response says it could not create a reliable test setup, although
no test was requested. The record contains `interpreter_unavailable` recovery
while lifecycle metadata says completed with no failure code. The recovery
message owner is `src/argus/agent_runtime/recovery_messages.py`.
See [phone](screenshots/followups-q1-es-419.png) and
[stored evidence](turns/followups-q1-es-419.json).

## Additional observations

Some history-only follow-ups still invoke paid research, despite requiring no
new facts and explicitly asking for no lookup. Correct conceptual answers can
therefore pass the stated goalpost while carrying unnecessary cost and a failed
lookup disclosure. Spend is included, not waived. Provider retry/fallback
behavior also varies across otherwise equivalent questions.

Q9 and its capital edits stop at the normal ready-to-run confirmation, matching
the committed smoke acceptance. No Run backtest button was clicked. These pass
routing and bounded confirmation acceptance; they are not new completed-engine
execution evidence. Long answers are preserved as full rendered text alongside
the requested phone-width viewport screenshot.
