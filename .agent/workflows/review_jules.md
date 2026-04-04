---
description: Manager-level review and prompt generation for Jules (Intern Persona)
---

**Context**: Use this workflow when reviewing PRs submitted by **Jules** via Google Labs. Since Jules does not respond to automated GitHub bot comments, this workflow analyzes the PR and generates a highly-optimized text prompt for you to copy-paste into the Jules Web UI.

1.  **Gather the Context (via GitHub MCP)**
    - **Fetch Diff**: Use your available tools or MCP to fetch the diff for the PR branch against `main`.
    - **Fetch PR Comments**: Use the GitHub MCP server to retrieve existing PR review threads and comments that Jules needs to address.

2.  **Generate Review Strategy (The "Staff Engineer")**
    - Act as the senior architect reviewing an intern's work.
    - Check against `agency_blueprint.md` or the `docs/designs/rfc-design.md` contract.
    - Identify logic errors, hardcoded values, missing edge cases, or leaked I/O in the Domain layer.

3.  **Draft the Jules UI Prompt**
    - Create a text artifact at `temp/review/prompt_for_jules.md`.
    - Format this to be highly instructional, grouping identical file changes together.
    - **Prompt Format**:
      ```markdown
      Hey Jules, I've reviewed your recent PR. Here are the corrections I need you to implement:

      **1. src/crypto_signals/domain/schemas.py**
      - Line 45: You hardcoded the timeout. Please extract this to `config.py` as `DEFAULT_TIMEOUT`.
      - Missing Validation: Add a Pydantic `@field_validator` to ensure `price > 0`.

      **2. External PR Comments**
      - [Synthesize and list the feedback pulled from GitHub MCP here].

      Please make these changes, run the `pytest` suite locally, and push the updates to the branch.
      ```

4.  **Handoff to Human**
    - Display the prompt to the user in the Antigravity chat.
    - Instruct the user: "Review the prompt above. If it looks good, copy and paste it directly into the Jules Web UI to trigger the fixes."
