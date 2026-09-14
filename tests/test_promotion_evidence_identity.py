"""What evidence measured at one commit may stand for (#608)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

import pytest

from tests.promotion_evidence_configuration import release_configuration_at_commit
from tests.promotion_evidence_identity import (
    _RECORDS_BEFORE_THIS_RULE,
    assert_measurement_stands_for,
    entry_modules,
    import_roots,
    reach_in_tree,
    reachable_changes,
)
from tests.promotion_evidence_repository import (
    REACHED_BY_THE_EVAL,
    STRUCTURAL_CHANGES_REACHED,
    UNREACHED_BY_THE_EVAL,
    commit_changes,
    commit_files,
    commit_measured_repository,
)

ROOT = Path(__file__).resolve().parents[1]
SHARING_OFF_PREFLIGHT = (
    ROOT
    / "docs/reports/evidence/2026-09-12-main-promotion/sharing-off/provenance-preflight.json"
)

_LOADED_MODULE_FILES = """
import importlib, json, pathlib, sys
root = pathlib.Path.cwd().resolve()
roots, modules = json.loads(sys.argv[1])
sys.path[:0] = [str(root / entry) for entry in roots]
for module in modules:
    importlib.import_module(module)
files = {
    pathlib.Path(module.__file__).resolve()
    for module in list(sys.modules.values())
    if getattr(module, "__file__", None)
}
print(json.dumps(sorted(
    path.relative_to(root).as_posix() for path in files if path.is_relative_to(root)
)))
"""


@pytest.mark.parametrize(
    "paths",
    [pytest.param(paths, id=kind) for kind, paths in UNREACHED_BY_THE_EVAL.items()],
)
def test_change_the_measurement_cannot_reach_keeps_the_evidence(
    tmp_path: Path, paths: tuple[str, ...]
) -> None:
    measured = commit_measured_repository(tmp_path)
    shipped = commit_changes(tmp_path, paths)

    assert reachable_changes(measured, shipped, repository_root=tmp_path) == ()


@pytest.mark.parametrize(
    "path",
    [pytest.param(path, id=kind) for kind, path in REACHED_BY_THE_EVAL.items()],
)
def test_change_the_measurement_reaches_needs_a_new_one(
    tmp_path: Path, path: str
) -> None:
    measured = commit_measured_repository(tmp_path)
    shipped = commit_changes(tmp_path, [path])

    assert reachable_changes(measured, shipped, repository_root=tmp_path) == (path,)


@pytest.mark.parametrize(
    ("before", "after", "reached"),
    [
        pytest.param(before, after, reached, id=kind)
        for kind, (before, after, reached) in STRUCTURAL_CHANGES_REACHED.items()
    ],
)
def test_added_deleted_or_moved_reached_files_need_a_new_measurement(
    tmp_path: Path,
    before: Mapping[str, str | None],
    after: Mapping[str, str | None],
    reached: tuple[str, ...],
) -> None:
    commit_measured_repository(tmp_path)
    measured = commit_files(tmp_path, before)
    shipped = commit_files(tmp_path, after)

    assert reachable_changes(measured, shipped, repository_root=tmp_path) == reached


def test_2026_09_13_sharing_off_change_kept_its_measurement() -> None:
    """The reproduction that opened #608: only release flags and docs changed."""

    preflight = json.loads(SHARING_OFF_PREFLIGHT.read_text(encoding="utf-8"))

    assert (
        reachable_changes(
            preflight["old_measured_sha"],
            preflight["sharing_off_product_sha"],
            repository_root=ROOT,
        )
        == ()
    )


