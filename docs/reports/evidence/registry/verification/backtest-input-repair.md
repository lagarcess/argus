# Backtest input repair after the initial live measurement

The failed `../live-measurement-initial.json` exposed a mismatch between a
prepared durable artifact and the richer input needed to prepare it. Declaring
`StrategySummary` as the callable input lost typed temporal intent, money roles,
cost evidence and rule structure. Dispatch also bypassed the existing preparation
owners. The repair changes that ownership boundary rather than classifying the
questions that exposed it.

`BacktestStrategyInput` now owns the rich fields read by the declared callable,
the model's pending draft, and focused extraction. The latter projects shared
fields from this owner instead of maintaining another hand-written field list.
Money-role and runtime-extension metadata travel with their declared fields.
The legacy pending-draft decoder retains its historical top-level precedence;
actual declared inputs reject conflicting duplicate values, including a known
zero versus a nonzero amount.

The declaration's confirmation handler calls existing strategy preparation once,
with the same trusted saved-result context as the graph. It cannot authorize
execution. Canonical `StrategySummary` remains the prepared durable artifact,
with its serializer class unchanged. Approval compares the pure projection of
the exact confirmed inputs, without resolving the temporal window a second time.

Replay and contract tests cover nested explicit dates and crossover rules;
starting capital of 0, 1,000 and 5,000; contribution ceilings with and without a
recurring amount; grounded fee/slippage evidence; unsupported options and
sentiment facts reaching existing recovery; and an indicator period longer than
the data window reaching launch validation. The new declaration does not
silently substitute a runnable family for unsupported input.

Capability packets now include the generated effective catalog for every focus,
including assets. Capability and educational composition receive those facts.
The model-facing instructions refer to the same typed strategy input whether it
appears in a call or a pending draft; no calculation-specific capability prose
or question-to-tool mapping is introduced.

The initial grounding replay produced 12 failures and one passing control.
After repair, the focused follow-up passed 307 checks; the runtime, spine and
OpenRouter policy sweep passed 2,327 checks in 25.18 seconds. Ruff and the shared
modularity budget pass. These are deterministic checks; the repaired model-facing
surface still requires a new full live scorecard.

Separately, research recovery now keeps its typed unavailable code instead of
projecting an empty completed result. Its 473 research tests pass. A queued card
without a typed answer cannot offer a public receipt; 41 focused frontend tests
cover the sharing and card projection change. Private sourced narrative remains
valid delivered chat content and is deliberately excluded from public receipts.
The evaluation observation repair is recorded in `README.md` and
`measurement-observation-repair.json`.

## Combined checks before the next live run

The complete backend suite passed 6,742 tests and skipped 571 checks in
178.09 seconds. Its only failure is the deliberately unupdated measured prompt
fingerprint. The command explicitly set `ARGUS_RESEARCH_RAIL_ENABLED=false`;
test fixtures suppress provider credentials. The earlier restricted run's local
server/process-probe permission failures passed when run with local test-server
access (31 checks). The discovery language fixture now covers both actual rail
flag profiles at the shared operation; the publication fixture constructs its
call from the declared argument validator. Their behavioral assertions remain.

The combined Lane C, generated-fingerprint, neutral-import and production
checkpoint checks passed 133 tests in 13.00 seconds. Ruff and modularity pass.
The two new modules pass configured mypy. After a two-line typing repair, their
grounding/preparation checks passed 27 tests; the independent reviewer verified
equivalent audit construction, including explicit zero.

The independent repair review returned no remaining actionable finding, with
191 focused tests and 16 existing measurement strategy snapshots round-tripped
without mismatch. This is local review evidence, not the owed GitHub Codex round
or a passing live measurement. Integration remains
`743dfda3da9b467d32023ac32e900dad5a392500`, already merged by `3c4f5aab`.
