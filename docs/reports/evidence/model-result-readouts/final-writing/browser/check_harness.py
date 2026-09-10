"""Free data/receipt boundary checks. No Argus import, servers or network."""

import copy
import json
import tempfile
from pathlib import Path

from replay_data import digest, draft_prose, load_inputs, source_numbers, synthetic_report

root = Path.cwd()
report = synthetic_report(root)
assert (
    draft_prose('{"language":"en","text":"Rejected **complete** text","figures":[]}')
    == "Rejected **complete** text"
)
assert draft_prose("Malformed raw draft") == "Malformed raw draft"
assert draft_prose('{"text":null}') is None
assert draft_prose(None) is None
with tempfile.TemporaryDirectory(prefix="final-writing-schema-") as temporary:
    path = Path(temporary) / "SYNTHETIC-preflight.json"
    path.write_text(json.dumps(report))
    inputs = load_inputs(root, path, synthetic=True)
    assert len(inputs["pairs"]) == 6
    assert sum(len(pair["outcomes"]) for pair in inputs["pairs"]) == 12
    assert (
        sum(
            item["accepted"]
            for pair in inputs["pairs"]
            for item in pair["outcomes"].values()
        )
        == 6
    )
    for pair in inputs["pairs"]:
        assert source_numbers(pair["run"])
        assert digest(root / pair["source_path"]) == pair["source"]["sha256"]

    mutations = {
        "fixture_hash": lambda value: value.update(fixture_sha256="incorrect"),
        "row_missing": lambda value: value["results"].pop(),
        "wrong_tier": lambda value: value["results"][0].update(variant="current"),
        "accepted_fallback_conflict": lambda value: value["results"][0][
            "quick_take"
        ].update(fallback_used=True),
        "partial_accept": lambda value: value["results"][0]["quick_take"].update(
            complete_text="partial"
        ),
        "extra_attempt": lambda value: value["results"][0].update(
            requests=[{"task": "result_summary"}, {"task": "result_summary"}]
        ),
    }
    for name, mutate in mutations.items():
        bad = copy.deepcopy(report)
        mutate(bad)
        path.write_text(json.dumps(bad))
        try:
            load_inputs(root, path, synthetic=True)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Boundary did not reject {name}")
    path.write_text(json.dumps(report))
    try:
        load_inputs(root, path, synthetic=False)
    except ValueError:
        pass
    else:
        raise AssertionError("Synthetic report was mistaken for provider evidence")
    actual_like = copy.deepcopy(report)
    actual_like.pop("synthetic_browser_preflight")
    actual_like.update(
        evaluation_mode="live_targeted",
        comparison_mode="writing",
        scheduled_task_completions=12,
        budget={"max_attempts_per_task": 1},
    )
    for row in actual_like["results"]:
        row["configuration"] = {"single_attempt": True}
    path.write_text(json.dumps(actual_like))
    assert len(load_inputs(root, path)["pairs"]) == 6
    actual_mutations = {
        "free_preflight": lambda value: value.update(
            evaluation_mode="preflight_no_calls"
        ),
        "wrong_comparison": lambda value: value.update(comparison_mode="tiers"),
        "wrong_task_count": lambda value: value.update(scheduled_task_completions=96),
        "retry_configuration": lambda value: value["budget"].update(
            max_attempts_per_task=2
        ),
        "missing_frame": lambda value: value["results"][0].pop("quick_take"),
    }
    for name, mutate in actual_mutations.items():
        bad = copy.deepcopy(actual_like)
        mutate(bad)
        path.write_text(json.dumps(bad))
        try:
            load_inputs(root, path)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Actual-proof boundary did not reject {name}")
print(
    json.dumps(
        {
            "status": "passed",
            "synthetic_rows": 6,
            "synthetic_frame_outcomes": 12,
            "invalid_input_checks": len(mutations) + len(actual_mutations) + 1,
            "source_fixtures_unchanged": True,
            "raw_draft_extraction_checks": 4,
            "servers_started": 0,
            "provider_calls": 0,
            "backtests": 0,
        }
    )
)
