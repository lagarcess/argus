---
description: Semantic Versioning and Git Conventions (Model Decision - Trigger when creating branches, proposing PRs, or writing commit messages)
---

# Conventional Commits & Git Rules

You must strictly enforce Conventional Commits and semantic branch naming across the repository. This is critical for automated CI/CD pipelines, release notes generation, and git history readability.

## 1. Branch Naming Convention
Branches must instantly communicate intent and trace back to an issue (if applicable).
- **Format**: `<type>/<issue-number>-<short-description>`
- **Types**:
  - `feat/`: New features (causes a MINOR version bump).
  - `fix/`: Bug fixes (causes a PATCH version bump).
  - `chore/`: Maintenance, dependency updates, tooling.
  - `refactor/`: Code reorganization without changing logic.
  - `docs/`: Documentation updates only.
  - `perf/`: Performance improvements.
  - `test/`: Adding or fixing tests.
- **Examples**:
  - `feat/102-add-alpaca-retry`
  - `fix/99-zombie-position-race-condition`

## 2. Commit Message Structure
Every commit message must follow the Conventional Commits 1.0.0 specification.
- **Format**:
  ```text
  <type>(<optional scope>): <description>

  [optional body]

  [optional footer(s)]
  ```
- **Rules**:
  - **Type**: Must be one of `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
  - **Scope**: (Optional) Enclosed in parentheses, describing the section of the codebase (e.g., `feat(engine): ...`).
  - **Description**: Short summary, imperative present tense ("add", not "added" or "adds"). No capitalization at the start, no period at the end.
  - **Breaking Changes**: If a commit introduces a breaking change, it MUST contain `BREAKING CHANGE:` in the footer or an exclamation mark after the type/scope (e.g., `feat(api)!: drop legacy endpoint`).

## 3. Pull Request Alignment
When generating a PR via the `/pr` workflow:
- The PR Title MUST match the Conventional Commit format (it will become the squash-merge commit message).
- The PR Label must match the semantic type.
