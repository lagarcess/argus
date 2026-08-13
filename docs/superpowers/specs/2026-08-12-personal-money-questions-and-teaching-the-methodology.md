# Personal Money Questions, and Teaching the Methodology

Status: DRAFT, founder-authored 2026-08-12. Not scheduled, not a lane.
Origin: private alpha feedback on the first day Argus had real users.

## 1. Why

Two things happened on 2026-08-12 that this document exists to hold.

A user asked, in Spanish, on the guest path:

> Cuanto dinero debo ahorrar si mensual si mi sueldo es 38,000 pesos, tengo
> gastos y quiero una ipad?

Argus refused:

> Argus se especializa en validar ideas de inversión con backtests históricos y
> no ofrece consejos personalizados de ahorro o presupuesto.

She had given Argus a salary, stated expenses, and a concrete goal with a price.
That is the richest input a personal finance product can receive, and the
product declined it and described a capability she had not asked about.

The same user then sent two suggestions, unprompted, in her own words:

> 1- Quizás al iniciar (cuando uno entra) podría tener un párrafo corto o
> bullets de funciones principales que hace la ia; porque ya estamos
> acostumbrados a que sabemos por ejemplo que a chatgpt le podemos preguntar o
> subir cualquier cosa y va a buscar info en internet para darte una respuesta,
> pero como esta es una metodología diferente, para personas como yo que
> normalmente no usamos una ia financiera caeríamos en el mismo formato que le
> preguntamos a chatgpt o claude.

> 2- Hice una pregunta super genérica si, pero podría darte una sugerencia de 3
> preguntas básicas que le podría responder para ir alimentando el desarrollo de
> mi pregunta y la ia me pueda responder.

Both points are the same problem stated twice: **Argus does not teach people how
to talk to it.** The first is teaching before the first message, the second is
teaching after a broad one.

Separately, feedback from the same cohort: users believe Argus is a finance
ChatGPT for anything, savings, bonds, banking products. They are not arriving to
run a backtest. Every one of them so far is a non-finance person, which is
exactly who `DESIGN.md` says the product is for. No trader or economist has
tested it yet.

## 2. The line that keeps this from becoming ChatGPT

Founder concern, stated plainly: the risk of answering personal money questions
is becoming another chat app, which is why memory and real backtests exist.

The line is not "refuse anything that is not a backtest." It is:

**Compute what the user gave you. Never prescribe what they should do.**

"Your iPad costs 45,000 pesos, you have 38,000 monthly, at 5,000 a month that is
nine months" is arithmetic on her own numbers. "You should save 20 percent of
your income" is advice, and the existing not-advice framing already refuses it.

The first is a grounded calculator. The second is regulated territory Argus does
not enter.

## 3. The conversion is the product

A general assistant answers the savings question and stops.

Argus answers it and then says:

> You would have 45,000 pesos in nine months. Want to see what that would have
> done in an index fund over the same period?

That single move is the whole differentiator. It turns a personal money question
into a runnable test, which is the thing Argus does that nothing else does.

It is also not a new pattern. The research rail already answers a question and
offers one to three fully specified, runnable test cards. This is the same
mechanism reaching a question shape the rail does not currently cover.

## 4. Personal money math as a sixth question shape

The rail covers five shapes today, all market-facing: market pulse, competitor
analysis, screening, sector radar, single-stock analysis.

Users arrived with a sixth: **personal money math with a goal.** Salary,
expenses, a target purchase, a horizon. It converts into a backtest cleanly, and
refusing it is where the funnel currently loses people.

Constraints that make it Argus rather than a calculator:

- Every number either comes from the user or from a cited source. Nothing is
  assumed. If the iPad price is needed, it is looked up and attributed.
- The arithmetic runs in our code, with tests. See section 7.
- The turn ends with a runnable offer, never with a plan the user is told to
  follow.

## 5. Currency and locale come from the user, not from a default

Observed defect the same day: a user said "13,000 pesos" and Argus carried the
number without a currency concept at all. `currency_pair` exists as an asset
class for forex; nothing interprets a stated amount as a currency.

