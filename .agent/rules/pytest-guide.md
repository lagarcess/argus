# Pytest Usage Guide

This guide provides mutually exclusive, collectively exhaustive (MECE) commands and best practices for using pytest efficiently, minimizing token usage, and identifying errors quickly.

## Important Caveats & Best Practices

1. **Minimize Coverage Failures on Subsets:**
   When running a set of tests (non-full test suite), always add the `--no-cov` flag to avoid coverage failures.
2. **Output Formatting & Archiving:**
   Output files to `temp/test_results` (create the `test_results` subdirectory if it does not exist).
   *Example:* `poetry run pytest -q --tb=long > temp/test_results/pytest_debug_<ISSUE>.txt`
3. **Final Verification:**
   Run the full test suite at the end of your workflow to check for overall coverage and regressions.

## Maximizing Efficiency & Error Traceback

To effectively combine pytest commands for different scenarios:

- **Maximize Error Traceback (Deep Debugging):**
  Combine verbosity and traceback formatting to see all details and local variables.
  *Command:* `poetry run pytest -vv --showlocals --tb=long --no-cov > temp/test_results/pytest_deep_debug.txt`

- **Narrow Down to Relevant Tests (Minimizing Token Usage):**
  Run specific test files or use the `-k` flag to match test names, keeping the output quiet and truncating tracebacks to the line level.
  *Command:* `poetry run pytest tests/path/to/test.py -k "test_name" -q --tb=short --no-cov`

- **Catching Unexpected Warnings & Edge Cases:**
  Run with maximum verbosity on a specific subset, exposing local variables and capturing output.
  *Command:* `poetry run pytest -v -l -W always --capture=tee-sys --no-cov`

---

## MECE List of Pytest Output Commands

Below is a Mutually Exclusive, Collectively Exhaustive (MECE) categorization of pytest command-line options for controlling output. Categories are divided by primary function.

### 1. Verbosity Control
These options adjust the overall detail level of test output during execution.
- **`poetry run pytest -v`** (or `--verbose`)
  *Scenario:* Use when you need to see individual test names for better progress tracking in medium-sized suites.
- **`poetry run pytest -vv`**
  *Scenario:* Use for detailed debugging, especially to view full assertion differences in complex failures.
- **`poetry run pytest -vvv`**
  *Scenario:* Use in advanced setups with plugins requiring maximum output detail for custom diagnostics.
- **`poetry run pytest -q`** (or `--quiet`)
  *Scenario:* Use in CI pipelines, large test runs, or when conserving tokens, where minimal output reduces log noise.

### 2. Local Variables Display
These control whether local variable states are shown in failure tracebacks.
- **`poetry run pytest --showlocals`** (or `-l`)
  *Scenario:* Use during debugging to inspect variable values at failure points for quicker root-cause analysis.
- **`poetry run pytest --no-showlocals`**
  *Scenario:* Use to simplify tracebacks when variable details add unnecessary clutter in reports.

### 3. Output Capturing
These manage how stdout/stderr from tests are captured and displayed.
- **`poetry run pytest --capture=fd`**
  *Scenario:* Use as default for standard buffering of print/log output in most test environments.
- **`poetry run pytest --capture=sys`**
  *Scenario:* Use when tests interact directly with `sys.stdout`/`stderr` for accurate stream handling.
- **`poetry run pytest --capture=no`** (or `-s`)
  *Scenario:* Use in development for real-time output, like seeing live prints during test runs.
- **`poetry run pytest --capture=tee-sys`**
  *Scenario:* Use for hybrid logging where you need both captured results and terminal output.

### 4. Traceback Formatting
These customize the style and depth of error tracebacks.
- **`poetry run pytest --tb=auto`**
  *Scenario:* Use as default for balanced traceback detail in routine testing.
- **`poetry run pytest --tb=long`**
  *Scenario:* Use when needing exhaustive context to understand deep stack failures.
- **`poetry run pytest --tb=short`**
  *Scenario:* Use for concise overviews in logs or when focusing on high-level failure locations.
- **`poetry run pytest --tb=line`**
  *Scenario:* Use in space-constrained outputs to show only failure lines.
- **`poetry run pytest --tb=native`**
  *Scenario:* Use for compatibility with standard Python error formats in mixed environments.
- **`poetry run pytest --tb=no`**
  *Scenario:* Use when suppressing tracebacks entirely, focusing only on summary failures.
- **`poetry run pytest --full-trace`**
  *Scenario:* Use to diagnose hangs or interruptions (e.g., Ctrl+C) with complete traces.

### 5. Test Summary Reporting
These control the end-of-run summary of test outcomes.
- **`poetry run pytest -r <chars>`** (or `--report <chars>`, e.g., `-ra` for all except passed)
  *Scenario:* Use in large suites to highlight specific outcomes like failures, skips, or xfails for quick review.

### 6. External Reporting
These export output for integration with other tools or sharing.
- **`poetry run pytest --junit-xml=<path>`** (e.g., `--junit-xml=results.xml`)
  *Scenario:* Use for CI/CD integration, like with Jenkins, to generate machine-readable test reports.
- **`poetry run pytest --pastebin=<failed|all>`**
  *Scenario:* Use to share detailed failure logs externally via a URL for collaboration.

### 7. Miscellaneous Output Controls
These handle niche output behaviors not covered elsewhere.
- **`poetry run pytest --no-fold-skipped`**
  *Scenario:* Use when individual skip reasons are important, preventing grouping in summaries.
