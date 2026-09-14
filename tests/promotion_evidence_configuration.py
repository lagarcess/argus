"""Release-owned API model and flag identity for eval evidence.

This checks measurement/configuration mistakes, not deliberate evidence tampering.
The release profile owns the keys; neither the eval nor the gate keeps a list.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Mapping

RELEASE_PROFILE = ".github/private-alpha-release-profile.json"

# These already shipped before configuration was recorded. Keep their evidence
# bytes unchanged; every new manifest needs measured configuration on every side.
MANIFESTS_BEFORE_CONFIGURATION = frozenset(
    {
        "2026-08-13-main-production-promotion.md",
        "2026-08-13-api-domain-promotion.md",
        "2026-08-13-guest-signup-hotfix-promotion.md",
        "2026-08-16-main-production-promotion.md",
        "2026-08-21-main-production-promotion.md",
        "2026-08-27-main-production-promotion.md",
        "2026-09-03-main-production-promotion.md",
        "2026-09-05-main-production-promotion.md",
        "2026-09-12-main-production-promotion.md",
    }
)


def release_configuration_at_commit(sha: str, *, repository_root: Path) -> dict[str, str]:
    """Only API model IDs and explicit on/off flags from the named commit."""
    assert re.fullmatch(r"[0-9a-f]{40}", sha), "release_configuration: full SHA required"
    source = subprocess.run(
        ["git", "--no-replace-objects", "show", f"{sha}:{RELEASE_PROFILE}"],
        cwd=repository_root,
        capture_output=True,
        check=True,
        text=True,
        timeout=10,
    ).stdout
    environment = json.loads(source)["services"]["api"]["env"]
    return {
        key: value
        for key, value in environment.items()
        if key.endswith("_MODEL") or value in ("true", "false")
    }


def measured_release_configuration(
    sha: str, *, repository_root: Path
) -> dict[str, str | None]:
    """Read only contract-selected keys, from the eval's process environment."""
    from argus.llm.memory_embedding import resolve_memory_embedding_model
    from argus.llm.openrouter import _env_model_value

    values: dict[str, str | None] = {}
    for key in release_configuration_at_commit(sha, repository_root=repository_root):
        if key == "ARGUS_MEMORY_EMBEDDING_MODEL":
            values[key] = resolve_memory_embedding_model()
        elif key.endswith("_MODEL"):
            # The same per-key resolution used by OpenRouter's ordered candidates.
            # Keep primary/fallback slots even when they resolve to the same ID.
            values[key] = _env_model_value(key)
        else:
            raw = os.getenv(key)
            value = raw.strip().lower() if raw is not None else None
            # Flag parsers differ in their accepted aliases. Require the contract's
            # explicit true/false spelling rather than inventing shared semantics.
            # Missing is unknown, never filled from the contract's desired value.
            values[key] = value
    return values


def assert_release_configuration_matches(
    measured: object, *, shipped_sha: str, repository_root: Path, evidence: str
) -> None:
    assert isinstance(measured, Mapping), (
        f"{evidence}: missing release_configuration; new promotions need "
        "configuration-bearing evidence (measurement scorecard schema v3)."
    )
    expected = release_configuration_at_commit(
        shipped_sha, repository_root=repository_root
    )
    for key in sorted(expected.keys() | measured.keys()):
        actual = measured.get(key)
        contract = expected.get(key)
        assert key in measured and key in expected and actual == contract, (
            f"{evidence}: release_configuration {key}: measured={actual!r}, "
            f"contract={contract!r} at {shipped_sha[:8]}. Measure again."
        )
