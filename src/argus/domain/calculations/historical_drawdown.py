"""A historical asset drawdown, with a provider-owned observation window."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from argus.domain.calculations._shared import (
    input_fact,
    note,
    number_fact,
    percent_fact,
    text,
)
from argus.domain.market_data.historical_drawdown import (
    HistoricalDrawdownObservation,
    observe_historical_drawdown,
)
from argus.domain.tool_contracts import ToolCardPresentation, ToolFactSource, ToolOutcome
from argus.domain.tool_declaration import (
    ToolCardBinding,
    ToolDeclaration,
    ToolPolicy,
    ToolProgressTemplate,
)


class HistoricalDrawdownArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    sources: dict[str, ToolFactSource] = Field(default_factory=dict)
    symbol: str = Field(min_length=1, max_length=24)
    start_date: date | None = None
    end_date: date | None = None


def compute_historical_drawdown(
    arguments: HistoricalDrawdownArguments,
) -> HistoricalDrawdownObservation:
    return observe_historical_drawdown(
        arguments.symbol, start_date=arguments.start_date, end_date=arguments.end_date
    )


def present_historical_drawdown(
    arguments: HistoricalDrawdownArguments, outcome: ToolOutcome
) -> ToolCardPresentation:
    title = text("tools.calc.historical_drawdown.title")
    inputs = [input_fact("symbol", arguments.symbol)]
    for name in ("start_date", "end_date"):
        value = getattr(arguments, name)
        if value is not None:
            inputs.append(input_fact(name, value.isoformat()))
    if outcome.status != "succeeded":
        return ToolCardPresentation(title=title, inputs=inputs)
    result = HistoricalDrawdownObservation.model_validate(outcome.result)
    source = ToolFactSource(kind="market_data", date=result.observed_end_date.isoformat())
    answer = percent_fact("max_drawdown_pct", result.max_drawdown_pct / 100).model_copy(
        update={"source": source}
    )
    rows = [
        number_fact("observed_start_date", result.observed_start_date.isoformat()),
        number_fact("observed_end_date", result.observed_end_date.isoformat()),
        number_fact("observations", result.observations),
    ]
    for name in ("peak_date", "trough_date"):
        value = getattr(result, name)
        if value is not None:
            rows.append(number_fact(name, value))
    notes = [note("historical_daily_closes")]
    if result.default_window:
        notes.append(
            note(
                "historical_default_window",
                start=result.requested_start_date.isoformat(),
                end=result.requested_end_date.isoformat(),
            )
        )
    return ToolCardPresentation(
        title=title, answer=answer, inputs=inputs, rows=rows, notes=notes
    )


def get_historical_drawdown_declaration() -> ToolDeclaration:
    return ToolDeclaration(
        name="historical_drawdown",
        description=(
            "Measure an asset's worst historical peak-to-trough percentage decline "
            "from Argus market-data daily closes. Supply the symbol and optional "
            "start_date/end_date; omitted dates use five years ending yesterday. "
            "The result reports the actual observation window, not an all-time or "
            "intraday loss, and does not predict future losses."
        ),
        handler=compute_historical_drawdown,
        policy=ToolPolicy(
            execution="provider",
            external_calls=1,
            ends_answer=True,
            confirmation="never",
            public_receipt="typed_facts",
        ),
        progress=ToolProgressTemplate(
            locale_key="tools.calc.historical_drawdown.progress"
        ),
        card=ToolCardBinding(
            card_type="historical_drawdown",
            version=1,
            presenter=present_historical_drawdown,
        ),
        domain=("Only Argus market data supplies the historical price series.",),
    )