Thirteen thousand Dominican pesos is roughly two hundred dollars. Rendering it as
$13,000 is wrong by a factor of about sixty five, silently, in a product about
money.

Founder direction: **location tells us the operating currency by default, and
the user can override it.** These are Dominican users. We have exchange rates
available. The default should be DOP for a DR user, flexible on request, and the
currency should be explicit in the card rather than assumed.

Perplexity's location filter supports the derivation. This is not a
localization concern; it is a correctness concern.

## 6. Grounding local reality is the real moat

Dominican users shop DOP/USD rates across several local banks, and their
financial information lives on a small number of local sites rather than in any
model's training data.

Perplexity domain filtering makes that a curated list rather than a hope. A
general assistant guesses at a Dominican bank's rate; Argus can cite today's.

That is grounding no general chat app has, it is cheap to build, and it is the
answer to "how is this different from ChatGPT" that a real user in Santo Domingo
would actually feel.

The same applies per country: location-filtered economic questions where the
sources are local. For the United States, `FRED_API_KEY` already exists in the
codebase and has never run in production, so there is unused capability before
any new one is added.

## 7. Tool assessment, honest

**Perplexity domain filtering: yes, highest value.** A curated list of Dominican
finance and bank rate sources. Cheap, differentiating, immediately felt.

**Perplexity location filter: yes.** Per-country economic questions, and the
derivation for section 5's currency default.

**Perplexity sandbox for calculations: no.** The 2026-08-12 math audit found
seven defects in arithmetic Argus owns, controls, and can unit test. Moving
financial arithmetic to a remote sandbox that cannot be unit tested is strictly
worse. Money math stays in Python, in this repository, behind the invariant
tests the audit produced.

**Bank API access, for example apiportal.popularenlinea.com: a thesis, not a
lane.** If a user's held products were known, Argus could show the realised
performance of their certificates of deposit and bonds against alternatives,
which is genuinely compelling and entirely on-thesis.

It also brings a regulatory posture, a security surface, a consent model, and a
support burden that do not exist today. It would require the memory and
personalization work to be real rather than dark. Park it, do not schedule it.

## 8. Teaching the methodology

Two moves, from the user's own two suggestions.

**On arrival**, say what Argus does with a question, not only what to ask. The
starter chips teach by example and never state the method. One line about
testing ideas against real history does more than three more chips.

Note that #481 means a guest who presses New chat sees a blank state, so chips
may never have been on screen for the second turn onward. Fix that before
concluding the chips are insufficient.

**When a question is too broad**, offer three specific questions that would make
it answerable, instead of refusing or asking one open question.

**This is not the menu the roadmap forbids.** A skill store, a picker, or a
capability list is a catalogue of features shown regardless of input. Three
questions derived from what the user actually asked are a response to their
input. The rule was that the range is reached through natural language; this is
natural language doing the reaching.

The same move fixes three observed failures: the iPad refusal, #483 where Argus
asked "which asset" after naming Coca-Cola, and the "use 10k" turn that fell
back to typed options only because interpretation timed out.

## 9. What this is not

- Not budgeting software, not a savings tracker, not an expense categoriser.
- Not personalized financial advice. Section 2 is the boundary.
- Not a general assistant. Every answer ends in something testable or in an
  honest statement that Argus cannot test it.
- Not a reason to widen the interpreter's surface before the current defects
  close. #453, #483, and #455 all live in the same territory.

## 10. Open questions for the founder

1. Does personal money math become a sixth rail shape, or a separate surface?
2. What is the smallest version worth shipping: arithmetic plus conversion with
   no grounding, or grounded from the start?
3. Which Dominican sources go in the domain list, and who maintains it?
4. Does currency selection belong in settings, in the card, or both?
5. Is the trader and economist cohort tested before or after this? All feedback
   to date is from non-finance users, and the two groups may want opposite
   things.

## 11. Evidence

The refusal, the two suggestions, and the currency observation are all from
production usage on 2026-08-12, the first day Argus was distributed. Roughly
twenty people, all guests, all non-finance.

Eleven issues were filed the same day from that usage. This document holds the
part that is not a defect.
