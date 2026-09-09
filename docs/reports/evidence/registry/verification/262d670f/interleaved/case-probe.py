"""Run one original measurement case as an explicitly partial live probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--environment", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if os.environ.get("ARGUS_RUN_LIVE_EVALS") != "1":
        raise SystemExit("Live opt-in is required; this command makes provider calls.")
    if args.output.exists():
        raise SystemExit("Refusing to overwrite an existing measurement.")
    repository = args.repository.resolve(strict=True)
    os.chdir(repository)
    sys.path[:0] = [str(repository), str(repository / "src")]

    from dotenv import load_dotenv

    load_dotenv(args.environment, override=False)

    import argus
    from tests.evals import measurement_eval_harness as harness
    from tests.evals import measurement_eval_scorecard as scorecards

    for module in (argus, harness, scorecards):
        if not Path(module.__file__).resolve().is_relative_to(repository):
            raise RuntimeError(f"Imported {module.__name__} from the wrong checkout")
    cases = {case.id: case for case in harness.load_eval_cases()}
    case = cases[args.case]
    provenance = scorecards.build_scorecard_provenance(evaluation_mode="live")
    inputs = {
        key: value
        for key, value in case.raw.items()
        if key not in {"expected", "expected_fail", "prose_judge"}
    }
    input_digest = hashlib.sha256(
        json.dumps(inputs, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    started = datetime.now(timezone.utc).isoformat()
    started_clock = monotonic()
    result = harness.run_eval_case(case)
    scorecards.assert_provenance_matches_current_run(provenance)
    payload = {
        "artifact_type": "partial_interleaved_case_probe",
        "is_full_suite_scorecard": False,
        "label": args.label,
        "started_at": started,
        "elapsed_seconds": monotonic() - started_clock,
        "provenance": scorecards.validated_provenance_payload(provenance),
        "case_input_sha256": input_digest,
        "selected_case_ids": [case.id],
        "provider_usage": scorecards._provider_usage([result]),
        "results": [result],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        json.dump(payload, output, indent=2, sort_keys=True)
        output.write("\n")
    print(json.dumps({
        "label": args.label,
        "case": case.id,
        "status": result["status"],
        "failed_checks": result["failed_checks"],
        "elapsed_seconds": payload["elapsed_seconds"],
        "output": str(args.output),
    }), flush=True)


if __name__ == "__main__":
    main()
