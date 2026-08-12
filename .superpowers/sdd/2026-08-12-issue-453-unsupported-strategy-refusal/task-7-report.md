# Task 7 report: terminal deterministic verification

## Outcome

Issue #453 has no lane-only deterministic failure at exact source and test SHA
`4321f1999e8b3d870428cc90c83419d977db6adc`. Full backend coverage is `87%`,
all 1,475 web tests pass, lint and production build pass, locale and modularity
gates pass, and the free mocked interpreter evaluation passes.

The repository still has three explicitly classified baseline surfaces:
repository-wide Ruff format debt, the existing TypeScript test-type debt, and
one OpenRouter error-origin assertion. Sandbox-only process and loopback
failures pass outside the sandbox.

## Reconciliation provenance

- Historical integration base:
  `8025672924d1c74eb80cc926c72b5d8574b613d7`
- Current fetched integration and comparison base:
  `c3a9aca181ea43770a81c13ec2fb5f02f85af293`
- One-way merge commit:
  `b585d429fee633751d5aa19b6668db79165944f9`
- Browser-reviewed product source:
  `d87d5d6524e0af89d99dab26cc3e4b6f56c24742`
- Terminal command execution head:
  `4321f1999e8b3d870428cc90c83419d977db6adc`
- Evidence commit: the later documentation-only commit that contains this
  report; it is not part of the source SHA it documents.

Intervening integration work was semantically independent of issue #453. It
changed runbook and roadmap material, Auth template evidence, backtest math
audit/tests, and a Render cron test, with no shared issue runtime owner, API
clarification section, UI-state owner, locale, or focused test.

## Exact results

### Repository and backend

- Python: `3.10.20`, PASS.
- Ownership policy: PASS, branch has no applicable policy.
- Ruff check: PASS.
- Ruff format check: RED, `142` files would reformat versus `144` at exact
  current integration. This is baseline-wide debt; no formatting was changed.
- Full backend in the sandbox: `5050 passed, 495 skipped, 7 failed` in
  `107.58s`, configured `TOTAL` coverage `87%`.
- Outside-sandbox permission-sensitive subset: `8 passed in 4.39s`.
- Exact integration OpenRouter comparison: the same single origin assertion
  fails with the same `<unknown>` result.
- Modularity script: PASS, no violations.
- Modularity budget suite: `8 passed`.
- Locale parity: `4 passed`.
- Free mocked interpreter evaluation: `72 passed`.
- Live eval: intentionally not run; it remains controller-owned.

The six sandbox failures were one process-inspection node and five canary nodes
that reached a loopback bind. Running the full canary module plus the process
node outside the sandbox proved all eight affected nodes green.

### Web

- `bun run test`: `1475` passed, `0` failed across `145` files.
- `bun run lint`: PASS with `0` errors and `8` existing warnings.
- `bun x tsc --noEmit`: baseline-family RED with `6017` diagnostics versus
  `6016` on current integration.
- Sandbox build: local-port bind `EPERM` after `166.04s`.
- Outside-sandbox build: PASS in `5.86s`.

The TypeScript lane delta is exactly two `TS2349` instances in the already-red
legacy `web/__tests__/chat-recovery-display.test.ts`: line `404:16` for
`expect(es).toContain("esa regla")` and line `410:16` for
`expect(en).toContain("that rule")`. They match the file's existing Bun
assertion union-type family, whose count changes from `80` to `82`. The new
focused issue file has zero diagnostics. Exact integration also contributes a
separate read-only-worktree `TS5033`, so the aggregate difference is one.

## Integrity and retained evidence

- Forbidden release and environment surfaces are unchanged from historical
  base.
- No tracked non-example `.env` path was found, and no secret value was read or
  printed.
- `git diff --check` passed and the read-only verification left a clean tree.
- The API contract research section hash matches historical base exactly.
- All ten browser-evidenced product files are byte-identical from
  `d87d5d6524e0af89d99dab26cc3e4b6f56c24742` through the terminal source SHA.
- The controlled-browser manifest and eight after receipts remain consistent:
  controlled/provider-free evidence, zero browser errors, eight non-empty
  `1440x1000` screenshots, and the reviewed product SHA on every record.

The accepted bilingual browser evidence is therefore retained. It remains
controlled evidence and does not claim a live hosted provider replay.

## Disposition

Task 7 deterministic verification is complete with no lane-only blocker. The
remaining reds are current-integration debt or sandbox restrictions, fully
classified above. Sanctioned live evaluation, CI, review-thread closure, and
promotion remain separate controller-owned gates.
