# R-gate-6b792ba1: review of PR #809 (pytest gate reports failures)

Diff: `a8c37d3a...6b792ba1`, 3 files. Checkout: `.claude/worktrees/cuadrao-gate`, HEAD verified `6b792ba165ee3eacbe0f78e14881e4352fdccf57`.

## Verdict

No P1. Two P2s and three P3s. No real pytest report I produced can pass the gate while a test failed. The gate decides from the suite summary attributes and ignores the testcase elements it already parses, so a report whose attributes undercount still exits 0. The new "passed" number is wrong whenever pytest records a teardown error.

The base gate passed the PR's own fixture. `python3 <(git show a8c37d3a:scripts/qa/assert_pytest_gate.py) tests/fixtures/pytest_gate/real_postgres_five_failures.xml` printed `required pytest gate passed: 7 tests, zero skips` with rc=0. At head it exits 1 and names all five tests. The fix is real.

## Findings

### P2-1: the decision trusts suite attributes over testcase elements

`scripts/qa/assert_pytest_gate.py:26-27` (`clean`), `:41-42` and `:53-56`.

`clean` reads only the summed `failures`/`errors`/`skipped` attributes. The `not_passed` tuple (`:44-51`) is used only for display. If the attributes undercount, the gate passes a report with a visible failure:

```xml
<testsuites><testsuite tests="2" failures="0" errors="0" skipped="0"><testcase classname="a" name="t1"/><testcase classname="a" name="t2"><failure message="x"/></testcase></testsuite></testsuites>
```
rc=0, stdout `required pytest gate passed: 2 tests, 2 passed, 0 failed, 0 errors, 0 skipped`

```xml
<testsuites><testsuite tests="2"><testcase classname="a" name="t1"/><testcase classname="a" name="t2"><failure message="x"/></testcase></testsuite></testsuites>
```
(count attributes missing) rc=0, same "passed" line.

```xml
<testsuites><testsuite tests="7" failures="0" errors="0" skipped="0"><testcase classname="a" name="t1"/></testsuite></testsuites>
```
rc=0, `7 tests, 7 passed` printed for one testcase.

Why P2 and not P1: pytest 8.4.2 (the locked version) always writes all four attributes, and they match its elements. Every real pytest report I generated was judged correctly. Only a hand-edited report or a non-pytest producer reaches this.

Smallest fix, at line 27: `return not (self.failures or self.errors or self.skipped or self.not_passed)`. To fail closed on case 3 as well, also fail when the attribute `tests` disagrees with `len(list(suite.iter("testcase")))`.

### P2-2: the printed "passed" count is wrong when pytest records a teardown error

`scripts/qa/assert_pytest_gate.py:22-23`

`passed = tests - failures - errors - skipped`. Pytest's `tests` attribute does not count tests one-to-one when a teardown error occurs:

- A test that fails in call and then errors in teardown is written as two `<testcase>` elements with the same name, one `<failure>` and one `<error>`. Pytest counts it once in `tests` (`cnt_double_fail_tests`) but once in each of `failures` and `errors`, so it is subtracted twice.
- A test that passes in call and then errors in teardown is counted in both `passed` and `error`, so `tests` is inflated by 1.

Evidence: real reports from `pytest==8.4.2` on Python 3.10.

`test_passtd.py` has one test, which passes and then hits a teardown `RuntimeError`. Pytest wrote:

```xml
<testsuite name="pytest" errors="1" failures="0" skipped="0" tests="2" ...><testcase classname="test_passtd" name="test_pass_then_teardown_error"><error message="failed on teardown with ..."/></testcase></testsuite>
```

Gate: rc=1, stderr `required pytest gate failed: 2 tests, 1 passed, 0 failed, 1 errors, 0 skipped` and `  error: test_passtd::test_pass_then_teardown_error`. There is one test and it did not pass.

`test_shapes.py` has 7 tests: a pass, a lenient xpass, fail plus teardown error, setup error, xfail, strict xpass, and a skip. Gate: rc=1, `7 tests, 1 passed, 2 failed, 2 errors, 2 skipped`. Two tests passed (the pass and the lenient xpass).

The hand-made single testcase holding both `<failure/>` and `<error/>` (`tests="1" failures="1" errors="1"`) gives rc=1 with `1 tests, -1 passed, 1 failed, 1 errors, 0 skipped`.

The exit code is right in every case. Only the summary line is wrong, and it shows on exactly the failure runs a person reads.

Smallest fix: compute `passed` from elements, as the number of `<testcase>` elements with no `failure`/`error`/`skipped` child. That gives 2 and 0 for the two real reports above. Otherwise, drop "passed" from the summary.

### P3-1: xfail is labelled "skipped"

`scripts/qa/assert_pytest_gate.py:10`

Pytest writes xfail as `<skipped type="pytest.xfail" message="known"/>`. The gate prints `skipped: test_shapes::test_xfail` and exits 1. Exit 1 is consistent with the base gate, which also counted it as a skip, and with "every test passed". The label sends a reader looking for a skip marker instead of an xfail marker. No `xfail` appears in `tests/test_*_postgres.py` or `tests/test_guest_auth_local_supabase.py` today. Fix: use the `type` attribute when it is `pytest.xfail`.

