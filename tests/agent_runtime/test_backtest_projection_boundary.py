"""The backtest declaration is usable without importing a sharing owner."""

import os
import subprocess
import sys


def test_backtest_declaration_builds_when_sharing_modules_are_unavailable():
    script = """
import importlib.abc, sys
class NoSharing(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('argus.api.public_excerpt', 'argus.domain.public_excerpt')):
            raise AssertionError('registry imported sharing owner: ' + fullname)
sys.meta_path.insert(0, NoSharing())
from argus.agent_runtime.tools.registered_backtest import get_backtest_declaration
assert get_backtest_declaration().result_type.__module__.startswith('argus.agent_runtime.tools.')
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "src"},
        check=False,
    )
    assert result.returncode == 0, result.stderr
