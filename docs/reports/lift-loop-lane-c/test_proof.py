"""Unit harness for the never-merge Lane C proof; no application startup."""

import inspect
import math

import pytest
from compute import solve_for_unknown

FIELDS = tuple(inspect.signature(solve_for_unknown).parameters)


def balance_after(present_value, payment, rate, periods):
    # Independent discrete cash-flow oracle, not the solver's annuity formula.
    balance = present_value
    for _ in range(periods):
        balance = balance * (1 + rate) + payment
    return -balance


@pytest.mark.parametrize("unknown", FIELDS)
@pytest.mark.parametrize("rate", [0.0, 0.005, -0.002])
@pytest.mark.parametrize("present_value,payment", [(-1200.0, -250.0), (12000.0, -900.0)])
def test_every_unknown_recovers_cash_flow_oracle(unknown, rate, present_value, payment):
    values = dict(
        zip(
            FIELDS,
            (
                present_value,
                payment,
                rate,
                12.0,
                balance_after(present_value, payment, rate, 12),
            ),
            strict=False,
        )
    )
    expected = values[unknown]
    values[unknown] = None
    assert solve_for_unknown(**values) == pytest.approx(expected, rel=1e-8, abs=1e-8)


@pytest.mark.parametrize(
    "values,expected",
    [
        ((0.0, None, 0.0, 12.0, 12000.0), -1000.0),
        ((None, -1000.0, 0.0, 12.0, 0.0), 12000.0),
    ],
)
def test_same_call_with_a_different_blank(values, expected):
    assert solve_for_unknown(*values) == pytest.approx(expected)


@pytest.mark.parametrize("rate", [1e-12, -1e-12])
@pytest.mark.parametrize(
    "unknown", ["present_value", "payment", "periods", "future_value"]
)
def test_near_zero_rate_preserves_cash_flow(unknown, rate):
    values = dict(
        zip(
            FIELDS,
            (-1200.0, -250.0, rate, 12.0, balance_after(-1200.0, -250.0, rate, 12)),
            strict=False,
        )
    )
    expected = values[unknown]
    values[unknown] = None
    assert solve_for_unknown(**values) == pytest.approx(expected, rel=1e-8, abs=1e-8)


@pytest.mark.parametrize(
    "values",
    [
        (0, 1, 0, 12, 1),
        (None, None, 0, 12, 1),
        (0, None, -1, 12, 1),
        (0, None, 0, 0, 1),
        (0, None, 0, -1, 1),
        (True, None, 0, 12, 1),
        (0, None, math.inf, 12, 1),
        (0, None, math.nan, 12, 1),
        (0, None, "0.01", 12, 1),
    ],
)
def test_invalid_inputs_fail_explicitly(values):
    with pytest.raises(ValueError):
        solve_for_unknown(*values)


@pytest.mark.parametrize(
    "values",
    [
        (0, 0, None, 12, 0),  # rate is indeterminate
        (-100, 0, None, 12, -100),  # no sign change, hence no rate root
        (100, -300, None, 2, 500),  # two positive discount-factor roots
        (-100, -1, None, 1.5, 120),  # outside rate solver's discrete domain
        (0, 0, 0, None, 1),  # time cannot change the balance
        (-100, 0, 0.01, None, 50),  # would need negative periods
        (-100, 1, 0.01, None, 100),  # constant balance: any period count
    ],
)
def test_unsolved_or_ambiguous_math_is_not_an_answer(values):
    with pytest.raises(ValueError):
        solve_for_unknown(*values)


@pytest.mark.parametrize("blank", ["payment", "present_value"])
def test_declaration_computes_then_carries_exact_inputs_in_its_card(blank):
    from declaration import DECLARATION

    inputs = dict(zip(FIELDS, (0.0, -1000.0, 0.0, 12.0, 12000.0), strict=False))
    inputs[blank] = None
    answer = DECLARATION["compute"](**inputs)
    card = DECLARATION["card"](inputs=inputs, answer=answer)
    assert card["answer"] == {"field": blank, "value": answer}
    assert card["inputs"] == inputs
    assert list(card).index("answer") < list(card).index("inputs")
    assert inputs[blank] is None
    assert DECLARATION["confirmation"] == "answer_first"


