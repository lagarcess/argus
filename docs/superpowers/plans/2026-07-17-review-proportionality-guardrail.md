# Review Proportionality Guardrail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one canonical repository instruction that keeps finding-driven fixes proportional without weakening confirmed high-impact requirements.

**Architecture:** Root `AGENTS.md` remains the only operative source for this policy. The existing design note records the rationale; review skills and agents inherit the rule by reading repository instructions, so no skill or runtime file changes are needed.

**Tech Stack:** Markdown, ripgrep, Git

## Global Constraints

- Change documentation only; do not modify product runtime, API, frontend, database, or deployment behavior.
- Keep the operative rule in root `AGENTS.md`; do not duplicate it in a global or project skill.
- Do not create a numeric severity threshold or a new release gate.
- Never waive a confirmed correctness, security, privacy, evidence-integrity, or durable-state requirement merely because its safe fix is difficult.
- Prefer the smallest safe lane-local fix and escalate when that fix exceeds the lane.

---

### Task 1: Add the Canonical Review-Proportionality Rule

**Files:**
- Modify: `AGENTS.md` under `Integration guardrails`
- Reference: `docs/superpowers/specs/2026-07-17-review-proportionality-guardrail-design.md`
- Verify: repository instruction and skill text with `rg` and `git diff --check`

**Interfaces:**
- Consumes: the approved guardrail contract in the design note
- Produces: one operative `AGENTS.md` instruction inherited by local, cloud, subagent, acceptance, and pre-merge review work

- [ ] **Step 1: Confirm the insertion point and absence of an operative duplicate**

Run:

```bash
sed -n '138,158p' AGENTS.md
rg -n "review proportionality|proportionality check|disproportionate scope" \
  AGENTS.md .agent/skills \
  /Users/garces/.codex/skills/argus-review-contract/SKILL.md
```

Expected: the insertion point follows the worker-diff review rule; no existing operative proportionality rule is found.

- [ ] **Step 2: Add the exact canonical instruction**

Insert immediately after the rule requiring Codex review of worker diffs:

```markdown
- Apply review proportionality to local, cloud, subagent, acceptance, and
  pre-merge review. Before changing code, confirm that the finding is real,
  reachable, and relevant to the active lane; weigh its severity, likelihood,
  affected users or artifacts, and risk to correctness, security, privacy,
  evidence integrity, or durable state against the complexity the fix adds.
  Choose the smallest safe fix. After implementation, reassess the actual diff
  and remove or simplify machinery the validated finding does not justify.
  Discard speculative or disproportionate scope, and revisit only risk surfaces
  materially changed by the latest fix; unchanged code must not become a new
  source of requirements merely to continue a review loop. If the smallest safe
  fix for a confirmed correctness, security, privacy, evidence-integrity, or
  durable-state requirement exceeds the lane, escalate instead of weakening or
  waiving the requirement because the fix is difficult.
```

- [ ] **Step 3: Verify content, uniqueness, and formatting**

Run:

```bash
rg -n "Apply review proportionality|smallest safe fix|unchanged code must not" \
  AGENTS.md .agent/skills \
  /Users/garces/.codex/skills/argus-review-contract/SKILL.md
git diff --check
```

Expected: each phrase appears only in `AGENTS.md`; `git diff --check` exits successfully with no output.

- [ ] **Step 4: Confirm the change is documentation-only and matches the approved scope**

Run:

```bash
git diff --stat
git diff -- AGENTS.md
```

Expected: only `AGENTS.md` is modified, and its diff adds the approved rule under `Integration guardrails` without changing another policy.

- [ ] **Step 5: Commit the guardrail**

Run:

```bash
git add AGENTS.md
git commit -m "docs(agents): add review proportionality guardrail"
```

Expected: one documentation commit containing only the root instruction change.
