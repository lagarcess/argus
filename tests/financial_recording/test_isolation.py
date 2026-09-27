import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SKIPPED_DIRS = {"node_modules", ".next"}


@pytest.mark.parametrize("module", ["model", "derive", "scenarios"])
def test_reference_model_loads_no_argus_module(module):
    probe = (
        "import sys; "
        f"import tests.financial_recording.{module}; "
        "loaded = sorted(n for n in sys.modules if n == 'argus' or n.startswith('argus.')); "
        "assert not loaded, loaded"
    )
    environment = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(REPO / "src"), str(REPO)]),
    }
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_production_trees_never_reference_the_reference_model():
    hits = []
    scanned = 0
    for tree in (REPO / "src", REPO / "web"):
        for directory, subdirectories, files in os.walk(tree):
            subdirectories[:] = [
                name for name in subdirectories if name not in SKIPPED_DIRS
            ]
            for name in files:
                path = Path(directory) / name
                scanned += 1
                if b"financial_recording" in path.read_bytes():
                    hits.append(str(path.relative_to(REPO)))
    assert scanned > 100
    assert hits == []
