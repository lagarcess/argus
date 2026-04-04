---
description: Translates Google Stitch UI/UX JSON exports into functional frontend components aligned with Pydantic schemas.
---

**Context**: This workflow is executed by the **UI/UX Prototyper** persona. It bridges the gap between raw UI designs (e.g. from v0, Google Stitch, or Figma exports) and the strictly-typed Backend Pydantic models handling the algorithmic logic.

1.  **Input Parsing**
    - Load the raw frontend code snippets or JSON design tokens provided by the user.
    - Review `docs/designs/rfc-design.md` to understand the Backend Pydantic data schemas that the UI must consume.

2.  **Frontend Translation**
    - **State**: Build Zustand/Redux stores or React Contexts that perfectly map to the Python API responses. Ensure strict typing (TypeScript interfaces matching Pydantic).
    - **Components**: Translate the raw UI into modular React/Next.js (or equivalent) components.
    - **Mocking**: Generate mock data payloads that mirror the actual trading pipeline (e.g., SignalStatus, TakeProfit levels).

3.  **Review & Assembly**
    - Present the generated UI logic to the Staff Engineer for review.
    - Integrate the pieces into the `frontend/` directory structure.
    - Note: This workflow assumes a decoupled Frontend/Backend repository architecture.