# Fresh processes prevent a previous test from hiding a transitive import.
# The guard refuses real imports; it never stubs modules or rewrites production.
BODY_ROOTS = (
    "argus.domain.backtesting",
    "argus.domain.engine_launch",
    "argus.agent_runtime.strategy_contract",
)
CATALOG_ROOTS = BODY_ROOTS + ("argus.domain.strategy_capabilities",)


def probe_transport():
    from datetime import datetime, timezone
    from uuid import uuid4

    from argus.agent_runtime.state.models import ArtifactReference, FinalResponsePayload
    from argus.api.schemas import Message
    from declaration import DECLARATION

    cards = []
    for values in ((0.0, None, 0.0, 12.0, 12000.0), (None, -1000.0, 0.0, 12.0, 0.0)):
        inputs = dict(zip(FIELDS, values, strict=True))
        answer = DECLARATION["compute"](**inputs)
        card = DECLARATION["card"](inputs=inputs, answer=answer)
        reference = ArtifactReference(
            artifact_kind=card["kind"],
            artifact_id=str(uuid4()),
            artifact_status="computed",
            metadata=card,
        )
        final = FinalResponsePayload(result=card)
        message = Message(
            id=str(uuid4()),
            conversation_id=str(uuid4()),
            role="assistant",
            content="",
            created_at=datetime.now(timezone.utc),
            metadata={
                "calculation_card": card,
                "artifact_references": [reference.model_dump(mode="json")],
            },
        )
        reloaded = Message.model_validate_json(message.model_dump_json())
        assert reloaded.metadata["calculation_card"] == final.result == reference.metadata
        cards.append(card)
    return {"round_trip": True, "cards": cards}


def probe_calculation():
    from declaration import DECLARATION

    return {"answer": DECLARATION["compute"](None, -1000, 0, 12, 0)}


def probe_confirmation_payload():
    from argus.agent_runtime.state.models import ConfirmationPayload, ResponseIntent
    from pydantic import ValidationError

    inputs = dict(zip(FIELDS, (0.0, None, 0.0, 12.0, 12000.0), strict=False))
    try:
        ConfirmationPayload.model_validate({"inputs": inputs})
    except ValidationError as exc:
        errors = [
            {"loc": list(item["loc"]), "type": item["type"]} for item in exc.errors()
        ]
    else:
        raise AssertionError("expected a required strategy")
    try:
        ResponseIntent(kind="calculation", facts=inputs)
    except ValidationError as exc:
        intent_errors = [item["type"] for item in exc.errors()]
    else:
        raise AssertionError("unexpected calculation intent")
    # Existing facts carrier retains new keys, but that does not add a renderer.
    facts = ResponseIntent(kind="artifact_assumptions", facts=inputs).facts
    return {
        "confirmation_errors": errors,
        "intent_errors": intent_errors,
        "facts_preserved": facts == inputs,
    }


def probe_lifecycle():
    from argus.api.chat.confirmation_lifecycle import _stamped_card_metadata

    metadata = {"calculation_card": {"kind": "time_value_of_money", "status": "computed"}}
    stamped = _stamped_card_metadata(metadata, "superseded")
    conventional = _stamped_card_metadata({"confirmation_card": {}}, "superseded")
    return {
        "own_kind_unchanged": stamped == metadata,
        "confirmation_state": conventional["confirmation_card"]["confirmation_state"],
    }


def probe_lifecycle_write():
    from types import SimpleNamespace

    from argus.api.chat.confirmation_lifecycle import apply_pending_card_update

    # Only invoked WITH the body-import guard; fails before any store is reached.
    return apply_pending_card_update(
        user_id="proof",
        conversation_id="proof",
        source_message=SimpleNamespace(metadata={}),
        expected_source_metadata={},
        expected_latest_message_id=None,
        confirmation_id="proof",
        confirmation_payload={},
        language="en",
    )


