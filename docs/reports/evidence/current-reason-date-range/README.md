# Current reply reason and stated date range

Status: implementation prepared; paid measurement is not authorized yet. This
is a progress record, not a READY or terminal audit. No merge or deployment.

## Cause and change

The clarification writer appended the last six transcript messages as live
chat turns after its current typed context. An earlier assistant complaint
could therefore compete with the current stored blocker. The writer request
now has no history field; the interpreter and durable history still keep it.
Every reply kind and both primary/fallback writers use the same current input
boundary. Options remain the current response intent's typed options.

The dateparser search for the reported English date phrase returns August 16
and “days this year”, losing August 19. The Spanish search finds both stated
dates and a trailing year. The natural-time adapter chose its first and last
matches, making December 31 the end, even when the structured model supplied
August 19. Mixed year plus named/numeric date evidence now declines this weak
normalization; the structured temporal intent owns the full reading. This is
language-neutral and adds no phrase table or pre-interpreter routing.

## Exact model-facing additions

Clarification writer system instruction:

> Use the current response_intent and typed constraints as the authority for this reply's reason and next step.

Shared `LLMDateRangeIntent.kind` description, used by the primary interpreter
and focused date extraction:

> Use explicit_range when the user states both endpoints; a year phrase qualifies their year and must not replace either endpoint with a whole-year window.

The existing prompt fingerprint is deliberately unchanged. It must be
remeasured, compared against the committed 71-case baseline, and refrozen only
after the approved measurement. No synthetic or stale scorecard substitutes
for that gate.

## Free verification

At reconciled runtime commit `948a085f0378aadcec064d75fa7bade07f670888`:

- 53 new regression checks fail against source archived from original
  integration `039189128ea6ffcf59be73f3564fd936f191f662` (all expected failures).
- 592 focused checks pass after reconciliation: reply inputs, supplied
  date-to-capital replay, date repair, conversation stages, history retention,
  incoming research recovery, the documented mocked eval harness, and
  modularity tests.
- Repository Ruff lint and the modularity budget pass.
- Python package sdist and wheel build passed before reconciliation; no
  packaging configuration changed in reconciliation.
- Prompt freeze: 1 expected failure, 2 passes; only the two instruction owners
  above changed their measured text.
- A broad local run during implementation was not green (43 failed, 8359
  passed, 599 skipped). Its lane test mismatches were corrected and covered by
  the focused pass. Other failures included sandbox-denied socket/sysctl work
  and research/memory expectations; they are not waived as a green suite.
  GitHub CI remains the independent full-suite check.

The reply checks are deterministic input-boundary evidence, not proof of live
model prose quality. The new live measurement cases are
`messy_english_explicit_end_survives_year_qualifier` and
`messy_spanish_explicit_end_survives_year_qualifier`; both assert the actual
stored dates. Their `current_year-` expectation is bound through the canonical
New York clock once at fixture load. The launch assertions describe this
September acceptance window; before August in a subsequent year the dates
would correctly need future-window recovery instead.

## Replay limits

The report supplies user turns 1 and 3, but not user turn 2. The scripted
replay covers the two supplied messages and the intervening wrong date reply;
the missing user message has been requested rather than invented. A complete
three-user-turn replay remains pending that text.

Integration's capital floor is now $10, so $100 no longer reproduces the
historical capital blocker. The replay injects the reported stored blocker at
the writer boundary and takes numeric bounds from current canonical config;
it does not claim today's validator rejects $100.

## Integration reconciliation

- Original base: `039189128ea6ffcf59be73f3564fd936f191f662`.
- Refreshed integration: `5cb360c1bb09ce75ab09559a47c7518026ef2fcf`.
- One-way reconciliation merge: `948a085f0378aadcec064d75fa7bade07f670888`.
- Shared test owner: `tests/test_degraded_recovery_history.py`; incoming work
  retains failed lookup replies in interpreter history. This lane preserves
  that behavior and excludes transcript history only from the clarification
  writer. The merged history and research-recovery checks pass.
- Shared documentation: separate paragraphs in `docs/API_CONTRACT.md`.
- No overlap in the changed date resolver or model-facing instruction owners.
  No lane schema, migration, environment variable, or frontend state change.
- Retained: original-source red proof. Revalidated: focused deterministic
  evidence on the merged tree. No paid or browser evidence exists to retain.

## Proposed paid gate

Proposed total spend ceiling: **US$5**, pending founder approval. Scope: the
full 73-case measurement, targeted current-reason English/Spanish acceptance
(including real browser turns), and at most one retry of an unexpected failed
case within the same ceiling. Stop before another paid call if the remaining
budget cannot cover it; do not run an unbounded batch without a cost guard.

The prior committed 71-case scorecard reports $1.488534 in known provider
charges, with 13 receipts lacking reported cost, so this is a proposed budget,
not an all-in price guarantee. A bounded reservation must account for those
unpriced routes before dispatch. Spend so far in this lane: $0.

After approval: measure, compare every existing case, commit evidence and the
new fingerprint, finish exact-head CI and Codex review, then report without
merging. If Codex raises a second finding on the same mechanism, stop and
report instead of applying another fix.
