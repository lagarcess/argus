---
description: AI Code Review (Staff Engineer Persona) + Hygiene Pass
---

0. **Context Gathering:**
   - Read `@knowledge_base.md` for project-specific standards, architecture, and style guidelines.
   - If not provided, ask for the GitHub issue number and PR number.
       - gh pr checkout <PR_NUMBER> and ensure you are in the correct branch for the given PR and that the branch it's up to date.
       - Then run `& "C:\Program Files\Git\bin\bash.exe" ./scripts/github/get_issue_details.sh <ISSUE_NUMBER>` and `& "C:\Program Files\Git\bin\bash.exe" ./scripts/github/get_pr_comments.sh <PR_NUMBER>` to fetch and understand details from the output files.
       - Verify full understanding of the problem, suggested solution and acceptance criteria: Ask clarifying questions if ambiguities exist (e.g., "Do you fully understand the question? What are the formal requirements and output format?").
   - Gather environment details: Recent changes (git log), dependencies, and any AI-generation history (e.g., check for AI markers in code/comments).

1. **Diff Analysis & Automated Cleanup**
   - Capture changes: Run `git diff main...HEAD` and save to `temp/review/diff.txt`.
   - Compare against `temp/plan/implementation-plan.md` (if exists) to ensure alignment with intended solution.
   - **Hygiene Pass (Pre-Review)**:
     - Scan for and remove dead code, resolved TODOs, and AI reasoning markers (e.g., "I'll now...", "As an AI..."). Replace with concise engineering notes (e.g., "Optimized for readability per PEP 8").
     - Check for AI-generated artifacts: Verify no blind copy-paste; ensure code logic is explainable (e.g., add comments explaining "why" a particular approach was chosen).
     - Use temp folder for any scratch analysis (e.g., create `temp/review/cleaned-diff.py` for isolated testing).
   - **Critical Thinking Guardrail**: Manually (or via `code-debug-investigator` skill) explain key code sections in notes: "Why is this code used? What is its logic? Pros/cons vs. alternatives?"

2. **Existing PR Comments Analysis**
   - Fetch PR details (if PR exists): Description, general comments, inline code reviews via GitHub MCP.
   - Parse and categorize: Identify unresolved high-priority feedback (e.g., bugs, security), medium (e.g., performance), low (e.g., style). Flag repeated issues as signs of deeper problems (e.g., consecutive fixes in different areas indicate architectural issues—recommend rethinking).
   - **Integration with Feedback**: Cross-check against mental checklist: "Is there any misunderstanding of the solution? Missing edge cases? Do not trust prior AI reviews blindly—re-verify with evidence."

3. **Semantic Critique**
   - Analyze against "Staff Engineer" standards, incorporating a mental checklist for correctness, maintainability, and critical thinking.
   - **Readability & Understanding**: Descriptive variable names? No magic numbers (replace with constants/explanations)? Can the code be explained without AI aid? Ensure no over-reliance on AI—flag sections that seem hallucinated or unverified.
   - **Logic & Correctness**: Check for bugs, logic errors, missing error handling (e.g., runtime errors, intermittent failures). Use `code-debug-investigator` skill for reproduction (MRE, hypotheses, root cause). Verify with tests: Run existing pytest suite; suggest additions via `pytest-test-writer` if coverage gaps (e.g., edge cases, invalid inputs).
     - Mental Checklist: "Is it solving the correct problem? Correctly? Any issues/misunderstandings? Missing edge cases (e.g., 'it worked before' dilemmas—use git bisect)? Fully understand the question?"
     - Handle Specifics: For intermittent failures, add loguru logging; for runtime errors, trace to original trigger (no superficial fixes).
   - **Complexity**: Flag nested loops >3 levels or functions >50 lines; suggest refactors for maintainability (articulate pros/cons of alternatives).
   - **Architecture**: No logic leaks between layers? Domain free of IO? Check race conditions (e.g., multi-threading guidelines).
   - **Performance**: Evaluate implications (e.g., hashmap vs. linear scan for larger data); not critical for small tasks but flag if relevant.
   - **Security**: Explicit checks for injections, hardcoded secrets, or vulnerabilities (e.g., input validation); prioritize in architecture reviews.
   - **Maintainability**: Prioritize over quick fixes; ensure solution is better than alternatives (explain why). Suggest preventive measures (e.g., tests to catch future bugs).
   - *Constraints*: Ignore simple styling (handled by pre-commit hooks in `/verify`). Do NOT fully trust AI tools—make final judgment calls with evidence. Avoid shotgun fixes; stop patching if architectural issues emerge (document and recommend rethink).
   - **Anti-Patterns (Inversions)**: Detect over-reliance on AI (e.g., unresolved merge conflicts from blind AI use); flag as "mess" and require manual verification.

