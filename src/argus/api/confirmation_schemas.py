"""Typed request models for no-turn confirmation mutations.

Split from api/schemas.py so the deterministic confirmation-patch surface
grows here instead of in the watched module. These models depend on nothing
from schemas, so either import order works; the Message-bearing response
models stay beside Message.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator


class ConfirmationPeerAssetsRequest(BaseModel):
    """Grow or restore the pending confirmation's basket without a turn.

    Add mode: only symbols the active turn offered as research peer rows are
    addable; the backend re-verifies each against the resolver and coverage
    gates. Restore mode undoes the latest add by re-materializing the exact
    previous asset set from the card's own typed adjustment data.
    """

    symbols: list[str] | None = Field(default=None, min_length=1, max_length=4)
    restore_previous: bool = False

    @model_validator(mode="after")
    def require_one_mode(self) -> "ConfirmationPeerAssetsRequest":
        if self.restore_previous == bool(self.symbols):
            raise ValueError("symbols_or_restore_required")
        return self


class ConfirmationDirectEditWindow(BaseModel):
    """Explicit calendar endpoints from the drawer's date inputs.

    Direct edits are deterministic UI values, never prose: relative or
    semantic windows stay on the conversational path where the interpreter
    owns them.
    """

    start: str = Field(min_length=10, max_length=10)
    end: str = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def require_ordered_iso_dates(self) -> "ConfirmationDirectEditWindow":
        try:
            start = date.fromisoformat(self.start)
            end = date.fromisoformat(self.end)
        except ValueError as exc:
            raise ValueError("invalid_date_window") from exc
        if start > end:
            raise ValueError("invalid_date_window")
        return self


class ConfirmationDirectEditRequest(BaseModel):
    """Edit the pending confirmation's capital, dates, or costs without a turn.

    At least one field is required. Capital is the starting capital, or the
    recurring contribution when the pending strategy is a recurring-buy plan,
    matching the money-role semantics of the conversational path. Costs are
    decimal rates (0.002 is 0.2 percent); zero explicitly clears a cost. The
    slippage cap is enforced by the shared edit resolver, not re-stated here.
    """

    capital: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    date_window: ConfirmationDirectEditWindow | None = None
    fee_rate: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    slippage: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def require_one_edit(self) -> "ConfirmationDirectEditRequest":
        if (
            self.capital is None
            and self.date_window is None
            and self.fee_rate is None
            and self.slippage is None
        ):
            raise ValueError("at_least_one_edit_required")
        return self
