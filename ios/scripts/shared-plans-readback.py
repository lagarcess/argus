"""Independent money expectations for the retained native four-plan journey."""

import argparse
import fcntl
import importlib.util
import json
import subprocess
from pathlib import Path
from uuid import UUID

spec = importlib.util.spec_from_file_location(
    "scene", Path(__file__).with_name("shared-plans-journey.py")
)
scene = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scene)
WORK = scene.WORK
BEFORE = WORK / "shared-plans-native-balances-before.json"


def account_ids(journal):
    return {
        name: (
            actor,
            journal.state["operations"][f"account-{actor}-{label}"]["result"]["id"],
        )
        for name, actor, label in (
            ("A_checking", 0, "checking"),
            ("A_savings", 0, "savings"),
            ("A_card", 0, "card"),
            ("A_unknown", 0, "unknown"),
            ("A_usd", 0, "usd"),
            ("B_checking", 1, "checking"),
            ("B_savings", 1, "savings"),
        )
    }


def balances(journal, client):
    result = {}
    for name, (actor, identifier) in account_ids(journal).items():
        value = client.get(actor, "/financial-accounts/" + identifier)
        result[name] = dict(
            currency=value["currency"], minor=value["balance"]["amount_minor"]
        )
    return result


def record_baseline(journal, client):
    scene.save_private(BEFORE, balances(journal, client))


