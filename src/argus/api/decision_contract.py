"""Decision wire contracts.

A decision attaches to a computation and carries what a re-run needs. Two
attachments exist, and every row holds exactly one:

- A backtest decision attaches to its evidence artifact. The run behind that
  artifact owns the computation, so the row stores none (``computation`` is
  ``None``) and readers derive ``{"kind": "backtest", "inputs":
  {"source_run_id": ...}}`` from the artifact.
- A computed-answer decision attaches to the assistant message that carried
  the answer and stores the computation the answer declared, so the decision
  survives the message and re-runs on its own.

The same rule is a check constraint on ``decision_notes``.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DecisionState = Literal["watching", "promising", "rejected", "revisit_later"]
DecisionActionAvailability = Literal[
    "available",
    "account_conversion_required",
]
DecisionRerunStatus = Literal["computed", "confirmation_required", "unavailable"]
DecisionRerunReasonCode = Literal[
    "kernel_unavailable",
    "invalid_inputs",
    "inputs_not_editable",
    "run_unavailable",
    "retest_unavailable",
]

DECISION_NOTE_WRITE_MAX_LENGTH = 500
COMPUTATION_KIND_MAX_LENGTH = 80
COMPUTATION_INPUTS_MAX_KEYS = 32
COMPUTATION_INPUTS_MAX_SERIALIZED_LENGTH = 8_192


def bounded_computation_inputs(value: dict[str, Any]) -> dict[str, Any]:
    """Inputs are a small JSON object; the bound keeps a row from becoming a blob."""
    if len(value) > COMPUTATION_INPUTS_MAX_KEYS:
        raise ValueError(
            f"Computation inputs may carry at most {COMPUTATION_INPUTS_MAX_KEYS} keys."
        )
    try:
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("Computation inputs must be JSON-serializable.") from exc
    if len(serialized) > COMPUTATION_INPUTS_MAX_SERIALIZED_LENGTH:
        raise ValueError(
            "Computation inputs may serialize to at most "
            f"{COMPUTATION_INPUTS_MAX_SERIALIZED_LENGTH} characters."
        )
    return value


class DecisionComputation(BaseModel):
    """What a decision can re-run: a registered kind and its typed inputs."""

    model_config = ConfigDict(frozen=True)

    kind: str = Field(
        min_length=1,
        max_length=COMPUTATION_KIND_MAX_LENGTH,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    inputs: dict[str, Any] = Field(default_factory=dict)

    @field_validator("inputs")
    @classmethod
    def bound_inputs(cls, value: dict[str, Any]) -> dict[str, Any]:
        return bounded_computation_inputs(value)


class DecisionNote(BaseModel):
    id: str
    idea_id: str | None = None
    idea_version_id: str | None = None
    evidence_artifact_id: str | None = None
    source_conversation_id: str | None = None
    source_message_id: str | None = None
    computation: DecisionComputation | None = None
    decision_state: DecisionState
    note: str | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def attach_to_exactly_one_computation_owner(self) -> DecisionNote:
        artifact_attached = self.evidence_artifact_id is not None
        if artifact_attached == (self.computation is not None):
            raise ValueError(
                "A decision attaches to exactly one of an evidence artifact "
                "or a stored computation."
            )
        if artifact_attached != (self.idea_id is not None) or artifact_attached != (
            self.idea_version_id is not None
        ):
            raise ValueError(
                "Idea and idea version identities travel with the evidence artifact."
            )
        return self


class DecisionNoteCreate(BaseModel):
    decision_state: DecisionState
    note: str | None = Field(
        default=None,
        max_length=DECISION_NOTE_WRITE_MAX_LENGTH,
    )

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class MessageDecisionResponse(BaseModel):
    decision: DecisionNote


class DecisionRerunRequest(BaseModel):
    """Input overrides merged over the stored inputs; the decision is unchanged."""

    model_config = ConfigDict(extra="forbid")

    inputs: dict[str, Any] = Field(default_factory=dict)

    @field_validator("inputs")
    @classmethod
    def bound_inputs(cls, value: dict[str, Any]) -> dict[str, Any]:
        return bounded_computation_inputs(value)


class SearchDossierDecision(BaseModel):
    state: DecisionState
    note: str | None = Field(default=None, max_length=2000)
    run_label: str | None = Field(default=None, max_length=160)


RetestDossierState = Literal["new_data_available", "no_new_data", "cant_do_it"]
RetestWindowViolationCode = Literal[
    "provider_history_start_unavailable",
    "kraken_ohlc_window_exceeded",
    "provider_timeframe_unavailable",
]


class SearchRetestRepair(BaseModel):
    kind: Literal["clamp_start"] = "clamp_start"
    start_date: date
    end_date: date


class SearchRetestAction(BaseModel):
    """Bounded typed retest envelope (spec 2.2).

    Carries identity and policy only. The executable setup is reloaded
    server-side from the owner-scoped source run, so no client value can
    reach canonical state.
    """

    type: Literal["retest_run"] = "retest_run"
    source_run_id: str
    run_label: str = Field(max_length=160)
    window_policy: Literal["preserve_start_ending_latest_available"] = (
        "preserve_start_ending_latest_available"
    )
    contract_version: Literal["argus_retest_run/v2"] = "argus_retest_run/v2"
    state: RetestDossierState
    reason_code: RetestWindowViolationCode | None = None
    repair: SearchRetestRepair | None = None

    @model_validator(mode="after")
    def validate_state_shape(self) -> SearchRetestAction:
        if self.state != "cant_do_it":
            if self.reason_code is not None or self.repair is not None:
                raise ValueError("Only cant_do_it may carry a reason or repair")
            return self
        if self.reason_code is None:
            raise ValueError("cant_do_it requires a reason_code")
        repairable = self.reason_code in {
            "provider_history_start_unavailable",
            "kraken_ohlc_window_exceeded",
        }
        if repairable != (self.repair is not None):
            raise ValueError("Retest repair must match the reason_code")
        return self


class SearchDecisionAction(BaseModel):
    type: Literal["decision"] = "decision"
    availability: DecisionActionAvailability
    evidence_artifact_id: str
    decision_state: DecisionState | None = None
    note: str | None = Field(default=None, max_length=2000)
    run_label: str = Field(max_length=160)


class DecisionRerun(BaseModel):
    """The outcome of opening or re-running a decision's computation.

    ``computed`` carries the kernel's typed result. ``confirmation_required``
    carries the typed retest action for a backtest, which earns its
    confirmation by cost and never executes here. ``unavailable`` names why
    nothing ran, as a code, never prose.
    """

    kind: str
    inputs: dict[str, Any]
    status: DecisionRerunStatus
    result: dict[str, Any] | None = None
    retest: SearchRetestAction | None = None
    reason_code: DecisionRerunReasonCode | None = None

    @model_validator(mode="after")
    def validate_status_shape(self) -> DecisionRerun:
        if self.status == "unavailable":
            if self.reason_code is None:
                raise ValueError("unavailable requires a reason_code")
            if self.result is not None or self.retest is not None:
                raise ValueError("unavailable carries neither a result nor a retest")
            return self
        if self.reason_code is not None:
            raise ValueError("Only unavailable may carry a reason_code")
        if self.status == "computed" and self.result is None:
            raise ValueError("computed requires a result")
        if self.status == "confirmation_required" and self.retest is None:
            raise ValueError("confirmation_required requires a retest action")
        return self


class DecisionOpenResponse(BaseModel):
    decision: DecisionNote
    computation: DecisionComputation
    rerun: DecisionRerun
