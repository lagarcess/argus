"""Guard and expose public synthetic IDs for one assigned native test lane."""

import json
from pathlib import Path
from uuid import UUID

SIMULATOR = "C93072E7-D29A-4B0A-BE76-E6418E4E9F88"


def shared_scene(args, work):
    if (
        not args.accounts
        or args.port_base != 59750
        or args.api_port not in (None, 59750)
        or args.simulator != SIMULATOR
        or args.user_index != 0
    ):
        raise SystemExit(
            "Shared planning requires its assigned simulator and allocation59750"
        )
    path = Path(work) / "shared-plans-private.json"
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise SystemExit("Missing safe retained shared-plan scene")
    journal = json.loads(path.read_bytes())
    if journal.get("version") != 1:
        raise SystemExit("Unsupported shared-plan scene")
    rows = journal["operations"]
    ids = {
        "HOUSEHOLD": rows["household"]["result"]["household_id"],
        "MEMBERSHIP_A": rows["household"]["result"]["membership_id"],
        "MEMBERSHIP_B": rows["accept"]["result"]["membership_id"],
    }
    names = {}
    for actor, suffix in ((0, "A"), (1, "B")):
        for kind in (
            ["checking", "savings", "card", "unknown", "usd"]
            if actor == 0
            else ["checking", "savings"]
        ):
            row = rows[f"account-{actor}-{kind}"]["result"]
            label = (
                "ACCOUNT_" + suffix + ("" if kind == "checking" else "_" + kind.upper())
            )
            ids[label] = row["id"]
            names[label + "_NAME"] = row["nickname"]
    result = {
        "ARGUS_TEST_SHARED_PLAN_" + name: str(UUID(value)).upper()
        for name, value in ids.items()
    }
    result.update(
        {"ARGUS_TEST_SHARED_PLAN_" + name: value for name, value in names.items()}
    )
    result["ARGUS_TEST_SHARED_PLAN_STAMP"] = journal["suffix"]
    return result
