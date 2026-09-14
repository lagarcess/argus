"""Whether evidence measured at one commit stands for another.

Every promotion check that binds a measurement to a build asks this module: the
live eval scorecard, the baseline at the deployed build, and each side of a
targeted A/B. Evidence measured at commit A stands for build B when nothing the
measurement can reach differs between them.

Reach fails closed. Python loads code through imports, strings, plugins, warning
filters and startup modules, and the toolchain reads its configuration from the
repository root, more channels than a reader can list. So every Python file the
eval process could import counts, with the data beside it, the pytest
configuration on its path, and every root file except the release contract's
deploy files and documentation. Only files outside that change without a new
measurement: deploy configuration, migrations, frontend code, docs and evidence.
"""

from __future__ import annotations

import importlib.machinery
import posixpath
import re
import subprocess
from collections.abc import Callable, Iterable, Mapping
from functools import lru_cache
from pathlib import Path, PurePosixPath

import iniconfig

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

# The live eval runs this module under pytest, and the targeted A/B imports it.
MEASUREMENT_ENTRY = "tests/evals/test_measurement_eval_live.py"

# Longest first, so an extension module's full suffix wins over ".so".
_MODULE_SUFFIXES = tuple(
    sorted(importlib.machinery.all_suffixes(), key=len, reverse=True)
)

# pytest takes its settings from an ini, toml or cfg file in the test's folder or
# above it; these are parsed for the pythonpath they declare.
_CONFIG_SUFFIXES = frozenset({".ini", ".toml", ".cfg"})

# The toolchain (pytest, coverage, Poetry, the interpreter pin) finds its
# configuration at the root, so every root file counts except the Render
# Blueprint and environment template the release contract owns, which the eval
# never reads, and documentation.
_ROOT_FILES_THE_EVAL_NEVER_READS = frozenset({"render.yaml", ".env.example"})
_DOCUMENTATION_SUFFIX = ".md"

# Recorded before this rule and not re-measurable: each baseline measured a commit
# that differs from the deployed build only in these release-validator tests, and
# the manifest does not name the measured commit.
_RECORDS_BEFORE_THIS_RULE: dict[str, frozenset[str]] = {
    "2026-08-13-api-domain-promotion.md": frozenset(
        {
            "tests/release_promotion_evidence_support.py",
            "tests/test_private_alpha_release_docs.py",
        }
    ),
    "2026-08-13-guest-signup-hotfix-promotion.md": frozenset(
        {"tests/test_private_alpha_release_docs.py"}
    ),
}

_FULL_SHA = re.compile(r"[0-9a-f]{40}")

ReadFiles = Callable[[Iterable[str]], Mapping[str, bytes]]


def assert_measurement_stands_for(
    manifest: str,
    manifest_path: Path,
    *,
    evidence: str,
    measured_sha: str,
    shipped_sha: str,
    repository_root: Path,
) -> None:
    """Evidence stands for a commit it did not measure only when the measurement
    cannot tell the two apart, and the manifest names both."""

    if measured_sha == shipped_sha:
        return
    name = manifest_path.name
    for sha in (measured_sha, shipped_sha):
        assert _FULL_SHA.fullmatch(sha) and _is_commit(sha, repository_root), (
            f"{name}: {evidence} binds {sha or '<unrecorded>'}, which is not a "
            "commit in this repository."
        )
    known = _RECORDS_BEFORE_THIS_RULE.get(name, frozenset())
    touched = [
        path
        for path in reachable_changes(
            measured_sha, shipped_sha, repository_root=repository_root
        )
        if path not in known
    ]
    assert not touched, (
        f"{name}: {evidence} measured {measured_sha[:8]}, and {len(touched)} "
        f"file(s) it reaches differ at {shipped_sha[:8]}: "
        f"{', '.join(touched[:12])}. Measure again at {shipped_sha[:8]}."
    )
    assert measured_sha in manifest or name in _RECORDS_BEFORE_THIS_RULE, (
        f"{name}: {evidence} measured {measured_sha} and stands for "
        f"{shipped_sha}. Name the measured commit in the manifest."
    )


def reachable_changes(
    measured_sha: str, shipped_sha: str, *, repository_root: Path
) -> tuple[str, ...]:
    """Files that either commit's measurement reaches and that differ between them."""

    if measured_sha == shipped_sha:
        return ()
    changed = _git_paths(
        repository_root,
        "diff",
        "--name-only",
        "--no-renames",
        "-z",
        measured_sha,
        shipped_sha,
    )
    reach = measurement_reach(
        measured_sha, repository_root=repository_root
    ) | measurement_reach(shipped_sha, repository_root=repository_root)
    return tuple(sorted(changed & reach))


def measurement_reach(sha: str, *, repository_root: Path) -> frozenset[str]:
    """Every file in commit `sha` that the live measurement can reach."""

    if not _FULL_SHA.fullmatch(sha):
        raise ValueError(f"measurement reach needs a full commit SHA, not {sha!r}")
    return _reach_at_commit(repository_root.resolve(), sha)


@lru_cache(maxsize=None)
def _reach_at_commit(repository_root: Path, sha: str) -> frozenset[str]:
    tracked = _git_paths(repository_root, "ls-tree", "-r", "--name-only", "-z", sha)
    return reach_in_tree(tracked, lambda paths: _blobs(repository_root, sha, paths))