def probe_edit_bookkeeping():
    from argus.agent_runtime.artifact_edit_planner import (
        EditOperation,
        ResolvedArtifactEdit,
        accepted_operation_targets,
        accepted_operations_partially_materialized,
        typed_unapplied_operations,
    )
    from pydantic import ValidationError

    resolved = ResolvedArtifactEdit(applied=["set.payment", "set.rate"])
    try:
        EditOperation(op="set", target="payment", number=100)
    except ValidationError as exc:
        errors = [item["type"] for item in exc.errors()]
    else:
        raise AssertionError("unexpected payment edit target")
    return {
        "accepted": sorted(accepted_operation_targets(resolved)),
        "partially_materialized": accepted_operations_partially_materialized(
            resolved, {"rate"}
        ),
        "unapplied": typed_unapplied_operations(
            resolved_unsupported=["set.payment"], dropped_cost_fields=[]
        ),
        "edit_target_errors": errors,
    }


def probe_display_facts():
    from argus.agent_runtime.confirmation_facts import confirmation_display_facts

    inputs = dict(zip(FIELDS, (0.0, None, 0.0, 12.0, 12000.0), strict=False))
    return confirmation_display_facts(
        strategy=inputs, optional_parameters={}, launch_payload={}
    )


def probe_next_rows():
    from argus.agent_runtime.next_experiments_contract import (
        NEXT_EXPERIMENTS_VERSION,
        continuity_next_experiment_kind,
        next_experiment_label_key,
        offered_kinds_from_thread_metadata,
    )

    kind = "solve_for_unknown"
    return {
        "version": NEXT_EXPERIMENTS_VERSION,
        "label_key": next_experiment_label_key(kind),
        "offered": offered_kinds_from_thread_metadata(
            {"next_experiments_offered_kinds": [kind]}
        ),
        "continuity": continuity_next_experiment_kind(
            action_type="refine_strategy", action_payload={"next_experiment_kind": kind}
        ),
    }


def probe_presentation():
    from argus.domain.artifact_presentation_kind import artifact_presentation_kind

    return {
        "own_key": artifact_presentation_kind({"calculation_card": {}}),
        "result_key": artifact_presentation_kind({"result_card": {}}),
    }


def probe_retry():
    from argus.agent_runtime.artifacts.lifecycle import (
        retry_lifecycle_after_artifact_event,
    )

    return {
        "decision": str(
            retry_lifecycle_after_artifact_event(
                retry_artifact_id="proof",
                latest_failed_artifact_id="proof",
                new_artifact_kind="time_value_of_money",
            )
        )
    }


def probe_registry():
    from argus.domain.capability_registry import RegisteredStrategyTemplate
    from argus.domain.strategy_capabilities import StrategyCapability
    from pydantic import TypeAdapter, ValidationError

    errors = []
    for attempt in (
        lambda: TypeAdapter(RegisteredStrategyTemplate).validate_python(
            "solve_for_unknown"
        ),
        lambda: StrategyCapability(
            template="solve_for_unknown",
            display_name="",
            aliases=[],
            execution_strategy_type="solve_for_unknown",
            supported_asset_classes=[],
        ),
    ):
        try:
            attempt()
        except ValidationError as exc:
            errors.append(
                [
                    {"loc": list(item["loc"]), "type": item["type"]}
                    for item in exc.errors()
                ]
            )
        else:
            raise AssertionError("unexpected registered calculation")
    return {"errors": errors}


def run_probe(name, boundary):
    import importlib.abc
    import sys

    forbidden = {"body": BODY_ROOTS, "catalog": CATALOG_ROOTS, "observe": ()}[boundary]
    assert name != "lifecycle_write" or boundary != "observe"

    class BlockedImport(ImportError):
        pass

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if any(
                fullname == root or fullname.startswith(root + ".") for root in forbidden
            ):
                raise BlockedImport(fullname)

    def refuse_network(event, args):
        if event in ("socket.connect", "socket.getaddrinfo"):
            raise RuntimeError("network_forbidden_in_unit_proof")

    sys.addaudithook(refuse_network)
    sys.meta_path.insert(0, Guard())
    record = {"probe": name, "boundary": boundary}
    try:
        record.update(status="returned", result=globals()["probe_" + name]())
    except BlockedImport as exc:
        record.update(status="blocked", blocked_import=str(exc))
    record["loaded_argus_modules"] = sorted(
        name for name in sys.modules if name.startswith("argus.")
    )
    return record