def verify(journal, client, native_path):
    native_path = native_path.resolve(strict=True)
    scene.require(
        WORK.resolve() in native_path.parents,
        "Native attachment must remain in this lane's ignored results",
    )
    native = json.loads(native_path.read_bytes())
    scene.require(
        set(native["rows"]) == {"budget", "bill", "goal", "debt"},
        "Native proof must include all four kinds",
    )
    before = scene.read_private(BEFORE)
    after = balances(journal, client)
    # Independently stated journey: A expense25, bill20, savings transfer20,
    # card payment20; B expense15. Transfers/payment do not become new spending.
    changes = {
        "A_checking": -8500,
        "A_savings": 2000,
        "A_card": 2000,
        "B_checking": -1500,
        "B_savings": 0,
        "A_usd": 0,
    }
    for name, change in changes.items():
        scene.require(
            after[name]["currency"] == before[name]["currency"], "Currency changed"
        )
        scene.require(
            after[name]["minor"] == before[name]["minor"] + change,
            "Canonical balance does not match independently stated journey: " + name,
        )
    scene.require(
        before["A_unknown"]["minor"] is None and after["A_unknown"]["minor"] is None,
        "Unknown balance became an invented amount",
    )
    hid = journal.state["operations"]["household"]["result"]["household_id"]
    prefix = "/households/" + hid
    private = {}
    for actor in (0, 1):
        private[actor] = [
            str(identifier).lower()
            for _, (owner, identifier) in account_ids(journal).items()
            if owner == actor
        ]
        private[actor] += [
            row["result"]["nickname"]
            for key, row in journal.state["operations"].items()
            if key.startswith(f"account-{actor}-")
        ]
    checks = []
    for kind, row in native["rows"].items():
        expected_prefix = "sharedPlan.row." + kind + "."
        scene.require(row.startswith(expected_prefix), "Unexpected native row reference")
        identifier = str(UUID(row[len(expected_prefix) :]))
        path = prefix + "/plan/" + kind + "/" + identifier
        a = client.get(0, path)
        b = client.get(1, path)
        client.get(2, path, status=404)
        for actor, value in ((0, a), (1, b)):
            scene.require(
                value["ref"] == {"kind": kind, "id": identifier},
                "Detail did not return original canonical reference",
            )
            scene.require(
                value["definition"]["name"] == native["names"][kind],
                "Native name was not persisted",
            )
            scene.require(
                not value["archived"], "Runnable native plans should remain active"
            )
            encoded = json.dumps(value).lower()
            scene.require(
                all(item.lower() not in encoded for item in private[1 - actor]),
                "Another member's private funding detail leaked",
            )
            scene.require(
                "private source " + ("b" if actor == 0 else "a") not in encoded,
                "Another member's private note leaked",
            )
        if kind == "budget":
            scene.require(
                a["progress"]["spent_minor"] == b["progress"]["spent_minor"] == "4000",
                "Shared spending must be25+15, not planned70+30",
            )
            scene.require(
                sorted(item["amount_minor"] for item in b["responsibilities"])
                == ["3000", "7000"],
                "Unequal intentions changed into actuals",
            )
            scene.require(
                b["permission"] == "view", "View-only proof lost its permission"
            )
            scene.require(
                sorted(
                    item["applied_minor"]
                    for item in b["contributions"]
                    if item["status"] == "current"
                )
                == ["1500", "2500"],
                "Corrections must replace, not add, progress",
            )
        elif kind == "bill":
            scene.require(
                a["definition"]["amount_minor"]
                == b["definition"]["amount_minor"]
                == "6000",
                "Explicit editor's agreed amount was not persisted",
            )
            scene.require(
                b["permission"] == "edit", "Named bill editor lost its permission"
            )
            scene.require(
                a["progress"]["applied_minor"]
                == b["progress"]["applied_minor"]
                == "2000",
                "Bill payment counted incorrectly",
            )
        elif kind == "goal":
            scene.require(
                a["progress"]["actual_minor"] == b["progress"]["actual_minor"] == "2000",
                "Recorded goal savings must be backed once",
            )
            scene.require(
                a["definition"]["planned_contribution_minor"] == "1000",
                "Planned contribution disappeared into actual money",
            )
        elif kind == "debt":
            scene.require(
                a["progress"]["applied_minor"]
                == b["progress"]["applied_minor"]
                == "2000",
                "Debt payment counted incorrectly",
            )
            scene.require(
                b["progress"]["debt_balance_minor"] is None,
                "Private debt balance leaked to plan-only participant",
            )
        history = client.get(1, path + "/history")
        scene.require(
            all(item.lower() not in json.dumps(history).lower() for item in private[0]),
            "Shared history leaked private owner funding",
        )
        checks.append(kind)
    for actor in (0, 1):
        snap = client.get(actor, prefix + "/plan")
        scene.require(
            len(snap["plans"]) >= 4, "Shared Plan list lost a native definition"
        )
        home = client.get(actor, prefix + "/snapshot")
        scene.require(
            home["accounts"] == [],
            "Sharing plans automatically shared financial accounts",
        )
    client.get(2, prefix + "/plan", status=404)
    return {
        "source_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=scene.ROOT, text=True
        ).strip(),
        "runtime": "native iOS simulator / real Auth59751 API59750 Postgres59752",
        "checks": checks
        + [
            "independent balance deltas",
            "25+15 actual versus70+30 planned",
            "view-only own correction",
            "explicit bill edit",
            "private funding/history redaction",
            "third identity denied",
            "unknown and currencies preserved",
            "one transfer and card payment",
        ],
        "account_changes_minor": changes,
        "limits": "Local native proof. Native retry/departure and broader server acceptance are separate recorded checks; no physical-phone internet claim.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("baseline", "verify"))
    parser.add_argument("--native-scene", type=Path)
    args = parser.parse_args()
    scene.require(
        WORK.is_dir() and not WORK.is_symlink(), "Missing owned local allocation"
    )
    with (WORK / "shared-plans.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        client = scene.Client(scene.load_client())
        journal = scene.Journal(scene.STATE)
        if args.action == "baseline":
            record_baseline(journal, client)
            print(
                "Retained synthetic balances captured before native journey; no writes sent"
            )
        else:
            scene.require(
                args.native_scene is not None,
                "Supply the exported native scene attachment",
            )
            proof = verify(journal, client, args.native_scene)
            scene.save_private(WORK / "shared-plans-native-readback.json", proof)
            print(
                "Verified all four native plans against independent canonical balance and privacy expectations"
            )


if __name__ == "__main__":
    try:
        main()
    except (scene.Refused, BlockingIOError) as error:
        raise SystemExit(str(error)) from None
