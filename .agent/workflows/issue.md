---
description: Diagnose, validate, and create high-quality GitHub issues
---

1. **Diagnosis & Validation**
   - **Identify the Gap**: Clearly state what is missing or broken.
   - **Forensic Check**:
     - Check `main.py` execution flow.
     - Check Pipelines (`src/crypto_signals/pipelines/`).
     - Check Schemas (`src/crypto_signals/domain/schemas.py`).
   - **Simulate/Verify**:
     - Can you reproduce it?
     - Does the code path exist?
     - Is it reachable?

2. **Draft Issue Content**
   - Create a draft file `temp/issue_draft.md`.
   - **Structure (Strict Template)**:
     ```markdown
     # [Title] (e.g., "Critical: TradeArchival Not Executing in Main Loop")

     ## Background
     [Context on why this feature/fix is needed. Connect it to Business Value (PnL, Analytics).]

     ## Problem Description
     [High-level summary of the defect or missing capability.]

     ## Impact & Importance
     **Why it matters**:
     [Explain the consequences of ignoring this. e.g. "We are flying blind."]

     **Business Impact**:
     - [ ] Impact 1 (e.g. Zero Observability)
     - [ ] Impact 2 (e.g. Broken Financials)

     ## Current Breaking Implementation
     [Show the CODE that is creating the problem.]

     ```python
     # Reference the file path
     def broken_function():
         # Show the missing call or broken logic
         pass
     ```

     ## Proposed Solution
     [High-level architecture of the fix. e.g., "Instantiate Pipeline X in main.py before Signal Generation."]

     ## Technical Details / Tasks
     - [ ] Step 1
     - [ ] Step 2

     ## Acceptance Criteria
     - [ ] Criterion 1
     - [ ] Criterion 2
     ```

3. **User Review**
   - Display the draft to the user using `view_file` or `notify_user`.
   - **STOP** and wait for approval.

4. **Submit Issue**
   - Run: `gh issue create --title "<ISSUE_TITLE>" --body-file temp/issue_draft.md --label "bug" (or "enhancement")`
   - Record the new Issue Number.

5. **Update Documentation**
   - Add the new Issue to `task.md`.
