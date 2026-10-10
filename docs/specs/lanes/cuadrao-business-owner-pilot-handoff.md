# Resume the Cuadrao Business owner-pilot records

This replaces the original dispatch prompt. Its exact text remains in the
[published October 8 revision](https://github.com/lagarcess/argus/blob/d86a791d0cf0de22ab43b0a7ea1cea2a756f6c48/docs/specs/lanes/cuadrao-business-owner-pilot-handoff.md).
The implementation lane has already run. Do not dispatch it again from an old
planning checklist.

Read the [current scope and decision provenance](cuadrao-business-owner-pilot.md#current-authority-and-landing-boundary),
the [Business handoff](../../handoffs/cuadrao-business-lane.md), and the
[core-flow tracker](https://github.com/lagarcess/argus/issues/942). The handoff is a
dated checkpoint. Later founder continuations in the scope document supersede
its local-work pause, but do not prove that every requested outcome was delivered.

## Current documentation assignment

1. Fetch `origin/codex/private-alpha-next` and record its SHA.
2. Reconcile #900 and #910 with current integration and the recorded continuations.
3. Preserve the existing technical contracts and the original design rationale.
4. Verify that each final PR changes only its two planning documents.
5. Run documentation checks, modularity checks, review, and exact-head CI.
6. Report the final head and remaining evidence gaps to the coordinator.
7. Wait for the serialized merge slot. Do not enable auto-merge.

The owner API, S1–S3 isolation, and non-model-facing S4 separation already landed.
The [implementation checkpoint](../../handoffs/cuadrao-business-lane.md#implemented-and-merged-into-integration-all-default-off)
records their PRs. Do not recreate those changes.

## Preserve separate work

- Keep #925 intact. Its model-facing restrictions, refusal presentation,
  evaluation-budget work, and Business scorecard are outside this landing.
- Keep `codex/cuadrao-business-sandbox` at its preserved checkpoint
  `df208f7ec2379cd84efd55eea0deb685d67c5360`. Do not include its later capture,
  email, WhatsApp, search, or custodian changes in the planning PRs.
- Preserve local audit notes and private configuration. Never add credentials,
  received customer documents, or private message contents to the PR.
- Leave Consumer, Marketing, staging deployment, and shared running services
  under their existing owners.

## Delivery and authority limits

**October 10, 2026 update.** The founder approved the Business agent direction later the same day. The [Business agent execution spec](cuadrao-business-agent-execution-spec.md) now owns the Business build order, the agent contract and the open decisions. Where this document says "Business chat stays off" or that the agent audit approves no model-facing implementation, that spec takes priority for build work. Business chat stays off in hosted environments. Each model-facing change still needs a committed scorecard.

Business chat stays off. This assignment changes no code, schema, flag, UI copy,
provider setup, or model instruction. It includes no paid calls, hosted actions,
phone work, main promotion, or broad UI pass.

The earlier owner-only and email-deferred scope is not the full current product
promise. Later capture and agent requirements remain tracked separately. Do not
claim complete capture, extraction, accounting readiness, real WhatsApp delivery,
or hosted acceptance from the publication of these documents.

After an authorized merge, run the repository integration-landing workflow within
the granted scope. Report implemented, locally verified, provider-verified, and
hosted-enabled status separately. A green documentation PR proves none of those
runtime outcomes by itself.
