from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_render_config_audit_uses_the_checked_in_release_profile() -> None:
    source = _source(".github/render-env-sync.sh")

    assert "private-alpha-release-profile.py" in source
    assert "env-pairs" in source
    assert "required-present" in source
    assert "release_profile_hash=" in source
    assert "release_profile_status=ready" in source


def test_warmup_passes_through_release_profile_proof() -> None:
    source = _source(".github/warmup-render.sh")

    assert "release_profile_hash" in source
    assert "release_profile_status=ready" in source
