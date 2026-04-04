---
description: Audits the repository and synchronizes all documentation (.md files, docstrings) with the current codebase state.
---

**Context**: You noticed that documentation (`docs/`, `AGENTS.md`, docstrings) can easily drift as code rapidly evolves. The `/sync-docs` workflow is the system's "immune response" against technical debt. It forces the AI to cross-reference reality against the written word.

1.  **Architecture vs. Reality Audit**
    - Read `.agent/agency_blueprint.md` and `AGENTS.md`.
    - Verify that all mentioned tools, constraints, and personas actually exist in the `.agent/` directories or `scripts/`.
    - If a feature is documented but missing, flag it as a hallucination or dead link.

2.  **Comprehensive Documentation Audit (`docs/` directory)**
    - Iterate through **all** markdown files in the `docs/` directory hierarchy (`docs/**/*.md`), including Strategy, Architecture, Operations, and Development guides.
    - Ensure cross-references between `docs/README.md`, `AGENTS.md`, and individual guides remain valid and accurately represent the current `.agent/workflows/` and `.agent/skills/`.
    - Cross-reference documented Python classes/types in `docs/designs/rfc-design.md` or `knowledge-base.md` against the actual `src/crypto_signals/` implementations.
    - If a Pydantic schema or system component has evolved, ensure the corresponding documentation in `docs/` is updated immediately.

3.  **Actionable Output**
    - **Hard Fixes**: Directly edit markdown files (`docs/**/*.md`, `AGENTS.md`, etc.) to match the code truth.
    - **Report**: Output a checklist of what was out-of-sync and what was updated.
    - "✅ Documentation and Agency Workflows are fully synchronized with the codebase."
