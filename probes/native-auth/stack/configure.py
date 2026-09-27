"""Write a disposable Supabase config for the native auth proof.

The repository's supabase/ directory is copied, never edited. The copy gets its
own project id and port range so it cannot collide with another lane's stack,
and `supabase stop --no-backup` on it deletes only volumes it created.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ID = "argus-native-auth-proof"
PORTS = {
    ("api", "port"): 57451,
    ("db", "port"): 57452,
    ("db", "shadow_port"): 57450,
    ("db.pooler", "port"): 57459,
    ("studio", "port"): 57453,
    ("local_smtp", "port"): 57454,
    ("analytics", "port"): 57457,
    ("edge_runtime", "inspector_port"): 8113,
}
# Synthetic custom scheme for simulator callback handling. Not a production
# identifier; a hosted allowlist entry needs the real bundle id or domain.
NATIVE_CALLBACK = "argusnativeproof://auth-callback"
# Cloudflare's published Turnstile test secrets. They are public test values:
# 1x... always passes, 2x... always fails. See the report for the source.
TURNSTILE_TEST_SECRETS = {
    "turnstile-pass": "1x0000000000000000000000000000000AA",
    "turnstile-fail": "2x0000000000000000000000000000000AA",
}
AUTH_OVERRIDES = {
    ("auth", "jwt_expiry"): "60",
    ("auth.email", "enable_confirmations"): "true",
}


def rewrite(text: str, captcha: str) -> str:
    section = ""
    out: list[str] = []
    for line in text.splitlines():
        header = re.match(r"^\[([^\]]+)\]\s*$", line)
        if header:
            section = header.group(1)
        key_match = re.match(r"^(\w+)\s*=", line)
        key = key_match.group(1) if key_match else None
        if section == "" and key == "project_id":
            line = f'project_id = "{PROJECT_ID}"'
        elif key and (section, key) in PORTS:
            line = f"{key} = {PORTS[(section, key)]}"
        elif key and (section, key) in AUTH_OVERRIDES:
            line = f"{key} = {AUTH_OVERRIDES[(section, key)]}"
        elif section == "auth" and key == "additional_redirect_urls":
            line = f'additional_redirect_urls = [\n  "{NATIVE_CALLBACK}",'
        out.append(line)
    config = "\n".join(out) + "\n"
    if captcha != "off":
        config += (
            "\n[auth.captcha]\n"
            "enabled = true\n"
            'provider = "turnstile"\n'
            f'secret = "{TURNSTILE_TEST_SECRETS[captcha]}"\n'
        )
    return config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stack_dir", type=Path)
    parser.add_argument(
        "--captcha",
        choices=("off", *TURNSTILE_TEST_SECRETS),
        default="off",
    )
    args = parser.parse_args()
    target = args.stack_dir / "supabase"
    if target.exists():
        shutil.rmtree(target / "migrations", ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(REPO_ROOT / "supabase" / "migrations", target / "migrations")
    shutil.copy2(REPO_ROOT / "supabase" / "seed.sql", target / "seed.sql")
    source = (REPO_ROOT / "supabase" / "config.toml").read_text()
    (target / "config.toml").write_text(rewrite(source, args.captcha))
    print(f"configured {PROJECT_ID} at {target} (captcha={args.captcha})")


if __name__ == "__main__":
    main()
