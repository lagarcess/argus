# AI Flywheel: The Triple-Agent Synergy

This project utilizes a high-velocity "flywheel" powered by three distinct AI entities: **Antigravity (IDE)**, **Gemini Code Assist (Reviewer)**, and **Jules (Autonomous Agent)**. This document outlines how they synchronize to maintain world-class engineering standards.

## 🔄 The Perfect Sync Model

Synchronization is driven by the **Repository-as-Source-of-Truth**. All tools share a common context derived from the following files:

| Tool | Role | Primary Context Sources |
| :--- | :--- | :--- |
| **Antigravity** | Human-Agent Interface | `temp/plan/implementation-plan.md` |
| **Jules** | Headless Execution Agent | `AGENTS.md`, `knowledge-base.md` |
| **Gemini** | Automated PR Reviewer | `gemini-reviewer-context.md` |

### Synchronization Lifecycle Triggers

1.  **`/plan` (IDE)**: Jules and Antigravity read the `knowledge-base.md` to ensure the new plan doesn't repeat past architectural mistakes.
2.  **`/verify` (Agent)**: Jules runs the full test suite and checks for environment isolation, JIT warmup, and **Local CD Pre-Flight (Docker)**.
3.  **`/preflight` (Utility)**: Runs container parity and GCP connectivity checks to catch 90% of deployment failures locally.
4.  **PR Creation (Reviewer)**: Gemini Code Assist triggers. It validates the code against the "Staff Engineer" standards and checks for CI/CD compatibility.
5.  **`/learn` (Sync Momemnt)**: **Atomic Update**. Jules runs `/learn` post-merge to update the `knowledge-base.md`. No PR is considered complete without this step.

---

## 🛠 Self-Healing & Forensic Loop

The flywheel includes an autonomous self-healing and forensic mechanism:

1.  **Test Failure**: If `/verify` fails, it automatically triggers Jules to run `/fix`.
2.  **CI/CD Failure**: If `deploy.yml` fails, Jules runs **`/diagnose`** to pull GH logs and categorize the failure.
3.  **Autonomous Fix**: Jules patches the code/config and re-runs `/verify` and `/preflight`.
4.  **Lesson Extraction**: After a successful fix or rollback, Jules runs `/learn` to extract the technical "gotcha" into the `knowledge-base.md`.
4.  **Mirroring**: If a safety rule changes, it must be updated in `AGENTS.md` (for Jules) AND `gemini-reviewer-context.md` (for Gemini).

---

## ⚡ Never-Violate Standards

To prevent "hallucination drift", we enforce these hard constraints:

- **Atomic Knowledge**: The `knowledge-base.md` is the only long-term memory.
- **Environment Parity**: `jules-setup.sh` ensures the VM matches the IDE environment exactly.
- **Two-Phase Commit**: Idempotency is enforced by persisting state BEFORE notifications.
- **TDD First**: Bug fixes must start with a failing test case in Jules's VM.

---

## 📚 Documentation Parity Protocol

To ensure the root `README.md` and the detailed `./docs` wiki remain synchronized, we use an **Expansion/Contraction** model:

1.  **Expansion (Root -> Wiki)**: Changes to core project features in the root `README.md` must be expanded into detailed architectural guides in `./docs`.
2.  **Contraction (Wiki -> Root)**: New detailed guides in `./docs` must have their key takeaways or links added to the root files.
3.  **The Anchor**: The `/learn` command extracts lessons from code fixes. These lessons must be used by Jules to update **both** the `knowledge-base.md` and the relevant root/wiki files.
4.  **Verification**: The `/verify` workflow includes a `scripts/verify_doc_parity.py` check to catch broken links and cross-reference gaps between the root and `./docs`.

---

## 🔗 The "Staff Engineer" Anchor

The `gemini-reviewer-context.md` acts as the quality anchor. If you find a new design pattern or safety gap, update that file immediately. This ensures the automated reviewer stays as sharp as the human leads.
