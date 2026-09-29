#!/usr/bin/env python3
"""Owned local Auth/Postgres setup, not an acceptance claim.

Usage: configure; start; api --python /absolute/python; seed; web.
Run api and web in separate tool-owned sessions; each execs its server in the
foreground. api --flag-off tests the API kill switch. web --production-check
builds and serves on 60419 after development has stopped. Stop retains volumes;
there is no reset command or application-process killer.

public_contract() is the non-secret endpoint contract for a future coordinated
cross-surface proof. Ignored client.json (0600) adds the local public Auth key
and A/B login credentials, never session tokens. runtime-receipts.jsonl records
process launches for externally controlled restart evidence. All migrations come
from the accepted backend commit, independently of uncommitted client work.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "web-accounts"
MIGRATION_SOURCE_HEAD = "296195e86c972e846c251d256b3cc211975bfd57"
API_PORT, APP_PORT, PRODUCTION_PORT = 60400, 3198, 60419
PORTS = {
    ("api", "port"): 60401,
    ("db", "port"): 60402,
    ("local_smtp", "port"): 60403,
    ("local_smtp", "smtp_port"): 60404,
    ("db", "shadow_port"): 60407,
    ("studio", "port"): 60408,
    ("db.pooler", "port"): 60409,
    ("analytics", "port"): 60410,
    ("edge_runtime", "inspector_port"): 60411,
}
EXCLUDE = (
    "vector,edge-runtime,imgproxy,studio,logflare,realtime,"
    "storage-api,postgres-meta,supavisor"
)
ENV_FILES = (
    ".env", ".env.local", ".env.development", ".env.development.local",
    ".env.production", ".env.production.local", ".env.test", ".env.test.local",
)


class HarnessError(RuntimeError):
    """An ownership or setup requirement was not satisfied."""


def origin(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def safe_environment() -> dict[str, str]:
    """Keep process plumbing only; discard inherited provider/app/proxy config."""
    keep = ("PATH", "HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "LC_ALL", "TERM")
    env = {key: os.environ[key] for key in keep if key in os.environ}
    env.update(
        SUPABASE_TELEMETRY_DISABLED="1", DO_NOT_TRACK="1",
        SUPABASE_NO_UPDATE_NOTIFIER="1", NEXT_TELEMETRY_DISABLED="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    return env


def require_free_ports(ports: list[int]) -> None:
    for port in ports:
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError as exc:
                raise HarnessError(f"Port {port} is occupied; stop nothing foreign.") from exc


def local_status(value: dict[str, Any]) -> dict[str, str]:
    required = ("API_URL", "DB_URL", "ANON_KEY", "SERVICE_ROLE_KEY", "JWT_SECRET")
    if any(not isinstance(value.get(key), str) or not value[key] for key in required):
        raise HarnessError("Local Supabase status is incomplete.")
    try:
        db = urlsplit(value["DB_URL"])
        valid_db = (
            db.scheme == "postgresql" and db.hostname == "127.0.0.1"
            and db.port == PORTS["db", "port"] and db.path == "/postgres"
            and not db.query and not db.fragment
        )
    except ValueError:
        valid_db = False
    if value["API_URL"] != origin(PORTS["api", "port"]) or not valid_db:
        raise HarnessError("Supabase status does not belong to the lane endpoints.")
    return {key: value[key] for key in required}


def render_config(source: str) -> str:
    section, redirects = "", False
    lines = []
    for line in source.splitlines():
        if redirects:
            redirects = line.strip() != "]"
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
                line = f"{name} = {PORTS[section, name]}"
            elif section == "auth" and name == "site_url":
                line = f'site_url = "{origin(APP_PORT)}"'
            elif section == "auth" and name == "additional_redirect_urls":
                redirects = line.rstrip().endswith("[")
                line = f'additional_redirect_urls = ["{origin(APP_PORT)}/auth/recovery"]'
            elif name == "enabled" and section in {
                "realtime", "studio", "storage", "edge_runtime", "analytics", "db.pooler"
            }:
                line = "enabled = false"
        if section == "local_smtp" and line.strip().startswith("# smtp_port ="):
            line = f"smtp_port = {PORTS['local_smtp', 'smtp_port']}"
        lines.append(line)
    return "\n".join(lines) + "\n"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise HarnessError("Local Auth request unexpectedly redirected.")


class LocalStack:
    def __init__(self, root: Path = ROOT) -> None:
        self.root = root.resolve()
        self.work = self.root / "temp/web-financial-accounts-local"
        self.stack = self.work / "stack"
        self.manifest = self.work / "manifest.json"
        self.client = self.work / "client.json"

    def run(self, argv: list[str]) -> bytes:
        result = subprocess.run(
            argv, cwd=self.root, env=safe_environment(), capture_output=True,
            check=False, timeout=300,
        )
        if result.returncode:
            raise HarnessError(f"{argv[0]} command failed; captured output suppressed.")
        return result.stdout

    def head(self) -> str:
        return self.run(["git", "rev-parse", "HEAD"]).decode().strip()

    def guard_root(self) -> None:
        actual = self.run(["git", "rev-parse", "--show-toplevel"]).decode().strip()
        if Path(actual).resolve() != self.root:
            raise HarnessError("Harness root is not the current repository root.")
        for parent in (self.root, self.root / "web", self.stack):
            for name in ENV_FILES:
                path = parent / name
                if path.exists() or path.is_symlink():
                    raise HarnessError("This harness refuses environment files or symlinks.")
        for path in (self.root / "temp", self.work, self.stack, self.stack / "supabase"):
            if path.is_symlink():
                raise HarnessError("The local stack path must not traverse a symlink.")
        linked = self.stack / "supabase/.temp/project-ref"
        if linked.exists() or linked.is_symlink():
            raise HarnessError("The local stack must not be linked to a hosted project.")

    def source_files(self) -> dict[str, bytes]:
        archive = self.run([
            "git", "archive", "--format=tar", MIGRATION_SOURCE_HEAD,
            "supabase/config.toml", "supabase/migrations", "supabase/seed.sql",
        ])
        files = {}
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            for member in bundle.getmembers():
                if member.isdir():
                    continue
                if not member.isfile() or ".." in Path(member.name).parts:
                    raise HarnessError("The landed schema contains a non-regular file.")
                stream = bundle.extractfile(member)
                assert stream is not None
                files[member.name] = stream.read()
        key = "supabase/config.toml"
        files[key] = render_config(files[key].decode()).encode()
        return files

    def resources(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for kind, args, name in (
            ("containers", ["ps", "-a"], "Names"),
            ("volumes", ["volume", "ls"], "Name"),
            ("networks", ["network", "ls"], "Name"),
        ):
            template = '{{.' + name + '}}\t{{.Label "com.supabase.cli.project"}}'
            rows = self.run(["docker", *args, "--format", template]).decode().splitlines()
            owned = []
            for row in rows:
                resource, _, project = row.partition("\t")
                if resource.endswith("_" + PROJECT) or project == PROJECT:
                    if project != PROJECT:
                        raise HarnessError("A lane resource name has a different owner label.")
                    owned.append(resource)
            result[kind] = sorted(owned)
        return result

    def write_json(self, path: Path, value: dict[str, Any]) -> None:
        if path.is_symlink():
            raise HarnessError("Refusing to replace a local fixture symlink.")
        with tempfile.NamedTemporaryFile(mode="w", dir=self.work, delete=False) as handle:
            temporary = Path(handle.name)
            os.chmod(temporary, 0o600)
            json.dump(value, handle, indent=2)
            handle.write("\n")
        os.replace(temporary, path)

    def read_json(self, path: Path) -> dict[str, Any]:
        if path.is_symlink() or not path.is_file():
            raise HarnessError("Expected a regular lane-local configuration file.")
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise HarnessError("Invalid lane-local configuration.")
        return value

    def validate(self) -> dict[str, Any]:
        self.guard_root()
        manifest = self.read_json(self.manifest)
        if (
            manifest.get("projectId") != PROJECT
            or manifest.get("repositoryRoot") != str(self.root)
            or manifest.get("migrationSourceHead") != MIGRATION_SOURCE_HEAD
        ):
            raise HarnessError("Local configuration belongs to a different project or root.")
        files = self.source_files()
        hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
        if manifest.get("files") != hashes:
            raise HarnessError("The configured schema differs from the landed source.")
        migrations = self.stack / "supabase/migrations"
        actual = {
            str(path.relative_to(self.stack)) for path in migrations.rglob("*")
            if path.is_file() or path.is_symlink()
        }
        if actual != {name for name in files if name.startswith("supabase/migrations/")}:
            raise HarnessError("The copied migration set has changed.")
        for name, data in files.items():
            path = self.stack / name
            if (
                path.is_symlink() or any(parent.is_symlink() for parent in path.parents)
                or not path.is_file() or path.read_bytes() != data
            ):
                raise HarnessError("Copied configuration bytes changed; do not reset this stack.")
        return manifest

    def configure(self) -> None:
        self.guard_root()
        if self.manifest.exists() or self.manifest.is_symlink():
            self.validate()
            print("Existing web-accounts configuration verified; nothing replaced.")
            return
        if self.work.exists() and any(self.work.iterdir()):
            raise HarnessError("The work directory is nonempty without an ownership manifest.")
        require_free_ports([APP_PORT, *range(API_PORT, PRODUCTION_PORT + 1)])
        if any(self.resources().values()):
            raise HarnessError("The web-accounts project name is already in use.")
        files = self.source_files()
        self.work.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.work.chmod(0o700)
        for name, data in files.items():
            path = self.stack / name
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.write_bytes(data)
        self.write_json(self.manifest, {
            "projectId": PROJECT, "repositoryRoot": str(self.root),
            "configuredHead": self.head(), "migrationSourceHead": MIGRATION_SOURCE_HEAD,
            "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
        })
        print("Configured web-accounts with only the accepted, landed migrations.")

    def supabase(self, *args: str) -> bytes:
        return self.run(["supabase", *args, "--workdir", str(self.stack)])

    def runtime_config(self) -> dict[str, str]:
        self.validate()
        if f"supabase_db_{PROJECT}" not in self.resources()["containers"]:
            raise HarnessError("The owned database container is absent; run start first.")
        return local_status(json.loads(self.supabase("status", "-o", "json")))

    def public_contract(self) -> dict[str, Any]:
        manifest = self.validate()
        return {
            "projectId": PROJECT, "repositoryRoot": str(self.root), "head": self.head(),
            "configuredHead": manifest["configuredHead"],
            "migrationSourceHead": MIGRATION_SOURCE_HEAD,
            "appURL": origin(APP_PORT), "apiURL": origin(API_PORT) + "/api/v1",
            "supabaseURL": origin(PORTS["api", "port"]),
            "databaseAddress": f"127.0.0.1:{PORTS['db', 'port']}",
            "mailURL": origin(PORTS["local_smtp", "port"]),
            "productionCheckURL": origin(PRODUCTION_PORT),
        }

    def start(self) -> None:
        self.validate()
        names = self.resources()["containers"]
        if names:
            running = self.run([
                "docker", "inspect", "--format", "{{.State.Running}}", *names,
            ]).decode().splitlines()
            if any(item == "true" for item in running):
                if not all(item == "true" for item in running):
                    raise HarnessError("Owned stack is partially running; inspect before restarting.")
                self.runtime_config()
                print("Owned Supabase is already serving; no containers restarted.")
                return
        require_free_ports(list(PORTS.values()))
        self.supabase("start", "-x", EXCLUDE)
        self.supabase("migration", "up", "--local")
        self.runtime_config()
        print("Owned Supabase started; landed migrations applied. Credentials suppressed.")

    def captcha_token(self) -> str:
        source = (self.root / "web/lib/guest-captcha.ts").read_text()
        match = re.search(r'export const LOCAL_QA_CAPTCHA_TOKEN = "([^"\n]+)";', source)
        if match is None:
            raise HarnessError("The canonical local CAPTCHA declaration changed.")
        return match[1]

    def request(self, path: str, payload: dict[str, Any] | None = None,
                token: str | None = None) -> dict[str, Any]:
        headers = {"Content-Type": "application/json", "Origin": origin(APP_PORT)}
        if token:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(
            origin(API_PORT) + "/api/v1/" + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=headers,
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(request, timeout=30) as response:
            return json.load(response)

    def seed(self) -> None:
        cfg = self.runtime_config()
        receipts = self.work / "runtime-receipts.jsonl"
        if not receipts.is_file() or receipts.is_symlink():
            raise HarnessError("Seed requires an API launched by this harness.")
        rows = [json.loads(line) for line in receipts.read_text().splitlines()]
        apis = [row for row in rows if row["action"] == "api"]
        listeners = self.run([
            "lsof", "-nP", f"-iTCP:{API_PORT}", "-sTCP:LISTEN", "-t",
        ]).decode().strip()
        if not apis or listeners != str(apis[-1]["pid"]):
            raise HarnessError("Seed requires the live API process launched by this harness.")
        contract = self.public_contract()
        if self.client.exists() or self.client.is_symlink():
            fixture = self.read_json(self.client)
            for key in ("projectId", "repositoryRoot", "apiURL", "supabaseURL"):
                if fixture.get(key) != contract[key]:
                    raise HarnessError("The client fixture belongs to a different stack.")
        else:
            fixture = {**contract, "publicAnonKey": cfg["ANON_KEY"], "users": [
                {"label": label,
                 "email": f"web-accounts-{label.lower()}-{secrets.token_hex(5)}@example.test",
                 "password": secrets.token_urlsafe(24), "id": None, "language": language}
                for label, language in (("A", "en"), ("B", "es-419"))
            ]}
            self.write_json(self.client, fixture)
        for user in fixture["users"]:
            login = {"email": user["email"], "password": user["password"],
                     "captcha_token": self.captcha_token()}
            try:
                session = self.request("auth/login", login)
            except urllib.error.HTTPError as exc:
                if exc.code != 401 or user["id"] is not None:
                    raise HarnessError("Synthetic login failed; response body suppressed.") from exc
                self.request("auth/signup", {
                    **login, "language": user["language"],
                    "display_name": "Local User " + user["label"],
                })
                session = self.request("auth/login", login)
            profile = self.request("me", token=session["session"]["access_token"])["user"]
            if user["id"] not in (None, profile["id"]) or profile["language"] != user["language"]:
                raise HarnessError("Synthetic user identity or language did not match.")
            user["id"] = profile["id"]
            self.write_json(self.client, fixture)
        print("Two synthetic users verified through /me; private client.json holds logins.")

    def backend_environment(self, cfg: dict[str, str], *, flag_off: bool) -> dict[str, str]:
        env = safe_environment()
        env.update({
            "PYTHONPATH": os.pathsep.join((str(self.root / "src"), str(self.root / "web"))),
            "APP_ENV": "development", "ARGUS_PERSISTENCE_MODE": "supabase",
            "ARGUS_CHECKPOINTER_MODE": "postgres", "ARGUS_DEV_MEMORY_FALLBACK": "false",
            "DATABASE_URL": cfg["DB_URL"],
            "SUPABASE_POSTGRES_SESSION_POOLER_URL": cfg["DB_URL"],
            "SUPABASE_PROJECT_URL": cfg["API_URL"], "SUPABASE_URL": cfg["API_URL"],
            "SUPABASE_ANON_PUBLIC_KEY": cfg["ANON_KEY"], "SUPABASE_ANON_KEY": cfg["ANON_KEY"],
            "SUPABASE_SERVICE_ROLE_KEY": cfg["SERVICE_ROLE_KEY"],
            "SUPABASE_JWT_SECRET": cfg["JWT_SECRET"],
            "ARGUS_FINANCIAL_ACCOUNTS_ENABLED": "false" if flag_off else "true",
            "ARGUS_MOCK_AUTH": "false", "NEXT_PUBLIC_MOCK_AUTH": "false",
            "ARGUS_GUEST_ACCESS_ENABLED": "true", "ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED": "true",
            "ARGUS_APP_ORIGIN": origin(APP_PORT),
            "ARGUS_CORS_ALLOW_ORIGINS": ",".join(map(origin, (APP_PORT, PRODUCTION_PORT))),
            "ARGUS_MARKET_DATA_PROVIDER_MODE": "synthetic_unit_fixture",
        })
        for key in (
            "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED", "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED",
            "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED", "ARGUS_CONTEXT_PACKETS_ENABLED",
            "ARGUS_TITLE_AUTOGEN_ENABLED", "ARGUS_RESEARCH_RAIL_ENABLED",
            "ARGUS_ENABLE_PERSONALIZATION_MEMORY", "ARGUS_ENABLE_MEMORY_SEMANTIC_RECALL",
        ):
            env[key] = "false"
        return env

    def receipt(self, action: str, port: int, **extra: Any) -> None:
        row = {**self.public_contract(), "action": action, "pid": os.getpid(), "port": port,
               "startedAt": datetime.now(timezone.utc).isoformat(), **extra}
        path = self.work / "runtime-receipts.jsonl"
        descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "a") as handle:
            handle.write(json.dumps(row) + "\n")

    def api(self, python: str, *, flag_off: bool) -> None:
        if not Path(python).is_absolute() or not Path(python).is_file():
            raise HarnessError("--python must name an existing absolute interpreter path.")
        cfg = self.runtime_config()
        require_free_ports([API_PORT])
        env = self.backend_environment(cfg, flag_off=flag_off)
        self.receipt("api", API_PORT, financialAccountsEnabled=not flag_off)
        os.chdir(self.root)
        os.execve(python, [python, "-m", "uvicorn", "argus.api.main:app", "--host",
                           "127.0.0.1", "--port", str(API_PORT), "--no-access-log"], env)

    def web(self, *, production_check: bool) -> None:
        cfg = self.runtime_config()
        # Both modes share the canonical ignored .next directory. Serialize them.
        require_free_ports([APP_PORT, PRODUCTION_PORT])
        port = PRODUCTION_PORT if production_check else APP_PORT
        env = safe_environment()
        env.update({
            "NEXT_PUBLIC_SUPABASE_URL": cfg["API_URL"],
            "NEXT_PUBLIC_SUPABASE_ANON_KEY": cfg["ANON_KEY"],
            "NEXT_PUBLIC_ARGUS_API_URL": origin(API_PORT) + "/api/v1",
            "ARGUS_APP_ORIGIN": origin(port),
            "NEXT_PUBLIC_ARGUS_LOCAL_QA_CAPTCHA_TOKEN": self.captcha_token(),
            "NEXT_PUBLIC_MOCK_AUTH": "false", "NEXT_PUBLIC_MOCK_API": "false",
            "NEXT_PUBLIC_GUEST_ACCESS_ENABLED": "true", "NEXT_PUBLIC_ENABLE_SPANISH": "true",
            "NEXT_PUBLIC_CHAT_EXPLORATORY_SUGGESTIONS_ENABLED": "false",
            "NEXT_PUBLIC_POSTHOG_KEY": "", "NEXT_PUBLIC_ARGUS_TURNSTILE_SITE_KEY": "",
        })
        binary = shutil.which("bun", path=env.get("PATH"))
        if binary is None or not (self.root / "web/node_modules/next/package.json").is_file():
            raise HarnessError("Bun and installed web dependencies are required.")
        os.chdir(self.root / "web")
        if production_check:
            subprocess.run([binary, "run", "build", "--webpack"], env=env, check=True)
            require_free_ports([APP_PORT, PRODUCTION_PORT])
        self.receipt("web", port, productionCheck=production_check)
        args = [binary, "run", "start" if production_check else "dev"]
        if not production_check:
            args.append("--webpack")
        os.execve(binary, [*args, "--hostname", "127.0.0.1", "--port", str(port)], env)

    def stop(self) -> None:
        self.validate()
        self.resources()
        self.supabase("stop", "--project-id", PROJECT)
        print("Stopped only web-accounts Supabase; database volumes retained.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("configure", "start", "seed", "api", "web", "status", "stop"))
    parser.add_argument("--python", help="Dependency-complete, absolute Python interpreter")
    parser.add_argument("--flag-off", action="store_true", help="API exposure check")
    parser.add_argument("--production-check", action="store_true", help="Build and serve on 60419")
    args = parser.parse_args()
    stack = LocalStack()
    if args.flag_off and args.action != "api":
        parser.error("--flag-off belongs to api")
    if args.production_check and args.action != "web":
        parser.error("--production-check belongs to web")
    if args.action == "api":
        if not args.python:
            parser.error("api requires --python")
        stack.api(args.python, flag_off=args.flag_off)
    elif args.action == "web":
        stack.web(production_check=args.production_check)
    elif args.action == "status":
        print(json.dumps({**stack.public_contract(), "containers": stack.resources()["containers"]}, indent=2))
    else:
        getattr(stack, args.action)()


if __name__ == "__main__":
    try:
        main()
    except HarnessError as error:
        raise SystemExit(str(error)) from None
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        raise SystemExit(f"Local harness failed ({type(error).__name__}); private output suppressed.") from None
