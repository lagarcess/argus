# Task 8 report: reconciliation and delivery readiness

## Outcome

Issue #453 is deterministically clean after the required one-way merge of
final fetched integration `716221f07ca50c3fdb1ad8de5314b07072bfe815`.
The reconciled execution head is
`aeb0a12e6f6b978821d47152485f5ffd7995fcb1`.

The only unresolved release gate is the paid exact-head live interpreter run.
A corrected pre-reconciliation run reached real providers but finished red at
`33 passed / 13 failed`; the later market-hours integration merge invalidates
it as exact-head acceptance evidence. The permitted rerun was rejected by the
external credential-backed traffic approval boundary. No workaround was used.

## Reconciliation

- Original base: `8025672924d1c74eb80cc926c72b5d8574b613d7`
- First integration: `c3a9aca181ea43770a81c13ec2fb5f02f85af293`
- First merge: `b585d429fee633751d5aa19b6668db79165944f9`
- Final integration: `716221f07ca50c3fdb1ad8de5314b07072bfe815`
- Final merge: `aeb0a12e6f6b978821d47152485f5ffd7995fcb1`
- Browser product source: `d87d5d6524e0af89d99dab26cc3e4b6f56c24742`
- Last issue test fix: `9df5cb1b16bc5174a820d69bdb17e30b78f114e2`

The final integration delta added password-recovery CAPTCHA handling and a
market-hours coverage clamp. `docs/API_CONTRACT.md` was shared, but its Account
recovery section is separate from issue #453's Cause-aware unsupported recovery
section. The union merged cleanly. No issue-owned runtime, frontend recovery,
or locale file changed during reconciliation.

## Exact reconciled evidence

- Python `3.10.20`: PASS.
- Ownership check: PASS, no policy for the branch.
- Ruff lint: PASS.
- Ruff format: baseline RED, `141` files versus `143` at exact integration.
- Full backend: `5075 passed, 495 skipped, 7 failed`, coverage `87%`.
- Permission-sensitive rerun: `8 passed` outside the sandbox.
- Mocked interpreter eval: `72 passed`.
- Focused issue plus locale checks: `33 passed`.
- Modularity script: PASS, no violation.
- Modularity tests: `8 passed`.
- Full web suite: `1482 passed`, `0 failed`.
- Web lint: `0` errors, `8` integration warnings.
- Production web build: PASS, `12/12` pages.
- TypeScript: existing baseline RED at `6034` on both exact integration and
  this lane; legacy recovery file `80` on both; new focused file `0`.

The full-backend failures are six sandbox process/socket denials and the
unchanged integration-baseline OpenRouter origin assertion. All permission
nodes pass outside the sandbox. There is no lane-only deterministic failure.

## Browser evidence retention

All ten product files covered by the controlled browser matrix are
byte-identical from `d87d5d65` through reconciled head `aeb0a12e`. The retained
evidence contains all four scenarios in English and `es-419`, before and after,
on the Guest `/chat` shell. It has 16 non-empty `1440x1000` PNGs, Guest and
`/me` assertions, and zero console or page errors.

## Live diagnostic

The corrected pre-reconciliation command used explicit `live_provider` mode
outside the sandbox. Local scorecard
`argus-eval-scorecard-20260812T182943Z.json` has SHA-256
`d1987e80c3b425e0a80684b6244c7aeb46141daebb02f86eb0d27d0ee16142d5`
and totals `33 passed / 13 failed` across 46 cases. The failures are old
asset-edit, discovery, options, and prose-judge families, not the deterministic
issue #453 cases. It remains a red diagnostic, not a waiver or acceptance
artifact.

The exact-head rerun needs explicit permission for paid provider traffic from
the protected environment file. Until that authority is granted, the branch
may be published and reviewed but must not be called READY.

## Scope and safety

- No `render.yaml`, `.env.example`, `.github/argus-env.sh`, release profile,
  `.env`, or `web/.env.local` change.
- No stash.
- No language-specific parser or gate.
- No API schema, database schema, release configuration, paid Render workflow,
  merge into integration, or deploy.
- Research PR #471 remains open. Its Research Responses hunk is not copied;
  the existing research tail hash remains unchanged.
