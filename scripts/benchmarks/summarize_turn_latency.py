"""Offline analysis of recorded #462 observations. Never starts a provider call."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from argus.domain.backtest_job_scopes import CHAT_RUN_SCOPE, RESEARCH_OPERATION_SCOPE

from scripts.benchmarks.turn_latency import distribution


def actual_turn_type(row):
    job = row.get("job") or {}
    outcome = row["outcome"]
    if row["status"] == "stream_error":
        return "stream_error"
    if row["status"] == "incomplete_stream":
        return "incomplete"
    if job.get("operation_scope") == CHAT_RUN_SCOPE or outcome.get("run"):
        return "backtest_run"
    if job.get("operation_scope") == RESEARCH_OPERATION_SCOPE:
        return "research_thorough"
    if outcome.get("research_shape"):
        return "research_" + outcome["research_shape"]
    if outcome.get("confirmation"):
        return "confirmation"
    if outcome.get("stage_outcome") == "await_user_reply":
        return "clarification"
    return "ordinary_chat"


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        actual = actual_turn_type(row)
        label = actual
        job = row.get("job") or {}
        outcome = job.get("result") or row["outcome"]
        if outcome.get("research_degraded"):
            label += "__degraded"
        elif job and job.get("status") != "succeeded":
            label += "__" + job["status"]
        if row["requested_category"] == "compute_intent_probe":
            label = "compute_intent_probe__" + actual
        groups[label].append(row)
    result = {"quantile_method": "nearest_rank", "observations": len(rows), "groups": {}}
    for category, cohort in sorted(groups.items()):
        metrics = defaultdict(list)
        tasks = defaultdict(list)
        tiers = Counter()
        served_tiers = Counter()
        calls = Counter()
        successful_calls = Counter()
        shapes = Counter()
        for row in cohort:
            times = row["timings"]
            for key in (
                "headers_ms",
                "first_stage_ms",
                "first_token_ms",
                "first_visible_ms",
                "done_ms",
            ):
                metrics[key].append(times.get(key))
            metrics["completion_ms"].append(row.get("completion_ms"))
            job = row.get("job") or {}
            outcome = job.get("result") or row["outcome"]
            is_grounded = (
                actual_turn_type(row).startswith("research_")
                and not outcome.get("research_degraded")
                and row["status"] in {"stream_complete", "succeeded"}
            )
            grounded_ms = None
            if is_grounded:
                if job:
                    if job.get("status") == "succeeded":
                        grounded_ms = job.get("answer_observed_ms")
                else:
                    grounded_ms = times.get("first_token_ms")
            metrics["first_grounded_answer_ms"].append(grounded_ms)
            if category.startswith("research_"):
                shapes[
                    (outcome.get("research_cache"), outcome.get("research_degraded"))
                ] += 1
            per_turn = defaultdict(float)
            positive_tiers = set()
            successful_tiers = set()
            for receipt in row.get("receipts", []):
                tier = receipt["tier"]
                calls[tier] += 1
                if receipt["outcome"] == "succeeded":
                    successful_calls[tier] += 1
                    successful_tiers.add(tier)
                if (receipt.get("latency_ms") or 0) > 0:
                    positive_tiers.add(tier)
                    # Preserve both task and schema: preflight is not focused repair.
                    name = (
                        receipt["task"]
                        + "/"
                        + (receipt.get("schema_name") or receipt["mode"])
                    )
                    per_turn[name] += receipt["latency_ms"]
            tiers.update(positive_tiers)
            served_tiers.update(successful_tiers)
            for name, duration in per_turn.items():
                tasks[name].append(duration)
            stages = [event for event in row["events"] if event["type"] == "stage_start"]
            interpret = next(
                (event["at_ms"] for event in stages if event.get("stage") == "interpret"),
                None,
            )
            first_outcome = next(
                (
                    event["at_ms"]
                    for event in row["events"]
                    if event["type"] == "stage_outcome"
                ),
                None,
            )
            span = (
                first_outcome - interpret
                if interpret is not None and first_outcome is not None
                else None
            )
            metrics["interpret_to_first_outcome_ms"].append(span)
            post = times.get("first_visible_ms")
            metrics["first_outcome_to_visible_ms"].append(
                post - first_outcome
                if post is not None
                and first_outcome is not None
                and post >= first_outcome
                else None
            )
        result["groups"][category] = {
            "n": len(cohort),
            "languages": dict(Counter(row["language"] for row in cohort)),
            "requested_categories": dict(
                Counter(row["requested_category"] for row in cohort)
            ),
            "statuses": dict(Counter(row["status"] for row in cohort)),
            "metrics": {key: distribution(values) for key, values in metrics.items()},
            "provider_task_ms_when_present": {
                key: distribution(values) for key, values in tasks.items()
            },
            "turns_with_positive_latency_tier": dict(tiers),
            "turns_with_successful_tier": dict(served_tiers),
            "receipt_rows_by_tier": dict(calls),
            "successful_receipt_rows_by_tier": dict(successful_calls),
            "research_cache_and_degradation": [
                {"cache": k[0], "degraded": k[1], "n": v} for k, v in shapes.items()
            ],
            "token_event_counts": dict(
                Counter(
                    sum(
                        event["type"] == "token" and event.get("characters", 0) > 0
                        for event in row["events"]
                    )
                    for row in cohort
                )
            ),
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text().splitlines() if line]
    args.output.write_text(json.dumps(summarize(rows), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
