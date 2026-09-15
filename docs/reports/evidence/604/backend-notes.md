# Backend #604 regression evidence

Integration base: `d788449385ec93e92609b4692aa0fe8c1981ab58`.

The retained owner-scoped GET-only diagnosis in `completed-result-diagnosis.json`
identifies two independent reasons a completed DCA result could not share:

1. The inline `run_backtest` action uses `message_only` lifecycle ownership. Its
   persisted result carries `result_run_id` and a result card, but neither an
   ordinary `agent_runtime_turn` terminal envelope nor `backtest_job_id`.
   Sharing previously looked up only explicit job ids and research result message
   ids, then incorrectly required the absent ordinary-turn envelope. The owner
   gateway's associated job was succeeded and its run/evidence passed the shared
   canonical completion predicate. Sharing now resolves the exact run-linked job
   for that typed action and evaluates the existing predicate. Ordinary follow-up
   answers keep their own question; merely referencing a run does not inherit its
   question or add its card.
2. The production DCA adapter emits `entry_rule.cadence`. The closed receipt rule
   omitted that field, while the older fixture omitted the emitted rule. The
   receipt now retains this cadence. A regression runs the production adapter
   with synthetic metrics/chart inputs and verifies its actual rule and explicit
   recurring contribution survive projection.

`backend-regression-red.txt` records 11 failing original-policy assertions for
publisher links, long questions/answers, missing sources, memory/degraded answers,
plain answers, confirmation/clarification exclusion and visible backtest prose.
`backend-completion-red.txt` additionally records the direct completed-result
failure before its completion fix. No provider calls were made.

`backend-green.txt` records the final focused receipt suite: 371 passed, 46
Postgres-environment-dependent tests skipped. The focused Ruff check and current
working-tree modularity budget also passed. The parent owns final merged-tree,
CI, browser and review evidence.

The additive migration `20260914120000_share_plain_answer_receipts.sql` widens
only the existing snapshot kind check to accept `answer`; it must run at
promotion. No hosted migration, flag enablement, commit, merge or push was done
by the backend worker.
