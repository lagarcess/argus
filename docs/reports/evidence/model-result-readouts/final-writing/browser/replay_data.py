"""Read final writing outcomes without invoking Argus or any provider."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

SURFACES = {"quick_take": "result_summary", "breakdown": "result_breakdown"}
FRAME_PROVIDERS = {"quick_take": "openrouter", "breakdown": "perplexity_agent"}
EVIDENCE = Path("docs/reports/evidence/model-result-readouts")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def draft_prose(raw: Any) -> str | None:
    """Extract a complete diagnostic body without making it accepted content."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except ValueError:
        return raw
    text = parsed.get("text") if isinstance(parsed, dict) else parsed
    return text if isinstance(text, str) and text.strip() else None


def load_inputs(root: Path, report_path: Path, synthetic: bool = False) -> dict[str, Any]:
    fixture_path = root / EVIDENCE / "recorded-fixtures.json"
    fixtures = json.loads(fixture_path.read_text())
    report = json.loads(report_path.read_text())
    if report.get("fixture_sha256") != digest(fixture_path):
        raise ValueError("report_fixture_hash_mismatch")
    if bool(report.get("synthetic_browser_preflight")) != synthetic:
        raise ValueError("synthetic_mode_must_be_explicit")
    if not synthetic and (
        report.get("evaluation_mode") != "live_targeted"
        or report.get("comparison_mode") != "luna"
        or report.get("scheduled_task_completions") != 12
        or report.get("budget", {}).get("max_attempts_per_task") != 1
    ):
        raise ValueError("completed_single_attempt_luna_measurement_required")
    cases = {case["id"]: case for case in fixtures["cases"]}
    expected = {(key, lang) for key in cases for lang in ("en", "es-419")}
    rows = report["results"]
    if len(rows) != 6 or {(row["case_id"], row["language"]) for row in rows} != expected:
        raise ValueError("exactly_three_runs_times_two_languages_required")
    pairs = []
    for row in rows:
        if row["variant"] != "candidate" or row["replicate"] != 1:
            raise ValueError("candidate_one_repetition_required")
        case = cases[row["case_id"]]
        source_path = root / EVIDENCE / case["source"]["artifact"]
        if digest(source_path) != case["source"]["sha256"]:
            raise ValueError("genuine_source_fixture_changed")
        run = json.loads(source_path.read_text())
        if case["run"] != run:
            raise ValueError("recorded_fixture_does_not_equal_canonical_source")
        if case["source"]["kind"] != "recorded_run":
            raise ValueError("genuine_recorded_run_required")
        outcomes = {}
        for surface, task in SURFACES.items():
            outcome = copy.deepcopy(row.get(surface) or {})
            if not synthetic and not outcome and not row.get("interruption"):
                raise ValueError("missing_outcome_without_recorded_interruption")
            accepted = outcome.get("accepted_text")
            if accepted is not None and (
                not isinstance(accepted, str) or not accepted.strip()
            ):
                raise ValueError("accepted_text_must_be_complete_or_null")
            if accepted is not None and outcome.get("fallback_used") is not False:
                raise ValueError("accepted_text_conflicts_with_fallback")
            if accepted is not None and outcome.get("complete_text") != accepted:
                raise ValueError("accepted_text_differs_from_complete_text")
            requests = [item for item in row.get("requests", []) if item["task"] == task]
            responses = [
                item for item in row.get("provider_responses", []) if item["task"] == task
            ]
            provider = FRAME_PROVIDERS[surface]
            if any(item.get("provider") != provider for item in requests + responses):
                raise ValueError("frame_provider_receipt_mismatch")
            if (
                not synthetic
                and row.get("configuration", {})
                .get("tasks", {})
                .get(task, {})
                .get("provider")
                != provider
            ):
                raise ValueError("frame_provider_configuration_mismatch")
            if len(requests) > 1:
                raise ValueError("more_than_one_provider_attempt_per_frame")
            outcome.update(
                {
                    "surface": surface,
                    "task": task,
                    "provider": provider,
                    "accepted": accepted is not None,
                    "requests": requests,
                    "provider_responses": responses,
                    "raw_drafts": [
                        draft
                        for response in responses
                        for draft in response.get("raw_drafts", [])
                    ],
                    "blocked_dispatches": [
                        item
                        for item in row.get("blocked_dispatches", [])
                        if item.get("task") == task
                    ],
                }
            )
            outcome["rejected_texts"] = (
                [
                    text
                    for raw in outcome["raw_drafts"]
                    if (text := draft_prose(raw)) is not None
                ]
                if accepted is None
                else []
            )
            outcomes[surface] = outcome
        key = f"{row['case_id']}-{row['language']}"
        pairs.append(
            {
                "key": key,
                "case_id": row["case_id"],
                "language": row["language"],
                "source": copy.deepcopy(case["source"]),
                "source_path": str(source_path.relative_to(root)),
                "run": run,
                "outcomes": outcomes,
            }
        )
    return {
        "report_path": str(report_path.resolve()),
        "report_sha256": digest(report_path),
        "fixture_sha256": digest(fixture_path),
        "measurement_checkouts": report.get("checkouts", {}),
        "synthetic_browser_preflight": synthetic,
        "pairs": pairs,
    }


