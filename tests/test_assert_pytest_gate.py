from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "scripts" / "qa" / "assert_pytest_gate.py"
REAL_POSTGRES_FIVE_FAILURES = (
    REPO_ROOT / "tests" / "fixtures" / "pytest_gate" / "real_postgres_five_failures.xml"
)


def _run_gate(junit_xml: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE), str(junit_xml)],
        capture_output=True,
        text=True,
        check=False,
    )


def _write_report(tmp_path: Path, suite_attributes: str, cases: str) -> Path:
    report = tmp_path / "junit.xml"
    report.write_text(
        f'<testsuites><testsuite name="pytest" {suite_attributes}>'
        f"{cases}</testsuite></testsuites>",
        encoding="utf-8",
    )
    return report


def test_real_report_with_five_failures_fails_and_names_them() -> None:
    result = _run_gate(REAL_POSTGRES_FIVE_FAILURES)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == (
        "required pytest gate failed:"
        " 7 tests, 2 passed, 5 failed, 0 errors, 0 skipped\n"
        "  failed: tests.test_bounded_read_indexes_postgres"
        "::test_forward_indexes_exist_without_changing_rls_or_select_grants\n"
        "  failed: tests.test_guest_workspace_postgres"
        "::test_owner_scoped_rls_separates_guest_and_registered_product_rows\n"
        "  failed: tests.test_guest_workspace_postgres"
        "::test_expired_guest_cannot_read_or_write_product_rows\n"
        "  failed: tests.test_guest_workspace_postgres"
        "::test_profile_and_usage_table_grants_stay_service_owned\n"
        "  failed: tests.test_invite_code_security_postgres"
        "::test_no_client_role_can_ever_read_a_code_digest\n"
    )


def test_report_with_an_error_fails_and_names_it(tmp_path: Path) -> None:
    report = _write_report(
        tmp_path,
        'tests="2" failures="0" errors="1" skipped="0"',
        '<testcase classname="tests.test_a" name="test_ok" />'
        '<testcase classname="tests.test_a" name="test_setup_breaks">'
        '<error message="fixture raised" /></testcase>',
    )

    result = _run_gate(report)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == (
        "required pytest gate failed:"
        " 2 tests, 1 passed, 0 failed, 1 errors, 0 skipped\n"
        "  error: tests.test_a::test_setup_breaks\n"
    )


def test_clean_report_passes_with_every_count(tmp_path: Path) -> None:
    report = _write_report(
        tmp_path,
        'tests="2" failures="0" errors="0" skipped="0"',
        '<testcase classname="tests.test_a" name="test_one" />'
        '<testcase classname="tests.test_a" name="test_two" />',
    )

    result = _run_gate(report)

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == (
        "required pytest gate passed: 2 tests, 2 passed, 0 failed, 0 errors, 0 skipped\n"
    )


def test_report_with_a_skip_fails_and_names_it(tmp_path: Path) -> None:
    report = _write_report(
        tmp_path,
        'tests="2" failures="0" errors="0" skipped="1"',
        '<testcase classname="tests.test_a" name="test_one" />'
        '<testcase classname="tests.test_a" name="test_needs_stack">'
        '<skipped message="no local stack" /></testcase>',
    )

    result = _run_gate(report)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == (
        "required pytest gate failed:"
        " 2 tests, 1 passed, 0 failed, 0 errors, 1 skipped\n"
        "  skipped: tests.test_a::test_needs_stack\n"
    )


def test_report_that_collected_nothing_fails(tmp_path: Path) -> None:
    report = _write_report(tmp_path, 'tests="0" failures="0" errors="0" skipped="0"', "")

    result = _run_gate(report)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "required pytest gate collected zero tests\n"