def reach_in_tree(tracked: frozenset[str], read: ReadFiles) -> frozenset[str]:
    """Every importable Python file, the data beside it, the pytest configuration
    on the measurement's path, and the toolchain configuration at the root."""

    assert MEASUREMENT_ENTRY in tracked, (
        f"{MEASUREMENT_ENTRY} is missing, so what the measurement reaches is unknown."
    )
    roots = import_roots(tracked, read)
    modules = frozenset(path for path in tracked if _importable(path, roots))
    root_configuration = {
        path
        for path in tracked
        if "/" not in path
        and path not in _ROOT_FILES_THE_EVAL_NEVER_READS
        and not path.endswith(_DOCUMENTATION_SUFFIX)
    }
    return frozenset(
        modules
        | _data_beside(modules, tracked, roots)
        | set(pytest_settings(tracked, read))
        | root_configuration
    )


def pytest_settings(
    tracked: frozenset[str], read: ReadFiles
) -> dict[str, dict[str, list[str]]]:
    """Each config file pytest could read for the measurement, with the pytest
    settings in it as words."""

    folders = {str(folder) for folder in PurePosixPath(MEASUREMENT_ENTRY).parents}
    paths = sorted(
        path
        for path in tracked
        if str(PurePosixPath(path).parent) in folders
        and PurePosixPath(path).suffix in _CONFIG_SUFFIXES
    )
    return {path: _pytest_section(path, source) for path, source in read(paths).items()}


def import_roots(tracked: frozenset[str], read: ReadFiles) -> tuple[str, ...]:
    """Where the eval resolves imports: every pythonpath a pytest config declares,
    relative to that config, the repository root (spelled ''), and each Poetry
    package source."""

    declared = [
        posixpath.join(str(PurePosixPath(path).parent), entry)
        for path, settings in pytest_settings(tracked, read).items()
        for entry in settings.get("pythonpath", [])
    ]
    pyproject = read(["pyproject.toml"]).get("pyproject.toml")
    tool = tomllib.loads(pyproject.decode("utf-8")).get("tool", {}) if pyproject else {}
    declared += [
        ".",
        *(package.get("from", ".") for package in tool.get("poetry", {}).get("packages", [])),
    ]
    normalized = (posixpath.normpath(entry) for entry in declared)
    return tuple(dict.fromkeys("" if entry == "." else entry for entry in normalized))


def entry_modules(tracked: frozenset[str], roots: tuple[str, ...]) -> tuple[str, ...]:
    """The measurement module, after each conftest.py pytest loads before it from
    the rootdir down."""

    entry = PurePosixPath(MEASUREMENT_ENTRY)
    paths = (
        *(str(folder / "conftest.py") for folder in reversed(entry.parents)),
        MEASUREMENT_ENTRY,
    )
    return tuple(_module_name(path, roots) for path in paths if path in tracked)


def _importable(path: str, roots: tuple[str, ...]) -> bool:
    """A file with a module suffix whose path under some import root is a dotted
    module name."""

    suffix = next((suffix for suffix in _MODULE_SUFFIXES if path.endswith(suffix)), None)
    if suffix is None:
        return False
    for root in roots:
        if root and not path.startswith(f"{root}/"):
            continue
        relative = path[len(root) + 1 :] if root else path
        if all(part.isidentifier() for part in relative[: -len(suffix)].split("/")):
            return True
    return False


def _pytest_section(path: str, source: bytes) -> dict[str, list[str]]:
    text = source.decode("utf-8")
    if path.endswith(".toml"):
        document = tomllib.loads(text)
        table = document.get("tool", {}).get("pytest", {})
        section = {**document.get("pytest", {}), **table, **table.get("ini_options", {})}
    else:
        config = iniconfig.IniConfig(path, data=text)
        section = {
            key: value
            for name in ("pytest", "tool:pytest")
            if name in config
            for key, value in config[name].items()
        }
    return {
        key: [str(item) for item in value] if isinstance(value, list) else str(value).split()
        for key, value in section.items()
        if not isinstance(value, dict)
    }


def _module_name(path: str, roots: tuple[str, ...]) -> str:
    root = max((root for root in roots if not root or path.startswith(f"{root}/")), key=len)
    relative = path[len(root) + 1 :] if root else path
    return relative.removesuffix(".py").removesuffix("/__init__").replace("/", ".")


def _data_beside(
    modules: frozenset[str], tracked: frozenset[str], roots: tuple[str, ...]
) -> frozenset[str]:
    """Package data, where importlib.resources and Path(__file__) find it: a
    non-Python file in or below a folder of importable modules, unless a package
    without one or an import root in between claims it first."""

    folders = {str(PurePosixPath(module).parent) for module in modules} - {".", *roots}
    packages = {
        str(PurePosixPath(path).parent)
        for path in tracked
        if PurePosixPath(path).name == "__init__.py"
    }
    data = set()
    for path in tracked:
        if path in modules:
            continue
        for folder in map(str, PurePosixPath(path).parents):
            if folder in folders:
                data.add(path)
                break
            if folder in packages or folder in roots or folder == ".":
                break
    return frozenset(data)


def _git_paths(repository_root: Path, *args: str) -> frozenset[str]:
    output = subprocess.run(
        ["git", *args], cwd=repository_root, capture_output=True, check=True
    ).stdout
    return frozenset(path for path in output.decode("utf-8").split("\0") if path)


def _is_commit(sha: str, repository_root: Path) -> bool:
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        cwd=repository_root,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def _blobs(repository_root: Path, sha: str, paths: Iterable[str]) -> dict[str, bytes]:
    requested = list(paths)
    if not requested:
        return {}
    output = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=repository_root,
        input="".join(f"{sha}:{path}\n" for path in requested).encode("utf-8"),
        capture_output=True,
        check=True,
    ).stdout
    blobs: dict[str, bytes] = {}
    offset = 0
    for path in requested:
        header_end = output.index(b"\n", offset)
        header = output[offset:header_end].split()
        offset = header_end + 1
        if header[-1] == b"missing":
            continue
        size = int(header[2])
        blobs[path] = output[offset : offset + size]
        offset += size + 1
    return blobs
