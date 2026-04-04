---
description: comprehensive planning phase for new tasks or github issues
---

1. **Context Gathering**
   - ask the user for the specific GitHub Issue number or Task description.
   - ensure directory exists: Use `if (!(Test-Path "temp/issues")) { New-Item -ItemType Directory -Path "temp/issues" }`
   - **Fetch Issue Details**: Use `(gh issue view <number> --json title,body,labels | ConvertFrom-Json) | ForEach-Object { "$($_.title) (Labels: $(($_.labels.name) -join ', '))`n`n$($_.body)" } | Out-File -FilePath "temp/issues/issue-<number>.txt" -Encoding utf8` to get the full title, body, and labels. Do NOT rely on truncated summaries.
   - read `README.md`, `DEPLOYMENT.md` and `SECURITY.md` to ensure alignment with system constraints.
   - search for any existing "Idea" files or `TODO.md` that might be relevant.

2. **Forensic Analysis (For Bug Fixes)**
   - If the task is a bug fix/issue, perform a cross-reference check:
     - Check **GCP Cloud Run Logs** for stack traces.
     - Check **Firestore/BigQuery** for data inconsistencies.
     - Check **Discord Notifications** for alert mismatches.
     - Check **Alpaca** for trade execution gaps.
   - Validate that the issue actually exists and reproduce it if possible.

3. **Architectural Analysis**
   - analyze the current system architecture by listing relevant directories in `src/`.
   - identify potential scalability bottlenecks or reliability risks for the proposed feature.
   - verify that the solution fits the "most optimal" architectural pattern (e.g., proper separation of concerns in `domain/`, `repository/`, `engine/`).

3. **Draft Implementation Plan**
   - create or update `temp/plan/implementation-plan.md`.
   - the plan MUST include:
     - **Goal**: Clear statement of what we are solving.
     - **Proposed Changes**: Specific files to create or modify.
     - **Verification Strategy**: How we will test this (unit tests, integration tests).
     - **Risk Assessment**: Potential side effects on the wider system.

4. **User Review**
   - present the plan to the user.
   - **STOP** and wait for explicit user approval before writing any code.
