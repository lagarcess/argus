# Refusal log

Deliver the grounded-finance board's Instrumentation item and #314 in one PR.
Founder instructions supplied on 2026-09-08 govern this bounded lane.

## Why

The board asks us to retain what people asked and what Argus did, then judge
refusals when reading. `docs/PRODUCT.md` says Argus must not refuse questions
it can compute or ground. No writer can decide which future question is a bug.

## Locked decisions

1. One private observation store covers terminal chat outcomes and admission
   rejections. No refusal category, missing-primitive guess, or correctness label.
2. Observe all terminal replies. This preserves boundaries stated only in prose
   without a phrase matcher, classifier, or changed model contract. Successful
   replies are context in the same read surface, not classified as refusals.
3. Accepted turns store exact request/response message links. A service-only
   view reads their content, action and outcome metadata from canonical messages.
   Rejected requests have no messages, so the record owns their submitted message,
   typed action and unchanged HTTP problem. Never infer pairing by timestamp.
4. Existing runtime facts retain their shape. Values are observed, never assigned
   new semantic categories. SQL groups existing outcome fields to read frequency.
5. Observations stay internal to Supabase. No frontend/API read surface, PostHog
   export, model context, or fingerprint change. Owner deletion removes records;
   message deletion removes linked observations. Rejected target ids are supplied
   claims, not proof an artifact exists or belongs to the actor.
6. Observation failure must preserve the original response and usage semantics.
   Report only a content-free operational failure. No background task may silently
   outlive the response to provide the sole write attempt.

## Reserved scope

No taxonomy, live eval, model text, visible recovery, analytics dashboard,
retrospective adjudication, forecast capability, or hosted migration.

## Contract gates

- `docs/DATA_MODEL.md`: private table/view, ownership, retention and query examples.
- `docs/API_CONTRACT.md`: internal evidence only; public contract unchanged.
- Additive Supabase migration and typed Python observation contract.

## Execution contract

One PR to `codex/private-alpha-next`; founder merges. Original and fetched lane
base: `00331188c9e42bb86b74042d0a74a8e24e423af3`.

Proof: a hermetic refused turn is readable with the asked text and existing
structured shape; all #314 rejection paths retain exact problem responses and
consume no allowance; read-only SQL frequency queries, RLS and deletion checks;
mocked eval harness, fingerprint freeze and modularity check. No browser proof
or live eval is required because visible and measured behavior is unchanged.

## Stop conditions

Report if complete capture requires a model contract or fingerprint change,
visible behavior change, inferred artifact ownership, hosted schema mutation,
or a write-time semantic classification. Do not weaken the privacy boundary.

## Sources

- `AGENTS.md`
- `docs/specs/argus-grounded-finance-roadmap.md`, Refusal log
- `docs/PRODUCT.md`
- https://github.com/lagarcess/argus/issues/314

The exact-pair observation view is an implementation choice derived from the
single-owner rule: messages already own transcript content and typed outcomes.
