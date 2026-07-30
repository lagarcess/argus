from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from shutil import copy2

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_frontend_search_casefold.py"
GENERATED_DATA = ROOT / "web" / "lib" / "search-casefold-data.ts"
GENERATED_BACKEND_DATA = (
    ROOT / "src" / "argus" / "domain" / "search_symbol_casefold_data.py"
)


def test_frontend_search_casefold_data_matches_python_contract() -> None:
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_casefold_check_requires_backend_symbol_data(tmp_path: Path) -> None:
    copied_generator = tmp_path / "scripts" / "generate_frontend_search_casefold.py"
    copied_generator.parent.mkdir()
    copy2(GENERATOR, copied_generator)
    copied_target = tmp_path / "web" / "lib" / "search-casefold-data.ts"
    copied_target.parent.mkdir(parents=True)
    copy2(GENERATED_DATA, copied_target)

    check_result = subprocess.run(
        [sys.executable, str(copied_generator), "--check"],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
    )

    assert check_result.returncode == 1
    assert "casefold data is stale" in check_result.stderr


def test_frontend_search_casefold_check_rejects_crlf_byte_drift(tmp_path: Path) -> None:
    copied_generator = tmp_path / "scripts" / "generate_frontend_search_casefold.py"
    copied_generator.parent.mkdir()
    copy2(GENERATOR, copied_generator)
    copied_target = tmp_path / "web" / "lib" / "search-casefold-data.ts"
    copied_target.parent.mkdir(parents=True)
    expected_bytes = GENERATED_DATA.read_bytes()
    copied_target.write_bytes(expected_bytes.replace(b"\n", b"\r\n"))
    copied_backend_target = (
        tmp_path / "src" / "argus" / "domain" / "search_symbol_casefold_data.py"
    )
    copied_backend_target.parent.mkdir(parents=True)
    copy2(GENERATED_BACKEND_DATA, copied_backend_target)

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