4. **Report Generation & Fix**
   - Generate "Review Report" in `temp/review/review-report.md` using the following standardized Markdown template for consistency. Populate it based on findings from previous steps.
     ```markdown
     # Code Review Report

     ## Summary
     - **Change Purpose**: [Brief description of the code change, e.g., "Implements feature X from GitHub issue #123."]
     - **Overall Assessment**: [e.g., "Approve with minor changes" or "Needs major revisions."]
     - **Strengths**: [Bullet list of positives, e.g., "- Strong error handling in core logic."]
     - **Key Issues**: [High-level overview, e.g., "Critical security vulnerability found; performance concerns in loop."]

     ## Checklist Results
     - **Solves Correct Problem?**: [Yes/No/Partial, with explanation.]
     - **Solved Correctly?**: [Yes/No/Partial, with evidence from tests.]
     - **Misunderstandings/Issues?**: [List any, e.g., "Missed edge case for empty input."]
     - **Missing Edge Cases?**: [List, e.g., "No test for intermittent failures."]
     - **Full Question Understanding?**: [Yes/No, with notes.]
     - **Performance Considerations?**: [Evaluation, e.g., "O(n^2) acceptable for small n."]
     - **Security Considerations?**: [Evaluation, e.g., "Input validation missing."]
     - **Maintainability?**: [Pros/cons of approach vs. alternatives.]

     ## Findings
     ### Critical (Bugs/Security - Must Fix)
     - [Issue 1]: [Description, code snippet, explanation, proposed fix.]
     - [Etc.]

     ### Major (Performance/Architecture)
     - [Issue 1]: [Description, code snippet, explanation, proposed fix.]
     - [Etc.]

     ### Minor (Readability/Maintainability)
     - [Issue 1]: [Description, code snippet, explanation, proposed fix.]
     - [Etc.]

     ## Recommendations
     - [Numbered list, e.g., "1. Add pytest for edge case X using pytest-test-writer skill."]
     - [Include preventive suggestions, e.g., "Refactor module if architectural issues persist."]

     ## Verification Steps
     - [Steps to confirm, e.g., "Re-run pytest suite; reproduce issue in temp env."]
     ```
5. Iterative Improvement
   - Present the report to the user (e.g., display contents or link to file).
   - STOP and ask: "Do you want me to apply these suggestions?"
   - If YES:
     - Apply the fixes.
      - **Fix Handling**:
      - For critical issues (e.g., bugs, security vulnerabilities): Use `code-debug-investigator` skill to perform root-cause analysis (reproduce, hypothesize, isolate, verify). Then, invoke `.agent/workflows/fix.md` workflow to propose, apply, and verify minimal fixes (e.g., trace to original trigger, ensure no regressions).
      - For major/medium issues (e.g., performance, architecture): Use `code-debug-investigator` for investigation if needed; propose fixes via `.agent/workflows/fix.md` and ask user approval before applying.
      - For minor/subjective suggestions (e.g., refactors): Document in report; ask user approval. Always verify fixes post-application: Re-run tests, check regressions using pytest.
      - **Guardrails**: No fixes without full investigation (via debug skill). If fixes reveal deeper issues (e.g., consecutive problems), halt and recommend architecture rethink. Emphasize critical thinking—"Think for yourself; do not blindly trust AI." Use temp folder for isolated fix testing.
     - Run `/verify` to ensure no regression.
   - If NO:
     - Exit workflow.