def source_numbers(run: dict[str, Any]) -> list[dict[str, Any]]:
    """Display stored scalars, with their exact paths and values; no new metric math."""
    rows: list[dict[str, Any]] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{path}.{key}" if path else key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")
        elif value is not None:
            rows.append({"path": path, "value": value})

    # Complete metrics, resolved strategy/parameters and chart scalar summaries.
    # Dense chart points and trade rows remain intact in the linked canonical JSON.
    for key in ("symbols", "benchmark_symbol", "metrics"):
        walk(run.get(key), key)
    config = run.get("config_snapshot", {})
    for key in ("resolved_strategy", "resolved_parameters"):
        walk(config.get(key), f"config_snapshot.{key}")
    chart = run.get("chart") or {}
    for key in ("kind", "currency", "base_value", "value_summary", "marker_summary"):
        walk(chart.get(key), f"chart.{key}")
    walk(run.get("figures"), "figures")
    return rows


def synthetic_report(root: Path) -> dict[str, Any]:
    """Distinctly labeled harness data; never a model-quality or live result."""
    fixtures = root / EVIDENCE / "recorded-fixtures.json"
    rows = []
    for case in json.loads(fixtures.read_text())["cases"]:
        for language in ("en", "es-419"):
            row: dict[str, Any] = {
                "case_id": case["id"],
                "language": language,
                "variant": "candidate",
                "replicate": 1,
                "requests": [],
                "provider_responses": [],
                "configuration": {
                    "tasks": {
                        task: {"provider": FRAME_PROVIDERS[surface]}
                        for surface, task in SURFACES.items()
                    },
                },
            }
            for index, (surface, task) in enumerate(SURFACES.items()):
                text = (
                    f"Synthetic {surface} renderer preflight. No model authored this text."
                    if language == "en"
                    else f"Prueba sintética del formato {surface}. Ningún modelo escribió este texto."
                )
                accepted = (language == "en") == (surface == "quick_take")
                sources = []
                if surface == "breakdown":
                    # An intentionally non-fetchable citation tests markup only.
                    url = "https://example.invalid/synthetic-source?year=2023&kind=test"
                    date_label = "Sep 1, 2023" if language == "en" else "1 sep 2023"
                    text += f" [{date_label}]({url})"
                    sources = [
                        {
                            "url": url,
                            "title": "SYNTHETIC citation fixture",
                            "source_date": "2023-09-01",
                        }
                    ]
                row[surface] = {
                    "complete_text": text
                    if accepted
                    else "Synthetic server fallback diagnostic.",
                    "accepted_text": text if accepted else None,
                    "source": "synthetic_browser_preflight",
                    "fallback_used": not accepted,
                    "failure_mode": None if accepted else "synthetic_rejection",
                    "sources": sources,
                }
                row["requests"].append(
                    {
                        "task": task,
                        "provider": FRAME_PROVIDERS[surface],
                        "attempt_id": index + 1,
                        "synthetic_browser_preflight": True,
                    }
                )
                row["provider_responses"].append(
                    {
                        "task": task,
                        "provider": FRAME_PROVIDERS[surface],
                        "attempt_id": index + 1,
                        "http_status": 200,
                        "raw_drafts": [
                            json.dumps(
                                {"synthetic_browser_preflight": True, "text": text}
                            )
                        ],
                    }
                )
            rows.append(row)
    return {
        "synthetic_browser_preflight": True,
        "fixture_sha256": digest(fixtures),
        "results": rows,
        "checkouts": {},
    }
