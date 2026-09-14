"""The web app and the API each hold the support address; these fail when they part."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from argus.domain.resend_email import SUPPORT_EMAIL_ADDRESS
from faker import Faker

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
SUPPORT_EMAIL_ENV = "NEXT_PUBLIC_ARGUS_SUPPORT_EMAIL"
WEB_OWNER = "lib/support-email.ts"
fake = Faker()


def _web_support_email(configured: str | None) -> str:
    env = {key: value for key, value in os.environ.items() if key != SUPPORT_EMAIL_ENV}
    if configured is not None:
        env[SUPPORT_EMAIL_ENV] = configured
    evaluated = subprocess.run(
        [
            "bun",
            "--no-env-file",
            "--eval",
            f'import {{ supportEmail }} from "./{WEB_OWNER}";'
            " console.log(JSON.stringify(supportEmail));",
        ],
        cwd=WEB_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert evaluated.returncode == 0, evaluated.stderr
    return json.loads(evaluated.stdout)


def _web_app_sources() -> list[Path]:
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", "web"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    return [
        ROOT / name
        for name in listed
        if name.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs"))
        and not name.startswith(("web/__tests__/", "web/e2e/"))
        and (ROOT / name).is_file()
    ]


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_web_fallback_is_the_api_support_address(configured: str | None) -> None:
    assert _web_support_email(configured) == SUPPORT_EMAIL_ADDRESS


def test_web_uses_the_configured_support_address() -> None:
    configured = fake.email()
    assert _web_support_email(configured) == configured


def test_release_profile_pins_the_api_support_address() -> None:
    # render.yaml is held to this profile by test_private_alpha_release_profile.py.
    profile_path = ROOT / ".github" / "private-alpha-release-profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    assert profile["services"]["web"]["env"][SUPPORT_EMAIL_ENV] == SUPPORT_EMAIL_ADDRESS


def test_only_the_web_owner_reads_the_support_address_setting() -> None:
    # Next inlines only the literal process.env name, so every working reader spells it.
    readers = sorted(
        path.relative_to(WEB_ROOT).as_posix()
        for path in _web_app_sources()
        if SUPPORT_EMAIL_ENV in path.read_text(encoding="utf-8")
    )
    assert readers == [WEB_OWNER]
