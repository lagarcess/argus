"""Lane-owned synthetic stack setup. Does not read a hosted .env or print credentials."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "ios/.build/auth-local"
STACK = WORK / "stack"
PROJECT = "ios-auth-8be2"
PORTS = {
    ("api", "port"): 58401,
    ("db", "port"): 58402,
    ("local_smtp", "port"): 58403,
    ("local_smtp", "smtp_port"): 58404,
    ("db", "shadow_port"): 58407,
    ("studio", "port"): 58408,
    ("db.pooler", "port"): 58409,
    ("analytics", "port"): 58410,
    ("edge_runtime", "inspector_port"): 58411,
}
EXCLUDE = "vector,edge-runtime,imgproxy,studio,logflare,realtime,storage-api,postgres-meta,supavisor"


def sb(*args: str, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["supabase", *args, "--workdir", str(STACK)],
        check=True,
        capture_output=capture,
        text=True,
    )


def configure() -> None:
    if (STACK / "supabase/config.toml").exists():
        raise SystemExit("Configuration exists. Reuse it; do not reset an active stack.")
    for port in [58400, 58405, 3001, *PORTS.values()]:
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                raise SystemExit(
                    f"Port {port} is occupied. Coordinate a new allocation; stop nothing."
                ) from None
    target = STACK / "supabase"
    target.mkdir(parents=True, mode=0o700)
    shutil.copytree(ROOT / "supabase/migrations", target / "migrations")
    shutil.copy2(ROOT / "supabase/seed.sql", target / "seed.sql")
    section = ""
    lines = []
    redirects = False
    for line in (ROOT / "supabase/config.toml").read_text().splitlines():
        if redirects:
            if line.strip() == "]":
                redirects = False
            continue
        match = re.match(r"^\[([^\]]+)\]", line)
        if match:
            section = match[1]
        key = re.match(r"^(\w+)\s*=", line)
        if key:
            name = key[1]
            if not section and name == "project_id":
                line = f'project_id = "{PROJECT}"'
            elif (section, name) in PORTS:
                line = f"{name} = {PORTS[section,name]}"
            elif section == "auth" and name == "site_url":
                line = 'site_url = "http://127.0.0.1:3001"'
            elif section == "auth" and name == "additional_redirect_urls":
                line = (
                    'additional_redirect_urls = ["http://127.0.0.1:3001/auth/recovery"]'
                )
                redirects = True
            elif section == "auth" and name == "jwt_expiry":
                line = "jwt_expiry = 60"
            elif section == "auth.email" and name == "enable_confirmations":
                line = "enable_confirmations = true"
        if section == "local_smtp" and line.strip().startswith("# smtp_port ="):
            line = "smtp_port = 58404"
        lines.append(line)
    # Public Cloudflare always-pass test secret; local container only.
    lines += [
        "",
        "[auth.captcha]",
        "enabled = true",
        'provider = "turnstile"',
        'secret = "1x0000000000000000000000000000000AA"',
    ]
    (target / "config.toml").write_text("\n".join(lines) + "\n")
    print("Configured isolated ios-auth-8be2 stack, ports 58401-58411.")


def status() -> dict:
    result = json.loads(sb("status", "-o", "json").stdout)
    if result["API_URL"] != "http://127.0.0.1:58401":
        raise SystemExit("Refusing non-lane Supabase endpoint")
    return result


def seed() -> None:
    cfg = status()
    path = WORK / "client.json"
    if path.exists():
        raise SystemExit(
            "Synthetic client fixture already exists; reuse, do not mint accounts repeatedly."
        )
    users = []
    for label in ("a", "b"):
        email = f"ios-{label}-{secrets.token_hex(5)}@example.test"
        password = secrets.token_urlsafe(24)
        data = json.dumps(
            {"email": email, "password": password, "email_confirm": True}
        ).encode()
        req = urllib.request.Request(
            cfg["API_URL"] + "/auth/v1/admin/users",
            data=data,
            headers={
                "apikey": cfg["SERVICE_ROLE_KEY"],
                "Authorization": "Bearer " + cfg["SERVICE_ROLE_KEY"],
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req) as response:
            user = json.load(response)
        users.append({"email": email, "password": password, "id": user["id"]})
    fixture = {
        "apiURL": "http://127.0.0.1:58400/api/v1",
        "supabaseURL": cfg["API_URL"],
        "publicAnonKey": cfg["ANON_KEY"],
        "users": users,
    }
    path.write_text(json.dumps(fixture))
    path.chmod(0o600)

    # xcconfig treats // as a comment; use its empty-variable escape.
    def url(value: str) -> str:
        return value.replace("://", ":/$()/")

    config = ROOT / "ios/Config/Local.xcconfig"
    if config.exists():
        raise SystemExit(
            "Local.xcconfig exists; synthetic fixture saved, leaving config untouched."
        )
    config.write_text(
        "\n".join(
            [
                "// Ignored local synthetic stack; public configuration only.",
                "ARGUS_AUTH_ENABLED = true",
                "ARGUS_API_URL = " + url("http://127.0.0.1:58400"),
                "ARGUS_SUPABASE_URL = " + url(cfg["API_URL"]),
                "ARGUS_SUPABASE_ANON_KEY = " + cfg["ANON_KEY"],
                "ARGUS_WEB_URL = " + url("http://127.0.0.1:3001"),
                "ARGUS_CAPTCHA_URL = " + url("http://127.0.0.1:58405/captcha.html"),
            ]
        )
        + "\n"
    )
    print(
        "Created two synthetic users and ignored client fixture/config. No secrets printed."
    )


def api(python: str) -> None:
    cfg = status()
    env = {
        key: value
        for key, value in os.environ.items()
        if not any(
            x in key
            for x in (
                "TOKEN",
                "SECRET",
                "API_KEY",
                "SUPABASE",
                "DATABASE",
                "ARGUS_",
                "SENTRY",
                "POSTHOG",
            )
        )
    }
    env.update(
        {
            "PYTHONPATH": str(ROOT / "src") + ":" + str(ROOT / "web"),
            "SUPABASE_PROJECT_URL": cfg["API_URL"],
            "SUPABASE_URL": cfg["API_URL"],
            "SUPABASE_ANON_PUBLIC_KEY": cfg["ANON_KEY"],
            "SUPABASE_ANON_KEY": cfg["ANON_KEY"],
            "SUPABASE_SERVICE_ROLE_KEY": cfg["SERVICE_ROLE_KEY"],
            "SUPABASE_JWT_SECRET": cfg["JWT_SECRET"],
            "SUPABASE_POSTGRES_SESSION_POOLER_URL": cfg["DB_URL"],
            "DATABASE_URL": cfg["DB_URL"],
            "ARGUS_PERSISTENCE_MODE": "supabase",
            "ARGUS_MARKET_DATA_PROVIDER_MODE": "synthetic_unit_fixture",
            "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED": "false",
            "ARGUS_GUEST_ACCESS_ENABLED": "true",
            "ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED": "true",
            "ARGUS_MOCK_AUTH": "false",
            "NEXT_PUBLIC_MOCK_AUTH": "false",
            "ARGUS_APP_ORIGIN": "http://127.0.0.1:3001",
        }
    )
    for key in (
        "ALPACA_API_KEY",
        "ALPACA_SECRET_KEY",
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "RESEND_API_KEY",
        "PERPLEXITY_API_KEY",
        "EXA_API_KEY",
        "POSTHOG_API_KEY",
        "SENTRY_DSN",
    ):
        env[key] = ""
    # No .env in this checkout; explicit env is the only local runtime source.
    if (ROOT / ".env").exists():
        raise SystemExit(
            "Refusing a checkout with a root .env; isolate runtime configuration first."
        )
    os.chdir(ROOT)
    os.execve(
        python,
        [
            python,
            "-m",
            "uvicorn",
            "argus.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "58400",
            "--no-access-log",
        ],
        env,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=["configure", "start", "seed", "api", "web", "stop"]
    )
    parser.add_argument(
        "--python", help="Absolute path to a dependency-complete Python runtime"
    )
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True, mode=0o700)
    if args.action == "configure":
        configure()
    elif args.action == "start":
        with (WORK / "supabase-start.log").open("w") as log:
            subprocess.run(
                ["supabase", "start", "-x", EXCLUDE, "--workdir", str(STACK)],
                stdout=log,
                stderr=log,
                check=True,
            )
        print("Lane Supabase started. Detailed output is ignored local evidence.")
    elif args.action == "seed":
        seed()
    elif args.action == "api":
        if not args.python or not Path(args.python).is_absolute():
            raise SystemExit("--python must be an absolute interpreter path")
        api(args.python)
    elif args.action == "web":
        cfg = status()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 3001))
        env = dict(os.environ)
        env.update(
            {
                "NEXT_PUBLIC_SUPABASE_URL": cfg["API_URL"],
                "NEXT_PUBLIC_SUPABASE_ANON_KEY": cfg["ANON_KEY"],
                "NEXT_PUBLIC_ARGUS_API_URL": "http://127.0.0.1:58400/api/v1",
                "ARGUS_APP_ORIGIN": "http://127.0.0.1:3001",
                "NEXT_PUBLIC_ARGUS_TURNSTILE_SITE_KEY": "1x00000000000000000000AA",
                "NEXT_PUBLIC_ARGUS_LOCAL_QA_CAPTCHA_TOKEN": "",
                "NEXT_PUBLIC_MOCK_AUTH": "false",
                "NEXT_PUBLIC_MOCK_API": "false",
                "NEXT_PUBLIC_GUEST_ACCESS_ENABLED": "true",
                "NEXT_DIST_DIR": ".next-ios-auth",
            }
        )
        if (ROOT / "web/.env.local").exists():
            raise SystemExit("Refusing preexisting web .env.local")
        os.chdir(ROOT / "web")
        binary = shutil.which("bun")
        os.execve(
            binary,
            [binary, "run", "dev", "--hostname", "127.0.0.1", "--port", "3001"],
            env,
        )
    elif args.action == "stop":
        if (
            f'project_id = "{PROJECT}"'
            not in (STACK / "supabase/config.toml").read_text()
        ):
            raise SystemExit("Stack ownership mismatch")
        sb("stop")
        print("Stopped only ios-auth-8be2; local data retained.")
