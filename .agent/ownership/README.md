# Branch Ownership Gate

This folder defines hard ownership boundaries for parallel branch work.

## Policy Source
- Manifest: `.agent/ownership/branch_ownership.json`
- Verifier: `.agent/scripts/ownership/verify_branch_ownership.py`

## Local Usage
Run on the active branch:

```bash
python .agent/scripts/ownership/verify_branch_ownership.py
```

Optional explicit branch:

```bash
python .agent/scripts/ownership/verify_branch_ownership.py --branch codex/section-3-backtest-engine
```

Optional explicit files (for dry checks):

```bash
python .agent/scripts/ownership/verify_branch_ownership.py --branch codex/section-4-persistence-model --files src/argus/api/main.py
```

## Enforcement Behavior
- Branches with a policy are enforced against both allowlist and denylist.
- Any changed file outside allowlist fails the gate.
- Any changed file matching denylist fails the gate.
- Branches without a policy are skipped.