PROBES = [
    (name, boundary)
    for name in (
        "calculation",
        "transport",
        "confirmation_payload",
        "lifecycle",
        "next_rows",
        "presentation",
        "retry",
        "registry",
        "edit_bookkeeping",
        "display_facts",
    )
    for boundary in ("body", "catalog", "observe")
] + [("lifecycle_write", "body")]


@pytest.fixture(scope="module")
def observations():
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    results = []
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(Path(__file__).resolve().parents[3] / "src"),
    }
    for name, boundary in PROBES:
        completed = subprocess.run(
            [sys.executable, __file__, "--probe", name, boundary],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            check=True,
        )
        results.append(json.loads(completed.stdout))
    # Opt-in durable evidence capture; ordinary reruns do not modify the tree.
    output = os.environ.get("LANE_C_EVIDENCE_PATH")
    if output:
        from hashlib import sha256

        proof_dir = Path(__file__).resolve().parent
        proof_files = {
            path.name: sha256(path.read_bytes()).hexdigest()
            for path in sorted(proof_dir.glob("*.py"))
        }
        Path(output).write_text(
            json.dumps(
                {
                    "source_base": subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], text=True
                    ).strip(),
                    "python": sys.version.split()[0],
                    "proof_file_sha256": proof_files,
                    "body_import_guard": list(BODY_ROOTS),
                    "catalog_import_guard": list(CATALOG_ROOTS),
                    "observations": results,
                },
                indent=2,
            )
            + "\n"
        )
    return {(row["probe"], row["boundary"]): row for row in results}


@pytest.mark.parametrize("name,boundary", PROBES)
def test_real_import_boundary_is_observed(name, boundary, observations):
    row = observations[name, boundary]
    should_block = (
        name == "lifecycle_write"
        or (boundary == "body" and name in ("edit_bookkeeping", "display_facts"))
        or (
            boundary == "catalog"
            and name not in ("calculation", "lifecycle", "presentation")
        )
    )
    assert row["status"] == ("blocked" if should_block else "returned"), row


def test_envelope_bodies_do_not_silently_become_calculations(observations):
    def result(name):
        return observations[name, "observe"]["result"]

    assert result("transport")["round_trip"]
    assert result("confirmation_payload")["confirmation_errors"] == [
        {"loc": ["strategy"], "type": "missing"}
    ]
    assert result("confirmation_payload")["intent_errors"] == ["literal_error"]
    assert result("confirmation_payload")["facts_preserved"]
    assert result("lifecycle") == {
        "own_kind_unchanged": True,
        "confirmation_state": "superseded",
    }
    assert result("edit_bookkeeping")["accepted"] == ["payment", "rate"]
    assert result("edit_bookkeeping")["partially_materialized"]
    assert result("edit_bookkeeping")["edit_target_errors"] == ["literal_error"]
    assert result("edit_bookkeeping")["unapplied"] == [
        {"op": "set", "target": "payment", "reason": "unsupported_operation"}
    ]
    assert result("display_facts") == {}
    assert result("next_rows")["offered"] == ["solve_for_unknown"]
    assert result("next_rows")["continuity"] is None
    assert result("presentation") == {"own_key": None, "result_key": "result"}
    assert result("retry") == {"decision": "active"}
    assert len(result("registry")["errors"]) == 2


if __name__ == "__main__":
    import json
    import sys

    assert sys.argv[1] == "--probe"
    print(json.dumps(run_probe(sys.argv[2], sys.argv[3])))


def test_small_positive_growth_is_not_rounded_to_zero_before_division():
    assert solve_for_unknown(None, 0, -0.5, 60, -(0.5**60)) == pytest.approx(1)


@pytest.mark.parametrize("rate", [0.0, 1.0])
def test_ambiguous_rate_fixture_really_has_two_solutions(rate):
    assert balance_after(100, -300, rate, 2) == 500
    with pytest.raises(ValueError, match="exactly_one_cash_flow_sign_change"):
        solve_for_unknown(100, -300, None, 2, 500)
