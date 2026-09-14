# Acceptance evidence

Start with [report.md](report.md) and [findings.md](findings.md).
The tested product is `039189128ea6ffcf59be73f3564fd936f191f662`.
Only drivers and evidence are changed in this lane. Nothing was fixed or deployed.

## Reproduction contract

- Base the product runtime on a clean archive of the tested integration SHA.
- Use a disposable local Supabase stack with the archived migrations, real local
  auth, and the production web build. This run used project
  `argus-acceptance-20260914`, API 8149, web 3149, Supabase API 56731 and PG 56732.
- `drivers/launch.py` derives model names and literal flags from `render.yaml`,
  checks the release profile, and reads provider secrets privately from the
  canonical `.env`. It rejects unapproved environment drift. Its explicit local
  differences are recorded in [environment-proof.json](environment-proof.json).
- The archived runtime and all private inputs/logs lived outside the repository
  at `/private/tmp/argus-acceptance-20260914`. Drivers intentionally identify this
  owned scratch directory so cleanup cannot target arbitrary files or services.
- `drivers/walk.mjs` adapts the committed grounded-math browser driver. Execute
  `preflight`, `registered`, `followups`, then `guest`; admit each paid phase only
  after reconciling `drivers/meter.py` and the remaining budget. `rendered` is a
  read-only history capture without new model turns. Follow-ups are in
  [followups.json](followups.json), written against the actual preceding answer.
- All 46 smoke prompts are synthetic public roadmap questions or synthetic
  follow-ups. Their full stored artifacts and rendered text can be committed.
  One initial English Q1 required recovering its actual conversation ID after
  the web created a new conversation; the stored result was reused, not rerun.
  Its record marks the unavailable original SSE capture.
- For private replay, use the adapted September 12 `pull_private_replay.py`,
  `replay_driver.py`, `record_replay_verdict.py`, `watch_acceptance_budget.py`, and
  `cleanup_replay.py`. A new run needs explicit production-read approval. The
  approved cohort is the union of UTC and New York August 12 guest conversations,
  excluding internal/canary accounts, with all user turns in conversation order.
- One initial private turn was emitted to tool output before the restriction was
  enforced. Local cleanup cannot erase that tool history. No customer text is
  committed. Never print further private transcript payloads. After an automatic approval review
  rejected a proposed private-text inspection, this run used
  `judge_private_replay.py`: a private structured semantic assessor that can
  return only finite verdict codes, booleans and confidence. The same release
  structured model receives the private context; its receipt cost counts in the
  separate replay budget. This is model-assessed evidence, not a claim that a
  human independently reviewed every customer reply. Low confidence is a fail.
- `export_replay.py` exports only explicit allowlisted metadata and fixed verdict
  reasons. It exports no user text, assistant text, artifact payloads or original
  customer identifiers. Private replay screenshots are not committed because
  they would contain customer text.
- Before cleanup, export final stored metadata, verdicts and meter. Then run the
  cleanup driver, which stops only owned processes and the disposable stack,
  deletes private inputs, responses, logs and local database volumes, and writes
  [cleanup-proof.json](cleanup-proof.json). It checks unrelated stacks survive.

## Meter semantics

[phase-admission.json](phase-admission.json) records smoke admission decisions.
The initial estimate derives from committed grounded-math costs; the follow-up
and guest estimates include contingencies. The replay estimate derives from the
September 12 replay plus contingency. The smoke cap is $9; replay has a separate
$4 cap, including the private assessor.

The live read-only observer records provider receipts immediately. The meter
also reconciles unpriced research ledger rows, and keeps missing invoices as
estimates rather than zero. Missing OpenRouter attempts reserve $0.02 each;
missing research usage assumes 30k input tokens, 15k output tokens and 20 finance
searches at the repository pricing table, totaling $0.625. These are estimates,
not verified invoices or mathematically guaranteed invoice ceilings. The guard
holds a further $0.65 before another turn and stops the owned API near the cap.

The complete smoke matrix has a phone viewport screenshot and stored route and
failure metadata for every answer. Empty lifecycle failure codes are preserved
even where a separate recovery payload or the rendered answer exposes failure.
