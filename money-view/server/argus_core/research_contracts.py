"""The citation type tool cards need, without loading the research runtime."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ResearchSource(BaseModel):
    """One real reader-visible source returned by a research endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str
    title: str = ""
    source_date: str | None = None
