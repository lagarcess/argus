"""Provider-free eligibility audit of existing evidence for a new candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from tests.promotion_evidence_configuration import assert_release_configuration_matches
from tests.promotion_evidence_identity import reachable_changes
from tests.release_promotion_evidence_support import (
    assert_main_promotion_live_eval_evidence,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[4]
    reports = []
    candidates = []
    for path in sorted((root / "docs/reports/evidence").rglob("*.json")):
        try:
            document = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        if not isinstance(document, dict):
            continue
        provenance = document.get("provenance")
        if (
            not isinstance(provenance, dict)
            or provenance.get("evaluation_mode") != "live"
        ):
            continue
        if not all(key in document for key in ("results", "totals")):
            continue
        measured = provenance.get("candidate_sha")
        if not isinstance(measured, str) or len(measured) != 40:
            continue
        relative = path.relative_to(root).as_posix()
        candidates.append(relative)
        report = {
            "path": relative,
            "measured_sha": measured,
            "schema_version": document.get("schema_version"),
        }
        try:
            changed = reachable_changes(
                measured, args.candidate_sha, repository_root=root
            )
            report["reachable_change_count"] = len(changed)
            report["reachable_change_examples"] = list(changed[:8])
            report["reachable_changes_sha256"] = hashlib.sha256(
                "\n".join(changed).encode()
            ).hexdigest()
        except Exception as exc:
            report["identity_error"] = type(exc).__name__
        try:
            assert_release_configuration_matches(
                provenance.get("release_configuration"),
                shipped_sha=args.candidate_sha,
                repository_root=root,
                evidence=relative,
            )
            report["configuration"] = "pass"
        except AssertionError as exc:
            report["configuration"] = str(exc)
        manifest = root / "temp/promotion-readiness/new-candidate-probe.md"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            f"- Candidate SHA: `{args.candidate_sha}`\n"
            f"- Live eval measured SHA: `{measured}`\n"
            f"- Live eval scorecard: `{relative}`\n"
        )
        try:
            assert_main_promotion_live_eval_evidence(manifest, repository_root=root)
            report["new_candidate_gate"] = "pass"
        except AssertionError as exc:
            report["new_candidate_gate"] = str(exc)
        reports.append(report)
    result = {
        "candidate_sha": args.candidate_sha,
        "provider_calls": 0,
        "production_access": "none",
        "examined_scorecards": len(candidates),
        "eligible_scorecards": sum(r["new_candidate_gate"] == "pass" for r in reports),
        "scorecards": reports,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "scorecards"}, indent=2))


if __name__ == "__main__":
    main()
