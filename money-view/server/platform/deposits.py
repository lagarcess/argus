"""Household export and reset for the existing deposit receipts."""

import json

from .common import Context


def export_data(db, context: Context) -> dict:
    confirmations = [
        dict(row)
        for row in db.execute(
            "SELECT c.* FROM confirmations c JOIN p_placement_confirmations pc ON pc.id=c.id "
            "WHERE pc.household_id=?",
            (context.household_id,),
        )
    ]
    comparisons = [
        json.loads(row["document"])
        for row in db.execute(
            "SELECT c.document FROM comparisons c JOIN p_placement_comparisons pc ON pc.id=c.id "
            "WHERE pc.household_id=?",
            (context.household_id,),
        )
    ]
    saved = [
        dict(row)
        for row in db.execute(
            "SELECT sd.* FROM saved_decisions sd JOIN p_placement_comparisons pc "
            "ON pc.id=sd.comparison_id WHERE pc.household_id=?",
            (context.household_id,),
        )
    ]
    checks = [
        dict(row)
        for row in db.execute(
            "SELECT dc.* FROM decision_checks dc JOIN saved_decisions sd ON sd.id=dc.decision_id "
            "JOIN p_placement_comparisons pc ON pc.id=sd.comparison_id WHERE pc.household_id=?",
            (context.household_id,),
        )
    ]
    return {
        "confirmations": confirmations,
        "comparisons": comparisons,
        "saved": saved,
        "checks": checks,
    }


def usage_data(db, context: Context) -> dict:
    return {
        "deposit_comparisons": db.execute(
            "SELECT COUNT(*) FROM p_placement_comparisons WHERE household_id=?",
            (context.household_id,),
        ).fetchone()[0]
    }


def clear_data(db, context: Context) -> None:
    owner = (context.household_id,)
    db.execute(
        "DELETE FROM decision_checks WHERE decision_id IN (SELECT sd.id FROM saved_decisions sd "
        "JOIN p_placement_comparisons pc ON pc.id=sd.comparison_id WHERE pc.household_id=?)",
        owner,
    )
    db.execute(
        "DELETE FROM saved_decisions WHERE comparison_id IN "
        "(SELECT id FROM p_placement_comparisons WHERE household_id=?)",
        owner,
    )
    db.execute(
        "DELETE FROM confirmations WHERE id IN "
        "(SELECT id FROM p_placement_confirmations WHERE household_id=?)",
        owner,
    )
    db.execute(
        "DELETE FROM comparisons WHERE id IN "
        "(SELECT id FROM p_placement_comparisons WHERE household_id=?)",
        owner,
    )
