from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from shutil import copy2

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_frontend_search_casefold.py"
GENERATED_DATA = ROOT / "web" / "lib" / "search-casefold-data.ts"


def test_frontend_search_casefold_data_matches_python_contract() -> None:
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_frontend_search_casefold_check_rejects_crlf_byte_drift(tmp_path: Path) -> None:
    copied_generator = tmp_path / "scripts" / "generate_frontend_search_casefold.py"
    copied_generator.parent.mkdir()
    copy2(GENERATOR, copied_generator)
    copied_target = tmp_path / "web" / "lib" / "search-casefold-data.ts"
    copied_target.parent.mkdir(parents=True)
    expected_bytes = GENERATED_DATA.read_bytes()
    copied_target.write_bytes(expected_bytes.replace(b"\n", b"\r\n"))

    check_result = subprocess.run(
        [sys.executable, str(copied_generator), "--check"],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
    )

    assert check_result.returncode == 1
    assert "casefold data is stale" in check_result.stderr

    write_result = subprocess.run(
        [sys.executable, str(copied_generator)],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
    )
    assert write_result.returncode == 0, write_result.stderr
    assert copied_target.read_bytes() == expected_bytes
