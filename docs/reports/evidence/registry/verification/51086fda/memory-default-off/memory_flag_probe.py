import json
import os
import pytest

TARGET = "tests/memory/test_saved_decision_lifecycle.py::test_registered_default_off_proposal_creates_no_state"
FLAG = "ARGUS_ENABLE_PERSONALIZATION_MEMORY"

@pytest.hookimpl(tryfirst=True)
def pytest_runtest_call(item):
    if item.nodeid != TARGET:
        return
    before = os.environ.get(FLAG)
    if os.environ.get("REGISTRY_MEMORY_PROBE_CLEAR_AT_TEST") == "1":
        item._request.getfixturevalue("monkeypatch").delenv(FLAG, raising=False)
    print("MEMORY_FLAG_PROBE " + json.dumps({"before_test": before, "at_test": os.environ.get(FLAG)}))
