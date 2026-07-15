# Private Alpha Release Manifest Template

Use one manifest per validated candidate checkpoint or promoted candidate. Fill
this after the release gate passes and before sending tester links. A validated
private-alpha checkpoint records technical evidence only; it does not itself
authorize a `main` merge, production deployment, automatic production
deployment, tester invitation, or tester exposure. Do not include raw
conversation, user, run, or job ids; use the privacy-safe labels from canary
evidence.

## Candidate

- Candidate SHA:
- Candidate branch:
- Validation status:
- Validation surface:
- Promotion target: `main`
- Release captain:
- Approver:
- Rollback target:
- Decision record:

## Deploy Proof

- API service: `argus-api`
- API deploy status:
- API deployed SHA:
- Web service: `argus-app`
- Web deploy status:
- Web deployed SHA:
- Checked at:

## Environment Proof

- Expected mode:
- Release profile hash:
- Effective locales and capabilities:
- api_web_env_fingerprint:
- workflow_env_fingerprint:
- workflow_env_status:
- workflow_runtime_provider_mode:
- workflow_runtime_proof:
- env_fingerprint script output:
- workflow_task:
- real_workflow_task:
- Backtest service mode:
- Workflow service proof:
  - `argus-backtests` latest deploy/status:
  - workflow provider mode verified: `live_provider`
  - effective runtime provider mode verified: `live_provider`
  - effective runtime proof status:
  - required workflow secrets present with redacted proof:
  - active workflow task verified:
  - real workflow task verified:
- Feature flags:
- Render config audit command:
- Secret rotation / least-privilege owner:

## Gate Evidence

- Local smoke command:
- Local smoke result:
- Warmup command:
- Warmup result:
- Canary evidence artifact: `private-alpha-canary-evidence`
- Authoritative Spanish release canary:
  - JSON evidence:
  - Exact candidate SHA verified:
  - Finalized evidence/result labels:
  - Decision-note label and reload hydration:
  - Omnisearch source identity:
  - Browser signup/login proof:
  - Failed-capture replay, if failed:
  - Exit status:

## Release Decision

- Public tester exposure approved:
- Known caveats:
- Rollback trigger:
- Rollback command or owner:
- Follow-up owner:

## Privacy Notes

- No raw conversation, user, run, or job ids.
- Canary labels are stable hashes for audit correlation only.
- The release profile contains no credentials, account ids, deploy ids, or
  candidate SHA; record its hash with the candidate evidence instead.
- Failed-capture artifacts are sanitized replay inputs, not raw transcripts.
- Service-role credentials, cookies, prompts, and route receipt payloads are not
  copied into this manifest.
