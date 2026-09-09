"""Template field contracts that do not load the catalog at model import time.

General envelopes may contain an optional strategy. Only validating a supplied
template or publishing its JSON-schema enum needs the backtest registry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from pydantic import AfterValidator, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema


def _registered_templates() -> frozenset[str]:
    from argus.domain.capability_registry import REGISTERED_STRATEGY_TEMPLATES

    return REGISTERED_STRATEGY_TEMPLATES


def _executable_templates() -> frozenset[str]:
    from argus.domain.capability_registry import EXECUTABLE_TEMPLATES

    return EXECUTABLE_TEMPLATES


@dataclass(frozen=True)
class _TemplateConstraint:
    templates: Callable[[], frozenset[str]]
    title: str
    error: str

    def validate(self, value: str) -> str:
        if value not in self.templates():
            raise ValueError(f"{self.error}: {value!r}")
        return value

    def __get_pydantic_json_schema__(
        self, _schema: CoreSchema, _handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return {
            "type": "string",
            "enum": sorted(self.templates()),
            "title": self.title,
        }


_registered = _TemplateConstraint(
    templates=_registered_templates,
    title="RegisteredStrategyTemplate",
    error="unrecognized strategy template",
)
_executable = _TemplateConstraint(
    templates=_executable_templates,
    title="StrategyTemplate",
    error="unsupported strategy template",
)

RegisteredStrategyTemplate = Annotated[
    str, AfterValidator(_registered.validate), _registered
]
ExecutableStrategyTemplate = Annotated[
    str, AfterValidator(_executable.validate), _executable
]
