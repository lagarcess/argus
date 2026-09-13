"""Validate this rendered-fixture archive without writes or network access."""

import hashlib
import json
import subprocess
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / "browser-manifest.json").read_text())
PROVENANCE = json.loads((ROOT / "provenance.json").read_text())


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


files = {
    str(path.relative_to(ROOT)): sha256(path.read_bytes())
    for path in ROOT.rglob("*")
    if path.is_file() and path.name != "browser-manifest.json"
}
assert files == MANIFEST["archived_file_sha256"], "Archived file hashes differ"
assert MANIFEST["source_sha"] == PROVENANCE["source_sha"]
for path, expected in PROVENANCE["source_files"].items():
    content = subprocess.check_output(
        ["git", "show", f'{MANIFEST["source_sha"]}:{path}']
    )
    assert sha256(content) == expected, path
for path, expected in PROVENANCE["fixture_files"].items():
    assert files[path] == expected, path

for run_name, expected_cases in (("coherent_full_matrix", 16),):
    run = MANIFEST["runs"][run_name]
    report = json.loads((ROOT / run["report"]).read_text())
    assert report["stats"] == run["stats"]
    assert report["stats"]["expected"] == expected_cases
    assert all(report["stats"][key] == 0 for key in ("skipped", "unexpected", "flaky"))
    network = [
        json.loads(path.read_text())
        for path in (ROOT / run["network_logs"]).glob("*.json")
    ]
    assert len(network) == expected_cases
    assert sum(len(case["requests"]) for case in network) == run["observed_mocked_api_requests"]
    for case in network:
        assert case["status"] == "passed", case["title"]
        assert not any(case[key] for key in ("external", "unhandledApi", "pageErrors"))

ledger = json.loads((ROOT / "fixture-coherence.json").read_text())
backtests = json.loads((ROOT / "backtest-cards.json").read_text())
signals = json.loads((ROOT / "signal-cards.json").read_text())
for template, cards in (
    ("dca_accumulation", {locale: entry["card"] for locale, entry in backtests.items()}),
    ("signal_strategy", signals["cards"]),
):
    facts = ledger[template]
    principal = Decimal(str(facts["principal"]))
    profit = principal * Decimal(str(facts["net_return_pct"])) / 100
    assert profit == Decimal(str(facts["profit"]))
    assert principal + profit == Decimal(str(facts["ending_value"]))
    for locale, card in cards.items():
        presentation = card["presentation"]
        rows = {row["name"]: row["value"] for row in presentation["rows"]}
        assert rows["cash_value"] == facts["cash_value_by_locale"][locale]
        assert presentation["answer"]["value"] == f'{facts["net_return_pct"]:+.1f}%'
        chart = presentation["visual"]
        assert chart["base_value"] == chart["series"][0]["value"] == facts["chart_start_value"]
        assert chart["series"][-1]["value"] == facts["ending_value"]
        assert chart["series"][0]["time"] == rows["start_date"] == facts["chart_start_date"]
        assert chart["series"][-1]["time"] == rows["end_date"] == facts["chart_end_date"]

assert len(MANIFEST["screenshots"]) == 14
for screenshot in MANIFEST["screenshots"]:
    assert files[screenshot["path"]] == screenshot["sha256"]
    assert screenshot["visually_inspected"] is True
assert PROVENANCE["generator_network_attempts"] == 0
assert all(
    MANIFEST[key] == 0
    for key in ("provider_calls", "interpreter_calls", "backtest_handler_calls", "real_api_calls", "paid_spend_usd")
)
print(json.dumps({
    "source_sha": MANIFEST["source_sha"],
    "verified_archived_files": len(files),
    "unique_cases": 16,
    "selected_run": "coherent_full_matrix",
    "coherent_dca_and_signal_fixtures": True,
    "inspected_images": 14,
    "external_requests": 0,
    "unhandled_api_requests": 0,
    "page_errors": 0,
    "result": "pass",
}, indent=2))