def test_manifest_names_the_commit_its_evidence_measured(tmp_path: Path) -> None:
    measured = commit_measured_repository(tmp_path)
    shipped = commit_changes(tmp_path, UNREACHED_BY_THE_EVAL["release-flags"])
    manifest_path = tmp_path / "2026-09-13-main-production-promotion.md"
    binding = {
        "evidence": "the live eval scorecard",
        "measured_sha": measured,
        "shipped_sha": shipped,
        "release_configuration": release_configuration_at_commit(
            measured, repository_root=tmp_path
        ),
        "repository_root": tmp_path,
    }

    assert_measurement_stands_for(
        f"- Candidate SHA: `{shipped}`\n- Live eval measured SHA: `{measured}`\n",
        manifest_path,
        **binding,
    )
    with pytest.raises(AssertionError, match="Name the measured commit"):
        assert_measurement_stands_for(
            f"- Candidate SHA: `{shipped}`\n", manifest_path, **binding
        )


def test_rejection_names_the_reached_files_that_changed(tmp_path: Path) -> None:
    measured = commit_measured_repository(tmp_path)
    changed = REACHED_BY_THE_EVAL["lazily-imported-module"]
    shipped = commit_changes(tmp_path, [changed])

    with pytest.raises(
        AssertionError, match=rf"{re.escape(changed)}\. Measure again at {shipped[:8]}"
    ):
        assert_measurement_stands_for(
            f"`{measured}`",
            tmp_path / "2026-09-13-main-production-promotion.md",
            evidence="the live eval scorecard",
            measured_sha=measured,
            release_configuration=release_configuration_at_commit(
                shipped, repository_root=tmp_path
            ),
            shipped_sha=shipped,
            repository_root=tmp_path,
        )


@pytest.mark.parametrize("measured", ["", "0" * 40], ids=["unrecorded", "unknown"])
def test_evidence_binds_a_commit_in_this_repository(
    tmp_path: Path, measured: str
) -> None:
    shipped = commit_measured_repository(tmp_path)

    with pytest.raises(AssertionError, match="not a commit in this repository"):
        assert_measurement_stands_for(
            f"`{measured}`",
            tmp_path / "2026-09-13-main-production-promotion.md",
            evidence="the live eval scorecard",
            measured_sha=measured,
            release_configuration=release_configuration_at_commit(
                shipped, repository_root=tmp_path
            ),
            shipped_sha=shipped,
            repository_root=tmp_path,
        )


def test_record_before_this_rule_allows_only_its_known_difference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = tmp_path / "2026-01-01-example-promotion.md"
    known = REACHED_BY_THE_EVAL["test-module"]
    monkeypatch.setitem(_RECORDS_BEFORE_THIS_RULE, record.name, frozenset({known}))
    measured = commit_measured_repository(tmp_path)
    binding = {
        "evidence": "the baseline eval scorecard",
        "release_configuration": release_configuration_at_commit(
            measured, repository_root=tmp_path
        ),
        "measured_sha": measured,
        "repository_root": tmp_path,
    }

    assert_measurement_stands_for(
        "", record, shipped_sha=commit_changes(tmp_path, [known]), **binding
    )
    beyond = commit_changes(tmp_path, [REACHED_BY_THE_EVAL["imported-module"]])
    with pytest.raises(AssertionError, match="Measure again"):
        assert_measurement_stands_for("", record, shipped_sha=beyond, **binding)


def test_reach_covers_every_repository_module_the_measurement_loads() -> None:
    """Python's own import of the measurement is the ground truth, and reach must
    never count fewer files than it loads."""

    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    tracked = frozenset(path for path in listed.split("\0") if path)

    def read(paths: Iterable[str]) -> dict[str, bytes]:
        return {
            path: (ROOT / path).read_bytes() for path in paths if (ROOT / path).is_file()
        }

    reach = reach_in_tree(tracked, read)
    roots = import_roots(tracked, read)
    loaded = subprocess.run(
        [
            sys.executable,
            "-c",
            _LOADED_MODULE_FILES,
            json.dumps([list(roots), list(entry_modules(tracked, roots))]),
        ],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout

    loaded_files = frozenset(json.loads(loaded.strip().splitlines()[-1]))
    assert loaded_files & tracked <= reach, sorted((loaded_files & tracked) - reach)
