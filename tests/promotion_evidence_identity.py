"""Whether evidence measured at one commit stands for another.

Every promotion check that binds a measurement to a build asks this module: the
live eval scorecard, the baseline at the deployed build, and each side of a
targeted A/B. Evidence measured at commit A stands for build B when nothing the
measurement can reach differs between them. A config, migration, frontend or
docs change keeps the evidence; a change to anything the eval imports needs a
new measurement.

Reach is read from the measurement's own imports in each commit's tree, never
from a list of product paths.
"""

from __future__ import annotations

import ast
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

# pytest takes its settings from an ini, toml or cfg file in the test's folder or
# above it, so every such file there can change the run.
_CONFIG_SUFFIXES = frozenset({".ini", ".toml", ".cfg"})

# Third-party code and the interpreter sit outside the tree, which reaches them
# only through the files the environment is built from.
_ENVIRONMENT_FILES = ("pyproject.toml", "poetry.lock", ".python-version")

# Their baselines measured a commit that the deployed build cannot be told apart
# from, recorded before a manifest had to name the measured commit.
_MANIFESTS_PREDATING_MEASURED_SHA_RULE = frozenset(
    {
        "2026-08-13-api-domain-promotion.md",
        "2026-08-13-guest-signup-hotfix-promotion.md",
    }
)

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
    touched = reachable_changes(
        measured_sha, shipped_sha, repository_root=repository_root
    )
    assert not touched, (
        f"{name}: {evidence} measured {measured_sha[:8]}, and {len(touched)} "
        f"file(s) it reaches differ at {shipped_sha[:8]}: "
        f"{', '.join(touched[:12])}. Measure again at {shipped_sha[:8]}."
    )
    assert measured_sha in manifest or name in _MANIFESTS_PREDATING_MEASURED_SHA_RULE, (
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
    """The measurement's modules, the data beside them, its pytest configuration,
    and its environment.

    An import counts wherever it appears, inside a function, as a package named
    by a string, or as a plugin a pytest config names, because code loaded late
    is measured all the same.
    """

    assert MEASUREMENT_ENTRY in tracked, (
        f"{MEASUREMENT_ENTRY} is missing, so what the measurement reaches is unknown."
    )
    settings = pytest_settings(tracked, read)
    roots = import_roots(tracked, read)
    named = [word for values in settings.values() for words in values.values() for word in words]
    modules = _imported_modules(tracked, read, roots, named)
    return frozenset(
        modules
        | _data_beside(modules, tracked, roots)
        | set(settings)
        | {path for path in _ENVIRONMENT_FILES if path in tracked}
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


def _imported_modules(
    tracked: frozenset[str],
    read: ReadFiles,
    roots: tuple[str, ...],
    named: Iterable[str],
) -> frozenset[str]:
    def resolve(dotted: str) -> tuple[str, ...]:
        parts = dotted.split(".")
        if not all(part.isidentifier() for part in parts):
            return ()
        matches = []
        for root in roots:
            stem = "/".join((root, *parts) if root else parts)
            # A regular package shadows a same-named module beside it. Roots come
            # from several configs, so a match under every root counts.
            for path in (f"{stem}/__init__.py", f"{stem}.py"):
                if path in tracked:
                    matches.append(path)
                    break
        return tuple(matches)

    found: dict[str, str] = {}
    pending: dict[str, str] = {}

    def reach(dotted: str) -> None:
        # Importing a.b.c runs a and a.b first.
        parts = dotted.split(".")
        for depth in range(1, len(parts) + 1):
            module = ".".join(parts[:depth])
            for path in resolve(module):
                if path not in found:
                    pending.setdefault(path, module)

    for module in entry_modules(tracked, roots):
        reach(module)
    # A module a pytest config names, such as `-p plugin`, loads before the run.
    for word in named:
        if resolve(word.removeprefix("-p")):
            reach(word.removeprefix("-p"))
    while pending:
        batch = dict(pending)
        pending.clear()
        found.update(batch)
        for path, source in read(batch).items():
            module = batch[path]
            package = module if path.endswith("__init__.py") else module.rpartition(".")[0]
            for node in ast.walk(ast.parse(source, filename=path)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        reach(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    base = _absolute_module(node, package)
                    for alias in node.names:
                        reach(f"{base}.{alias.name}" if base else alias.name)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    # importlib.resources.files("pkg") and import_module("pkg").
                    if resolve(node.value):
                        reach(node.value)
    return frozenset(found)


def _module_name(path: str, roots: tuple[str, ...]) -> str:
    root = max((root for root in roots if not root or path.startswith(f"{root}/")), key=len)
    relative = path[len(root) + 1 :] if root else path
    return relative.removesuffix(".py").removesuffix("/__init__").replace("/", ".")


def _absolute_module(node: ast.ImportFrom, package: str) -> str:
    if not node.level:
        return node.module or ""
    anchor = package.split(".") if package else []
    anchor = anchor[: max(len(anchor) - node.level + 1, 0)]
    return ".".join([*anchor, *([node.module] if node.module else [])])


def _data_beside(
    modules: frozenset[str], tracked: frozenset[str], roots: tuple[str, ...]
) -> frozenset[str]:
    """Package data, where importlib.resources and Path(__file__) find it: a
    non-Python file in or below a measured module's folder, unless an unmeasured
    package or an import root in between claims it first."""

    folders = {str(PurePosixPath(module).parent) for module in modules} - {".", *roots}
    packages = {
        str(PurePosixPath(path).parent)
        for path in tracked
        if PurePosixPath(path).name == "__init__.py"
    }
    data = set()
    for path in tracked:
        if path.endswith(".py"):
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
