# R-gate-ecd2bb57: delta review of PR #809 (testcase elements own the verdict)

Head: `ecd2bb5704db21f4d1ff1be3e64ce9325aa6b9c2`. Diff reviewed: `6b792ba16..ecd2bb570` (`scripts/qa/assert_pytest_gate.py`, `tests/test_assert_pytest_gate.py`). Checkout: `.claude/worktrees/cuadrao-gate`, HEAD verified. The script was run with plain `python3` (3.14.7) and with Python 3.10.20, which CI uses. All XML and test files are in the session scratchpad under `scratchpad/gate2/`. No repo files were touched, and `git status --porcelain` is clean.

## Verdict: CLEAN

All five findings from R-gate-6b792ba1 are fixed. I found no clean report from pytest 8.4.2 that the new mismatch check fails, in any configuration CI can produce. I also found no report written by pytest for a non-passing run that exits 0. There are no new findings.

## Prior findings, re-run at head

| Finding | XML (same as R-gate-6b792ba1) | Before | At head |
|---|---|---|---|
| P2-1a | attrs `failures="0"`, one `<failure>` element | rc=0 | rc=1, `failed: a::t2` + `mismatch: ... failures=0, testcase elements show 1` |
| P2-1b | no count attrs, one `<failure>` element | rc=0 | rc=1, `failed: a::t2` |
| P2-1c | `tests="7"`, one testcase | rc=0, "7 passed" | rc=1, `mismatch: ... tests=7, testcase elements show 1` |
| P2-2 | real pytest pass-then-teardown-error (`tests="2"`, 1 testcase with `<error>`) | `2 tests, 1 passed` | `1 tests, 0 passed, 0 failed, 1 errors` + mismatch line, rc=1 |
| P2-2 | one testcase holding both `<failure/>` and `<error/>` | `-1 passed` | `1 tests, 0 passed, 1 failed`, `failed, error: a::t1`, rc=1 |
| P3-1 | `<skipped type="pytest.xfail">` | labelled `skipped` | labelled `xfail`, rc=1 |
| P3-2 | counts only on the inner nested suite / only on the `<testsuites>` root | "collected zero tests" | names the failure, rc=1 |
| P3-3 | tests for the `<testsuite>` root, several suites, nested suites, teardown shapes, xfail and attribute mismatch | missing | 15 tests, all pass on py3.10 + pytest 8.4.2. ruff 0.4.10 check and format are clean |

The committed fixture `tests/fixtures/pytest_gate/real_postgres_five_failures.xml` gives rc=1 and names all 5 failed tests, with `7 tests, 2 passed`.

## The new risk: can a clean pytest report fail the mismatch check?

**How CI produces the reports:** `.github/workflows/ci.yml:258-274`. It runs serial `poetry run pytest <files> --junitxml=temp/... -q --no-cov`, then the gate. `poetry.lock` pins pytest 8.4.2, pytest-asyncio 1.4.0, pytest-cov, pytest-mock and pytest-benchmark. **pytest-xdist and pytest-rerunfailures are not in the lock**, and `pyproject.toml` has no `-n` or `--reruns` in `addopts`. No junit hook or `record_*` usage turns up in the gated test files or in conftest.

I made a scratch venv (py3.10.20) with pytest 8.4.2, pytest-asyncio 1.4.0, pytest-cov, pytest-mock and pytest-benchmark, plus pytest-xdist 3.8.0 and pytest-rerunfailures 16.7. The clean suite covers:

- plain tests with session- and module-scoped yield fixtures, stdout/stderr output and a warning
- parametrize with ids `a::b`, a space, unicode and `<&>`
- a stacked parametrize grid and duplicate `id="same"` params
- a class with a parametrized method and a nested class
- `unittest.TestCase` with passing `subTest`
- an asyncio test
- `record_property`, `record_xml_attribute` and `record_testsuite_property`
- a pytest-benchmark test
- a lenient xpass

Every run below had pytest rc=0 and **gate rc=0**:

- serial; `-n 2`, `-n 4`, `-n auto --dist loadfile`, `--dist each` (46), `worksteal`, `loadgroup`, `loadscope`
- `junit_family=xunit1`, `junit_family=legacy`, `junit_logging=all` + `junit_log_passing_tests`, `junit_suite_name=custom`
- `--cov` on, `--benchmark-disable`, `-k` deselection, the same file passed twice, `--keep-duplicates` (serial and xdist)

Pytest 8.4.2 writes `<testsuites name="pytest tests">` with no count attributes, so only the inner `testsuite` is compared. On a clean run its `tests` always equals the number of testcases.

**Only exception: pytest-rerunfailures.** A test that fails once and then passes on rerun is written as **two plain passing `<testcase>` elements**, while the suite keeps `tests="23"`. The gate prints `mismatch: suite "pytest" says tests=23, testcase elements show 24` and exits 1, although pytest exited 0. The plugin is not installed in this project, so CI cannot hit this. It matters only if someone adds the plugin later. Failing a required gate on a flaky pass is arguably correct anyway. This is not a finding.

## Can a non-passing report exit 0?

Not for any report pytest wrote. These real pytest 8.4.2 reports all exit 1, both serial and with `-n 2`/`-n 3`:

- fail
- setup error
- pass then teardown error
- fail then teardown error
- skip
- module `skipif` (pytest rc=0, gate rc=1)
- xfail only (pytest rc=0, gate rc=1)
- strict xpass
- unittest `subTest` failure
- collection error
- session-fixture teardown error
- `--reruns` that never pass
- `pytest.exit(returncode=0)` mid-run (pytest rc=0, gate rc=1 on `tests=1` vs 2 elements). At base this exited 0, so this is an improvement.

Hand-made shapes that still exit 0: a suite-level `<error>` with no `errors` attribute, `<testcase status="failed">`, `<failure>` nested under `<system-out>`, a namespaced `<j:failure>`, and Surefire `<flakyFailure>`/`<rerun>` children. Pytest writes none of these. All of them also exit 0 at base 6b792ba1, so they are unchanged behaviour and out of scope. If the suite-level `<error>` carries `errors="1"`, the mismatch check now catches it (rc=1). Malformed counts (`tests="1.0"`, `failures=""`) raise ValueError at `:56`, rc=1, so they fail closed.

## Observations (not findings)

- On pytest's own teardown-error shapes, the failure output gets an extra `mismatch: ... tests=2, testcase elements show 1` line, because pytest's `tests` attribute counts those shapes differently. The exit is already 1 for the error itself. The tests pin this output on purpose (`test_pass_then_teardown_error_...`, `test_fail_then_teardown_error_...`).
- A test that fails in call and then errors in teardown appears as 2 tests in the summary (1 failed + 1 error), because pytest writes it as two testcases. "passed" is now correct in every case I ran.
