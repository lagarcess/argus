# Calculation follow-ups and the money-answer goalpost

Founder-directed 2026-09-14 from the acceptance dry run at `03918912`, PR #631.

## 1. Why

The grounded-finance roadmap requires a money question to reach a primitive,
compute, or state an honest bound. A conversation cannot do that when its next
turn loses the previous calculation's inputs. The decision memo's durable
artifact boundary and the Split-Brain Rule make the stored card the owner.

## 2. Locked decisions

1. Runtime history derives calculation facts from stored typed cards, including
   inputs, provenance, outcome and results. Prose cannot override these facts.
2. Replies complete requested inputs and explicit user changes recompute through
   the registered calculation. Unchanged inputs retain their sources.
3. An unstated currency derives from the resolved profile currency, with recorded
   assumption provenance; explicit currencies remain explicit.
4. Model-owned language must describe the computed card, withhold personal
   product selection when necessary facts are missing, and use the current
   spending goal for currency-risk direction.
5. Historical drawdown is a registered calculation using Argus market-data
   history and the existing drawdown math. It reports its actual observation
   window and cannot accept research/model price arrays as market history.
6. Build and test deterministic work first. Present exact proposed model-facing
   strings and stop for founder go before any live measurement.
7. A follow-up needing no new facts never calls research, including a changed
   input and explaining an earlier answer. `ResearchQueryExtraction` owns
   `requires_new_facts`; an asset name alone does not override false. Its new
   description is measured with the rest of the lane's model-facing text.

Implementation clarification: the ratio family gains one `scaled_amount`
calculation for multiplying/dividing by a percentage or quoted ratio without an
invented annual time basis. It covers cash-back and currency conversion with
honest units. Historical drawdown is a provider tool, read-only, with no automatic
decision rerun; its default five-year window is explicitly labeled. It measures
the provider's asset prices, not a return translated to the profile currency.

## 3. Reserved scope

No interpreter taxonomy, phrase routing, research-provider replacement, personal
memory, brokerage, migrations, merge or deployment. Unrelated failures in #631
remain outside this lane. No paid calls before the explicit measurement go.

## 4. Contract gates

Update `docs/API_CONTRACT.md` for typed history, pending input changes, currency
provenance and historical drawdown. Use the existing generic ToolResultCard and
its bilingual catalogs. Preserve public request compatibility. Document exact
model text separately from deterministic proof; do not refreeze without evidence.

## 5. Execution contract

One worker PR, `codex/calculation-followup-goalpost`, against
`codex/private-alpha-next`. Original fetched base:
`0893c27e878f8b55c39afb467cba15ed0ed3cfee`.

Implementation sequence: typed history; pending input/currency behavior;
historical calculation; bilingual regression measurement fixtures; exact prompt
proposal; founder go; live measurement, CI and Codex review.

Proof: red/green focused Python regressions, registered calculation tests,
mocked eval harness, relevant frontend catalog checks, modularity budget against
the reconciled integration tree, exact-head CI and a clean Codex review with
zero unresolved threads. After go, the measurement adds English and Spanish
cases for every listed failure, with durable browser evidence where relevant.
The prompt freeze may remain failing until that measurement. No READY claim
before the corresponding evidence exists. The founder alone merges.

## 6. Stop conditions

- Stop on a second Codex finding on the same mechanism; report both findings.
- Stop and show exact strings before live model measurement.
- Stop on a need for a second runtime, question-specific routing, research data
  entering historical computation, or scope beyond the named ownership boundaries.

## Sources

- `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md`,
  `docs/DATA_MODEL.md`, `.agent/designs/argus/DESIGN.md`.
- `docs/specs/argus-grounded-finance-roadmap.md`, operating rules, goalpost and
  Any grounded math; `docs/specs/private-alpha-next-decision-memo.md`.
- PR #631, `findings.md` and `report.md`, inspected from `origin/pr-631`.
