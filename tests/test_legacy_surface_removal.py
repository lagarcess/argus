from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RETIRED_ENV_KEYS = {
    "ARGUS_STRATEGIES_ENABLED",
    "NEXT_PUBLIC_STRATEGIES_ENABLED",
    "NEXT_PUBLIC_COLLECTIONS_ENABLED",
}


def test_legacy_strategy_and_collection_routes_are_absent() -> None:
    openapi = yaml.safe_load(
        (ROOT / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8")
    )

    paths = openapi["paths"]
    assert not any(path.startswith("/api/v1/strategies") for path in paths)
    assert not any(path.startswith("/api/v1/collections") for path in paths)
    assert not (ROOT / "src" / "argus" / "api" / "routers" / "strategies.py").exists()
    assert not (ROOT / "src" / "argus" / "api" / "routers" / "collections.py").exists()


def test_legacy_rows_keep_read_compatibility_without_write_routes() -> None:
    schemas = (ROOT / "src" / "argus" / "api" / "schemas.py").read_text(
        encoding="utf-8"
    )
    history_reader = (
        ROOT / "src" / "argus" / "domain" / "postgres_history_reader.py"
    ).read_text(encoding="utf-8")
    gateway = (
        ROOT / "src" / "argus" / "domain" / "supabase_gateway.py"
    ).read_text(encoding="utf-8")

    assert "class Strategy(BaseModel):" in schemas
    assert "class Collection(BaseModel):" in schemas
    assert "strategy_id: str | None = None" in schemas
    assert "from public.strategies as strategy" in history_reader
    assert "from public.collections as collection" in history_reader
    assert "def get_strategy(" in gateway


def test_retired_env_keys_are_absent_from_the_release_contract() -> None:
    profile = json.loads(
        (ROOT / ".github" / "private-alpha-release-profile.json").read_text(
            encoding="utf-8"
        )
    )
    contract_files = (
        ROOT / ".env.example",
        ROOT / "web" / ".env.local.example",
        ROOT / "render.yaml",
        ROOT / ".github" / "argus-env.sh",
        ROOT / ".github" / "local-smoke.sh",
        ROOT / "scripts" / "qa" / "write-local-env.sh",
        ROOT / "scripts" / "qa" / "run-guest-experience-qa.sh",
    )

    for path in contract_files:
        text = path.read_text(encoding="utf-8")
        for key in RETIRED_ENV_KEYS:
            assert key not in text

    serialized_profile = json.dumps(profile, sort_keys=True)
    for key in RETIRED_ENV_KEYS:
        assert key not in serialized_profile


def test_live_asset_provider_override_remains_untouched() -> None:
    assets = (
        ROOT / "src" / "argus" / "domain" / "market_data" / "assets.py"
    ).read_text(encoding="utf-8")

    assert "ARGUS_ASSET_PROVIDER_MODE" in assets
    assert "ARGUS_MARKET_DATA_PROVIDER_MODE" in assets
