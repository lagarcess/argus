---
description: The Backend Architect and DRE draft a system architecture `docs/designs/rfc-design.md` for approval.
---

**Context**: This workflow is executed by the **Backend Architect** and **Database Reliability Engineer (DRE)**. It takes the Product Owner's `docs/designs/requirements.md` and translates it into technical schemas, database queries, and system interactions.

1.  **Input Parsing**
    - Read `docs/designs/requirements.md`. If it does not exist, halt and ask the user to run `/kickoff` first.

2.  **Architectural Drafting**
    - **Data Layer**: Define Pydantic models. What new fields are required in Firestore? What composite indexes do we need?
    - **Logic Layer**: Define the event flow. Avoid direct I/O inside the domain layer.
    - **Observability**: What metrics need to be added to `MetricsCollector`?

3.  **Documentation**
    - Create or update `docs/designs/rfc-design.md`. Ensure this is saved to the persistent `docs/` folder so Jules and other agents can reference it.
    - Format:
      ```markdown
      # Request for Comment (RFC): [Feature]
      ## 1. Context & Scope
      ## 2. API / Schema Changes
      ## 3. Infrastructure Impact (Firestore Read/Writes, Memory)
      ## 4. Implementation Steps
      ```

4.  **Approval Handoff**
    - Present the RFC to the human Staff Engineer.
    - Ask: "Do you approve this design? Once approved, we can proceed to `/plan` or delegate to Jules."
