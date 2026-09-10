# Bounded validation after the fourth full measurement

The complete fourth measurement remains unchanged and failed. Its 11 failed
cases, plus three previously passing controls, will run twice in each arm:
56 fresh-process case runs, alternating candidate/integration order and then
reversing it. Controls cover a supported indicator strategy, a result capital
edit, and a Spanish explanation with no required tool. This is an explicitly
partial interleaved comparison, not another full-suite scorecard.

The integration arm is the unchanged checkout at
`542fcfb2432e906663160d8cb874d955faeafd16`. The candidate includes the bounded
cost-audit, call-scope, benchmark-owner and observation repairs. A normal merge
`156ddd9c21aaba1e24309db563882b1dadf70bc9` includes the new integration commit;
it changes only the product/design decision filters, with no runtime, API,
data, migration, UI-state, environment or test overlap. The earlier
`51086fda` reconciliation and its accepted deterministic evidence are retained.

[interleaved-fourth-repairs.py](interleaved-fourth-repairs.py) requires clean
checkouts and equal fixture inputs before any run. Each arm executes its own
unchanged native harness and grading contract. The candidate's extra bound
result and semantic selection checks remain active; this difference must be
reported rather than disguised as identical graders. No tool name is prescribed
by the schedule. Existing case IDs select tests, not runtime tools.

[retained-case-probe.py](retained-case-probe.py) leaves requests, return objects,
timeouts, schema validation and grades unchanged. It records completed
OpenRouter replies, the exact judge request payload (without headers), and the
final research sidecar for cost accounting. Both functions and final-patch
return identity are preserved. A [free mocked control](retained-case-control.py)
checks those boundaries, grade preservation, header exclusion and final
provenance assertions; its temporary mock output was deleted. Its
[control log](retained-case-control.log) is not live evidence.

Current-integration [provider-free controls](542fcfb2-baseline-controls/)
reproduce the existing next-experiment failure and the same downstream budget
ceiling state. They do not reconstruct an integration model reply or regrade
the candidate. Crypto controls establish inherited promotion boundaries but
cannot explain per-coin rejection from missing historical metadata.

No fingerprint update or lane clearance follows from this plan. Actual paired
results and their costs must be retained and assessed first.
