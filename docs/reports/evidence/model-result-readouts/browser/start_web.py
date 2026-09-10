"""Start an isolated readout replay frontend with explicit non-secret env."""

import os
import subprocess
from pathlib import Path

import dotenv

environment = dict(os.environ)
# Never print dotenv values. Explicit empties prevent linked files supplying a
# credential even if Next's dotenv loading behavior changes.
for path in [Path(".env"), Path("web/.env"), Path("web/.env.local")]:
    if path.exists():
        for key in dotenv.dotenv_values(path):
            environment[key] = ""
for key in tuple(environment):
    if any(part in key.upper() for part in ("KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL", "DATABASE", "SUPABASE", "POSTHOG", "ALPACA", "OPENROUTER")):
        environment[key] = ""
environment.update({
    "__NEXT_PROCESSED_ENV": "true",
    "NEXT_DIST_DIR": ".next-readout-replay",
    "NEXT_PUBLIC_MOCK_AUTH": "true",
    "NEXT_PUBLIC_ENABLE_SPANISH": "true",
    "NEXT_PUBLIC_GUEST_ACCESS_ENABLED": "false",
    "NEXT_PUBLIC_ARGUS_API_URL": "http://127.0.0.1:8539/api/v1",
    "NEXT_PUBLIC_SUPABASE_URL": "",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY": "",
    "NEXT_TELEMETRY_DISABLED": "1",
})
subprocess.run(["bun", "run", "dev", "--hostname", "127.0.0.1", "--port", "3219"], cwd="web", env=environment, check=True)