A lenient (non-strict) xpass is written as a plain passed testcase and passes the gate, rc=0 (`test_xpass_only.py`). A strict xpass is a `<failure message="[XPASS(strict)] ...">` and fails, rc=1. Both match pytest's own pass/fail semantics.

### P3-2: nested suites with counts only on the inner suite say "collected zero tests"

`scripts/qa/assert_pytest_gate.py:39`

```xml
<testsuites><testsuite name="outer"><testsuite name="inner" tests="2" failures="1" errors="0" skipped="0"><testcase classname="a" name="t1"/><testcase classname="a" name="t2"><failure message="x"/></testcase></testsuite></testsuite></testsuites>
```
rc=1, `required pytest gate collected zero tests`. This fails closed with a misleading message.

The same happens with counts only on the `<testsuites>` root:
```xml
<testsuites tests="1" failures="1"><testsuite><testcase classname="a" name="t1"><failure/></testcase></testsuite></testsuites>
```
rc=1, the same message.

Pytest never writes either shape. When both outer and inner suites carry counts (case 04 below), the result is correct. The fix for P2-1 (decide from elements) also fixes this message.

### P3-3: tests cover only the `<testsuites>` root

`tests/test_assert_pytest_gate.py:23-30`

`_write_report` always wraps the case in `<testsuites>`. Nothing tests the single-`<testsuite>` root branch (`:39`), several suites, the double-outcome/teardown shape behind P2-2, xfail, or attribute/element disagreement (P2-1). A test with a real teardown-error shape would have caught P2-2.

## Checks that came back clean

**(1) Call sites.** `git grep assert_pytest_gate` finds these callers:
- `.github/workflows/ci.yml:264` and `:273` (guest-release-gates job). Both run under the default `bash -e` shell, since `ci.yml` sets no `defaults`/`shell`. A failing pytest aborts the step before the gate runs, so in CI the new failure branch is unreachable. In CI, the only change is the success line, which goes from `N tests, zero skips` to the counts string.
- `docs/release-manifests/NEXT-PROMOTION-CHECKLIST.md:135,137`: manual, one command per line.
- `tests/test_ci_workflow.py:173`: checks only that the path appears in the step.
- `scripts/qa/run-guest-experience-qa.sh:39`: only a dirty-path allowlist.

Nothing parses the stdout or stderr text; a grep for `zero skips` and `pytest gate` over `scripts`, `.github` and `tests` found no consumers. The interface is unchanged (one positional path, exit 0/1).

**(2)/(3) Other shapes, all exit codes correct:**
- `<testsuite>` root clean: rc=0. Same root with a failure: rc=1, the failure named.
- Two suites with an error and a skip: rc=1, both named.
- Nested suites with counts on outer and inner: rc=1, the failure named.
- Strict xpass: rc=1.
- `<testsuites tests="0">`: rc=1. `<testsuites/>`: rc=1. Zero-test message correct.
- `tests="0"` with a testcase present: rc=1.
- Non-standard root `<report><testsuite ...>` with a failure: rc=1, named.
- `<rerun>` then pass (pytest-rerunfailures shape; the plugin is not in the lock file): rc=0.
- Missing file: FileNotFoundError traceback, rc=1. Empty file and unclosed tag: ParseError traceback, rc=1. `tests="1.0"`: ValueError traceback, rc=1. All fail closed, unchanged from the base gate.
- Real pytest 8.4.2 clean report: rc=0, `2 tests, 2 passed, 0 failed, 0 errors, 0 skipped`. Real pytest skip, setup error and teardown error: rc=1.

**(4) The tests check literal behaviour.** All five tests assert the exact returncode, stdout and stderr. Stub results, run against a scratch copy of the test file and fixture:
- gate replaced by `raise SystemExit(0)`: 5 failed.
- gate replaced by `raise SystemExit("x")`: 5 failed.
- base gate `a8c37d3a`: 4 failed, 1 passed (only the zero-tests test still passes, as expected).

**(5) Python 3.10 and ruff.**
- The script runs with plain `python3` (3.14.7 here) and under `uv run --python 3.10`. It needs only the standard library.
- `tests/test_assert_pytest_gate.py` passes on Python 3.10 with pytest 8.4.2: `5 passed` (`--noconftest -o addopts=""`).
- `ruff==0.4.10` (the locked version): `check` reports "All checks passed!" and `format --check` reports "2 files already formatted".
- `scripts/check_modularity_budget.py`: no violations.

## Environment note

My first ruff attempt used `poetry run`, which created an empty, gitignored `.venv/` in the `cuadrao-gate` worktree at 21:24. Removing it was refused by the permission classifier, so it is still there. It is untracked (`.gitignore:23`), and `git status --porcelain` is clean. Delete it if you want the worktree back exactly as it was. No repo files were edited. All XML experiments are in the session scratchpad under `scratchpad/gate/`.
