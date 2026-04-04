# Project Agents & Tools: Crypto Sentinel

This file serves as the **AI Team Registry**. It dictates how AI agents (like Jules or the Antigravity assistant) must behave, what skills they possess, and what workflows they can execute.

If you are an AI reading this, you are part of a strict, production-grade engineering team. You must adhere to the Global Rules and activate the appropriate Expert Skills when working in specific domains.

---

## 🛡️ 1. Global & Workspace Rules (`.agent/rules/`)

These rules are machine-enforceable constraints. You must follow them implicitly.

| Rule | Trigger | Purpose |
| :--- | :--- | :--- |
| `architecture.md` | Model Decision | Enforces strict boundaries (Zero IO in Domain, Market parses to Domain, Engine orchestrates). |
| `data-integrity.md` | Model Decision | Enforces **Two-Phase Commit** (Firestore before Discord). Prevents overriding `ENVIRONMENT=PROD`. |
| `coding-standards.md` | Model Decision | Enforces `loguru` (never `print`), 100% type hinting, 90 char limits, and Pydantic validation. |
| `numba-jit.md` | Glob (`analysis/**/*.py`) | Enforces pure math inside JIT, requires `warmup_jit()` calls. |
| `testing-tdd.md` | Glob (`tests/**/*.py`) | Enforces creating *new* test files for refactored classes. Mandates `polyfactory` mock generation. |

---

## 🧠 2. AI Expert Skills (`.agent/skills/`)

Skills are specialized instruction sets. If your current task touches one of these domains, you **must** read the corresponding `SKILL.md` file before generating code.

| Skill | Expert Persona | When to Use |
| :--- | :--- | :--- |
| `signal-state-machine` | Trading Execution Specialist | Modifying `engine/signal_generator.py` or editing signal state lifecycles. Prevents Phantom TP3 jumps. |
| `alpaca-integration` | Brokerage Infra Engineer | Modifying `market/` wrappers or execution API calls. Teaches 404 defensive parsing and rate limit handling. |
| `math-io-separation` | Quant Systems Architect | Refactoring monoliths. Teaches how to decouple Pandas/NumPy from external I/O for easy testing. |
| `firestore-mutations` | Database Reliability Engineer | Modifying `repository/`. Teaches atomic batches, composite indexes, and preventing zombie positions. |
| `schema-migration` | Data Platform Engineer | Editing Pydantic schemas in `domain/`. Teaches backwards compat and BQ pipeline sync requirements. |

---

## ⚙️ 3. Standard Workflows (Slash Commands)

Workflows are automated scripts outlining step-by-step processes. Execute them via `/workflow-name` or by reading the `.agent/workflows/` directory.

### Orchestration & Design (The Master Hand-offs)
- `/kickoff`: The Product Owner gathers business requirements and outputs `docs/designs/requirements.md`.
- `/design`: The Backend Architect and DRE draft a system architecture `docs/designs/rfc-design.md` for your approval.
- `/proto-sync`: Translates Google Stitch UI/UX JSON exports into functional frontend components aligned with Pydantic schemas.

### Core Development Loop
- `/plan`: Generates `temp/plan/implementation-plan.md`. Always start here.
- `/implement`: Enters the Red-Green-Refactor loop, creates branch, writes test.
- `/fix`: The universal TDD inner-loop. Reads a failing test, fixes code, loops 3 times.

### Validation & CI/CD
- `/verify`: Runs the full suite, coverage regression check, type checking, and pre-commit hooks.
- /preflight: Local Docker + GCP check (FLAGGED AS BROKEN - run manually for now).
- `/architect`: Analyzes massive monoliths (e.g. `main.py`) to draft an extraction plan without touching code.
- `/perf`: Benchmarks Numba JIT logic and backtest paths to catch latency spikes.

### Data & Architecture
- `/migrate`: Validates Firestore schemas and BigQuery parity, then commits changes.
- `/diagnose`: Infrastructure health check (GCP, Firestore, Alpaca) and Book Balancing Audit (Reverse Orphans/Zombies).

### Review & Learning
- `/sync`: Resolve upstream conflicts, rebase, and verify infrastructure integrity before PR review.
- `/sync-docs`: Audits the repository and synchronizes all documentation (.md files, docstrings) with the current codebase state.
- `/pr`: Creates a comprehensive Pull Request from current changes, formatting, and checking for secrets.
- `/review`: AI Code Review (Staff Engineer Persona) + Automated Code Hygiene pass.
- `/review-jules`: Manager-level review for delegations to the Jules Agent.
- `/learn`: **Critical**. Extracts engineering lessons for future reference and commits to knowledge base. Run after every major change.
- `/cleanup_branch`: Post-merge cleanup workflow. Delete local branches, prune remote, and refresh dependencies.

---

## 🤝 4. Team Delegation Strategy

As the solo Staff Engineer, you orchestrate this AI Agency using three primary tools: **Antigravity**, **GitHub**, and **Jules**.

**Note on MCP**: GitHub's native integrations are extremely powerful for asynchronous agentic tracking. For a solo project, GitHub Issues is sufficient to manage the AI Agency. You only need to scale to Linear if sprint planning and cross-functional ticketing become overwhelming.

### Antigravity (The Staff Copilot)
*Role*: High-level reasoning, system architecture, complex refactoring, and orchestration.
- Use for `/kickoff`, `/design`, and `/architect` workflows.
- Use for deep systemic bugs requiring `/diagnose`.
- Use to maintain `agency_blueprint.md` and `AGENTS.md`.

### GitHub Issues (The Workflow Contract)
*Role*: The central source of truth for work tracking.
- **When to Create an Issue (`/issue`)**:
  - Any task exceeding 1 hour of work or touching >2 modules.
  - Epics that emerge from a `/kickoff` session.
  - Vague bugs that require isolated investigation before coding.
- *Why*: It forces you to define strict **acceptance criteria** before an AI writes code, preventing hallucinations and scope creep.

### Jules (The Execution Engine)
*Role*: The junior-to-mid level engineer executing well-defined tickets.
- **When to Delegate (Add `jules` tag to a GitHub Issue)**:
  - Repetitive, isolated tasks (e.g., "Add a new endpoint for X that matches schema Y").
  - Test coverage expansion (e.g., "Write unit tests for `analysis/indicators.py`").
  - Boilerplate generation based on an approved `docs/designs/rfc-design.md` from Antigravity.
- **VM Setup (`scripts/jules-setup.sh`)**: Jules should run this script to correctly initialize its workspace (dependencies, safe environment variables, JIT warmup) before executing tasks.
- *Why*: Jules excels at asynchronous, scoped task execution. Jules writes the PR, and you (with Antigravity's help) review it via the `/review-jules` workflow.

---

## 🛑 Never-Violate Standards

1. **Environment Isolation**: Never override `ENVIRONMENT=PROD` in automated scripts. Use `DEV` for fixes.
2. **Two-Phase Commit**: Always persist a signal or state to Firestore *before* sending a Discord notification.
3. **Structured Logging**: Use `loguru` with context (`signal_id`, `symbol`). No standard `print` statements.
4. **TDD First**: Generate a failing unit test for bugs before writing the fix.
5. **JIT Warmup**: Any changes to `src/crypto_signals/analysis/` require a `warmup_jit()` call to prevent latency spikes in production.
