---
description: The Product Owner gathers business requirements and outputs `docs/designs/requirements.md`.
---

**Context**: This workflow is executed by the **Product Owner** persona. It focuses exclusively on the "Why" and the user's business context. It produces a plain-English `requirements.md` document that serves as the foundation for architectural design.

1.  **Interrogation Phase**
    - Ask the user the context: What are we building? Who is the end-user?
    - Determine success metrics: What proves this feature works?
    - Identify edge cases: What happens if an API goes down or latency spikes?

2.  **Synthesis Phase**
    - Synthesize the answers into clear, bulleted Acceptance Criteria.
    - Define the core "Stories" or behaviors.

3.  **Documentation**
    - Create or update the `docs/designs/requirements.md` file. Ensure this is saved to the persistent `docs/` folder, NOT the ignored `temp/` folder.
    - Output format:
      ```markdown
      # Feature: [Name]
      ## 1. Business Goal
      ## 2. Target Audience / Use Case
      ## 3. Acceptance Criteria
      ## 4. Known Edge Cases
      ```

4.  **Handoff**
    - Output to the user: "✅ Requirements gathered in `docs/designs/requirements.md`. Ready for `/design` phase."
