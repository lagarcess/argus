"""Read a disposable local ledger with the production gate's comparison code.

This is a rehearsal, never production clearance. Supabase CLI applies the SQL
separately. The adapter deliberately replaces production TLS with a loopback-only
connection; the production CLI and its target/TLS checks remain unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import psycopg

from scripts.ops.production_migration_gate import (
    ProductionDatabaseTarget,
    build_migration_report,
    read_applied_migrations,
    read_candidate_migrations,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    url = os.environ["ARGUS_DISPOSABLE_DATABASE_URL"]
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"postgres", "postgresql"}
        or parsed.hostname not in {"127.0.0.1", "::1"}
        or parsed.query
        or parsed.fragment
    ):
        raise SystemExit("An explicit loopback database URL without options is required")

    def local_connect(database_url: str, **options: object):
        options.pop("sslrootcert")
        options["sslmode"] = "disable"
        return psycopg.connect(database_url, **options)

    root = Path(__file__).resolve().parents[4]
    candidate = read_candidate_migrations(root, args.candidate_sha)
    applied = read_applied_migrations(
        url, ssl_root_cert="local-only", connect_factory=local_connect
    )
    comparison = build_migration_report(
        candidate_sha=args.candidate_sha,
        target=ProductionDatabaseTarget(
            project_ref="disposable-local", database_host=parsed.hostname
        ),
        candidate_migrations=candidate,
        applied_migrations=applied,
    )
    comparison["database_transport"] = "loopback_without_tls"
    report = {
        "evidence_kind": "disposable_local_rehearsal",
        "production_access": "none",
        "production_clearance": False,
        "transport": "loopback_without_tls",
        "historical_production_fingerprint": "not_applicable_to_fresh_local_ledger",
        "comparison": comparison,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": comparison["status"],
                "candidate_sha": args.candidate_sha,
                "candidate_count": len(candidate),
                "applied_count": len(applied),
                "stop_reasons": comparison["stop_reasons"],
                "missing": comparison["missing_migrations"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
