from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_MODULE_PREFIXES = (
    "pandas",
    "vectorbt",
    "vectorbtpro",
    "numba",
    "scipy",
    "argus.analysis",
    "argus.domain.engine",
    "argus.domain.backtesting",
    "argus.domain.engine_launch.adapter",
)


def test_api_startup_health_does_not_import_backtest_compute_stack() -> None:
    result = _run_import_probe()
    assert result["health_status_code"] == 200
    assert result["health_body"]["status"] == "healthy"
    assert result["forbidden_loaded"] == []


def test_api_import_probe_reports_memory_smoke() -> None:
    result = _run_import_probe()
    rss = result["rss_mb"]

    assert rss["baseline"] > 0
    assert rss["after_import"] >= rss["baseline"]
    assert rss["after_health"] >= rss["after_import"]

    print(
        "api import rss smoke: "
        f"baseline={rss['baseline']:.1f} MB "
        f"after_import={rss['after_import']:.1f} MB "
        f"after_health={rss['after_health']:.1f} MB"
    )


def _run_import_probe() -> dict[str, Any]:
    env = os.environ.copy()
    env.update(
        {
            "ARGUS_PERSISTENCE_MODE": "memory",
            "ARGUS_CHECKPOINTER_MODE": "memory",
            "ARGUS_DEV_MEMORY_FALLBACK": "true",
            "ARGUS_MOCK_AUTH": "true",
            "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED": "true",
            "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED": "true",
            "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED": "true",
            "ARGUS_MARKET_DATA_PROVIDER_MODE": "synthetic_unit_fixture",
            "PYTHONPATH": str(REPO_ROOT / "src"),
        }
    )
    completed = subprocess.run(
        [sys.executable, "-c", _IMPORT_PROBE_SCRIPT],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


_IMPORT_PROBE_SCRIPT = textwrap.dedent(
    f"""
    import json
    import resource
    import sys


    FORBIDDEN_MODULE_PREFIXES = {FORBIDDEN_MODULE_PREFIXES!r}


    def rss_mb():
        raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if raw > 10_000_000:
            return raw / (1024 * 1024)
        return raw / 1024


    def forbidden_loaded():
        loaded = []
        for name in sys.modules:
            for prefix in FORBIDDEN_MODULE_PREFIXES:
                if name == prefix or name.startswith(prefix + "."):
                    loaded.append(name)
                    break
        return sorted(loaded)


    baseline = rss_mb()
    from argus.api.main import app

    after_import = rss_mb()
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        response = client.get("/health")
        health_status_code = response.status_code
        health_body = response.json()

    after_health = rss_mb()
    print(
        json.dumps(
            {{
                "rss_mb": {{
                    "baseline": baseline,
                    "after_import": after_import,
                    "after_health": after_health,
                }},
                "health_status_code": health_status_code,
                "health_body": health_body,
                "forbidden_loaded": forbidden_loaded(),
            }},
            sort_keys=True,
        )
    )
    """
)
