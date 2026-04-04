---
description: Conventional commits, branch naming, PR process.
---

# Git Workflow Rule

## Branch Naming
`<type>/issue-<num>-<short-desc>` — e.g., `feat/issue-42-backtest-api`

Types: `feat`, `fix`, `refactor`, `chore`, `docs`, `strip`

## Commit Messages
```
<type>: <concise description> (#<issue>)

- Detail 1
- Detail 2
```

### Types
| Type | When |
|------|------|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code restructure (no behavior change) |
| `chore` | Build, CI, tooling |
| `docs` | Documentation only |
| `perf` | Performance improvement |
| `test` | Adding/fixing tests |

## PR Process
1. Pass `/verify` before opening PR.
2. Reference issue number in PR title and body.
3. One logical change per PR — avoid mega-PRs.
4. Squash merge to main.

See: `.agent/workflows/pr.md` for full PR workflow.
