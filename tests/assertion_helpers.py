import json
from typing import Any, Dict


def assert_dicts_equal(
    actual: Dict[str, Any], expected: Dict[str, Any], context_msg: str = ""
) -> None:
    """
    Asserts that two dictionaries are equal, providing a helpful error message with diff.
    """
    if actual == expected:
        return

    actual_json = json.dumps(actual, indent=2, sort_keys=True, default=str)
    expected_json = json.dumps(expected, indent=2, sort_keys=True, default=str)
    diff_msg = f"Dictionaries are not equal.\n\nExpected:\n{expected_json}\n\nActual:\n{actual_json}"
    full_msg = f"{context_msg}\n{diff_msg}" if context_msg else diff_msg
    raise AssertionError(full_msg)


def assert_payload_matches(
    actual: Dict[str, Any], expected_subset: Dict[str, Any], context_msg: str = ""
) -> None:
    """
    Asserts that expected_subset is a subset of actual dictionary.
    """
    missing_or_mismatch = {}
    for k, v in expected_subset.items():
        if k not in actual:
            missing_or_mismatch[k] = "MISSING"
        elif actual[k] != v:
            missing_or_mismatch[k] = {"expected": v, "actual": actual[k]}

    if missing_or_mismatch:
        error_msg = f"{context_msg}\nPayload mismatch.\nErrors: {json.dumps(missing_or_mismatch, indent=2)}\nFull Actual: {json.dumps(actual, default=str, indent=2)}"
        raise AssertionError(error_msg)
