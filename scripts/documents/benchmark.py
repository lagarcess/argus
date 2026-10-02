"""Validate fixtures offline; run approved serial extraction with a capped provider key."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import mimetypes
import os
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx
from argus.domain.ingestion.documents.config import DocumentExtractionSettings
from argus.domain.ingestion.documents.extractor import DocumentExtractor
from argus.domain.ingestion.documents.models import DocumentExtractionError
from argus.llm.openrouter_key_policy import resolve_openrouter_api_key

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tests/document_extraction_fixtures/manifest.json"
FIELDS = ("amount", "currency", "date", "direction")
DIRECTIONS = {
    "expense": "outflow",
    "fee": "outflow",
    "income": "inflow",
    "refund": "inflow",
}


def money(value: object) -> Decimal:
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("invalid_cost") from None
    if not amount.is_finite() or amount < 0:
        raise ValueError("invalid_cost")
    return amount


def validate_key_cap(data: dict, cap: Decimal) -> Decimal:
    """Require a nonresetting provider cap, including any BYOK usage."""
    if cap <= 0 or not cap.is_finite():
        raise ValueError("invalid_spend_cap")
    if data.get("limit") is None or data.get("limit_remaining") is None:
        raise ValueError("dedicated_capped_key_required")
    remaining = money(data["limit_remaining"])
    if (
        money(data["limit"]) > cap
        or remaining > cap
        or remaining <= 0
        or data.get("limit_reset") is not None
        or data.get("include_byok_in_limit") is not True
    ):
        raise ValueError("dedicated_capped_key_required")
    return remaining


async def key_status(key: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            "https://openrouter.ai/api/v1/key",
            headers={"Authorization": f"Bearer {key}"},
        )
        response.raise_for_status()
        return response.json()["data"]


def row_score(sample: dict, candidates: tuple) -> dict:
    expected = [
        (money(row["amount"]), row["currency"], row["date"], DIRECTIONS[row["kind"]])
        for row in sample["expected_rows"]
    ]
    transactions = [row for row in candidates if row.evidence == "transaction"]
    actual = [
        (
            money(row.amount) if row.amount is not None else None,
            row.currency,
            row.occurred_on.isoformat() if row.occurred_on else None,
            row.direction,
        )
        for row in transactions
    ]
    wanted, got = Counter(expected), Counter(actual)
    field_matches = {
        name: sum(
            (
                Counter(row[index] for row in expected)
                & Counter(row[index] for row in actual)
            ).values()
        )
        for index, name in enumerate(FIELDS)
    }
    balances = sample.get("excluded_balances", {})
    balance_values = {
        money(balances[name]) for name in ("opening", "closing") if name in balances
    }
    return {
        "expected_transactions": len(expected),
        "observed_transactions": len(actual),
        "exact_matches": sum((wanted & got).values()),
        "missing_or_mismatched": sum((wanted - got).values()),
        "invented_or_mismatched": sum((got - wanted).values()),
        "field_multiset_matches": field_matches,
        "field_denominator": max(len(expected), len(actual)),
        "balance_candidates": sum(row.evidence == "balance" for row in candidates),
        "balances_as_transactions": sum(
            row[0] in balance_values and row[1] == balances.get("currency")
            for row in actual
        ),
    }


def receipt_cost(metadata: dict) -> tuple[Decimal, dict]:
    receipts = metadata.get("route_receipts", [])
    if len(receipts) != 1 or receipts[0].get("usage_cost_usd") is None:
        raise ValueError("unknown_cost_or_multiple_attempts")
    receipt = receipts[0]
    cost = money(receipt["usage_cost_usd"])
    return cost, {
        "model": receipt.get("model"),
        "token_usage": receipt.get("token_usage"),
        "cost_usd": str(cost),
    }


def validate_fixtures(manifest: Path) -> list[dict]:
    data = json.loads(manifest.read_text())
    samples = data["samples"]
    if len(samples) != 6 or len({s["id"] for s in samples}) != 6:
        raise ValueError("expected_six_unique_fixtures")
    for sample in samples:
        for file_key, digest_key in (
            ("file", "sha256"),
            ("original_labels", "labels_sha256"),
        ):
            if file_key not in sample:
                continue
            path = (manifest.parent / sample[file_key]).resolve()
            if not path.is_relative_to(manifest.parent.resolve()):
                raise ValueError("fixture_path_outside_dataset")
            if hashlib.sha256(path.read_bytes()).hexdigest() != sample[digest_key]:
                raise ValueError("fixture_checksum_mismatch")
        if not sample.get("license"):
            raise ValueError("missing_fixture_license")
        if not sample["synthetic"] and not sample.get("validation", {}).get(
            "image_inspected"
        ):
            raise ValueError("unvalidated_document_label_pair")
        for row in sample["expected_rows"]:
            money(row["amount"])
            if row["kind"] not in DIRECTIONS:
                raise ValueError("unsupported_expected_direction")
    return samples


async def run_live(samples, directory, extractor, cap, check_key, report, save):
    spent = Decimal(0)
    for sample in samples:
        try:
            validate_key_cap(await check_key(), cap)
        except (ValueError, httpx.HTTPError, KeyError):
            report["stop_reason"] = "provider_cap_not_verified"
            break
        if spent >= cap:
            report["stop_reason"] = "spend_cap_reached"
            break
        started = time.perf_counter()
        candidates, metadata, error = (), {}, None
        try:
            batch = await extractor.extract(
                (directory / sample["file"]).read_bytes(),
                sample["file"],
                mimetypes.guess_type(sample["file"])[0],
                "document-benchmark",
                datetime.now(timezone.utc),
            )
            candidates, metadata = batch.candidates, batch.metadata
        except DocumentExtractionError as failure:
            error, metadata = failure.code, failure.metadata
        result = {
            "fixture_id": sample["id"],
            "sha256": sample["sha256"],
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "error_code": error,
            "expected_rejection": sample["expected_status"] == "unreadable",
            "rejection_correct": error == "unreadable_document"
            if sample["expected_status"] == "unreadable"
            else error is None,
            "quality": row_score(sample, candidates),
        }
        report["results"].append(result)
        try:
            cost, usage = receipt_cost(metadata)
        except ValueError:
            report["stop_reason"] = "unknown_cost_or_multiple_attempts"
            save(report)
            break
        result["usage"] = usage
        spent += cost
        report["actual_cost_usd"] = str(spent)
        if spent > cap:
            report["stop_reason"] = "provider_cap_exceeded"
        save(report)
        if report.get("stop_reason"):
            break
    report["complete"] = len(report["results"]) == len(samples) and not report.get(
        "stop_reason"
    )
    save(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--max-documents", type=int)
    parser.add_argument("--spend-cap-usd")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    samples = validate_fixtures(args.manifest)
    report = {
        "mode": "live" if args.live else "offline",
        "results": [],
        "fixture_count": len(samples),
        "fixtures": [
            {"id": sample["id"], "sha256": sample["sha256"]} for sample in samples
        ],
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "model": os.getenv("ARGUS_VISION_MODEL", ""),
        "actual_cost_usd": "0",
        "complete": not args.live,
        "scope": "Small public/synthetic sample; no Dominican-bank compatibility claim.",
    }
    # Exclusive creation prevents accidentally overwriting an earlier paid run's evidence.
    with args.output.open("x") as output:
        output.write(json.dumps(report, indent=2) + "\n")

    def save(value):
        args.output.write_text(json.dumps(value, indent=2) + "\n")

    if args.live:
        if args.max_documents != 6 or not args.spend_cap_usd or not report["model"]:
            parser.error(
                "live requires --max-documents 6, --spend-cap-usd and ARGUS_VISION_MODEL"
            )
        cap = money(args.spend_cap_usd)
        key = resolve_openrouter_api_key("registered")
        if not key:
            parser.error("missing OpenRouter credentials")
        report["approved_cap_usd"] = str(cap)
        extractor = DocumentExtractor(DocumentExtractionSettings(enabled=True))
        asyncio.run(
            run_live(
                samples,
                args.manifest.parent,
                extractor,
                cap,
                lambda: key_status(key),
                report,
                save,
            )
        )
    print(
        json.dumps(
            {
                "complete": report["complete"],
                "mode": report["mode"],
                "output": str(args.output),
            }
        )
    )
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
