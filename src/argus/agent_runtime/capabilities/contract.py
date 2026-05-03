from __future__ import annotations

from copy import deepcopy
from numbers import Real
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from argus.agent_runtime.state.models import IntentName, SimplificationOption


def freeze_contract_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(
            {key: freeze_contract_payload(nested_value) for key, nested_value in value.items()}
        )
    if isinstance(value, list):
        return tuple(freeze_contract_payload(item) for item in value)
    if isinstance(value, tuple):
        return tuple(freeze_contract_payload(item) for item in value)
    if isinstance(value, set):
        return frozenset(freeze_contract_payload(item) for item in value)
    if isinstance(value, frozenset):
        return frozenset(freeze_contract_payload(item) for item in value)
    return value


def clone_contract_payload(value: Any) -> Any:
    if isinstance(value, MappingProxyType):
        return {
            key: clone_contract_payload(nested_value)
            for key, nested_value in value.items()
        }
    if isinstance(value, tuple):
        return [clone_contract_payload(item) for item in value]
    if isinstance(value, frozenset):
        return {clone_contract_payload(item) for item in value}
    return deepcopy(value)


class CapabilityRange(BaseModel):
    model_config = ConfigDict(frozen=True)

    minimum: float | None = None
    maximum: float | None = None
    allowed_values: tuple[Any, ...] = ()


class ValidationRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    field_name: str
    rule_type: str
    message: str


class FieldDescription(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str
    description: str


class OptionalParameterSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    default_value: Any
    description: FieldDescription
    allowed_range: CapabilityRange | None = None

    @model_validator(mode="after")
    def freeze_default_value(self) -> "OptionalParameterSpec":
        object.__setattr__(
            self,
            "default_value",
            freeze_contract_payload(self.default_value),
        )
        return self


class UnsupportedCombination(BaseModel):
    model_config = ConfigDict(frozen=True)

    fields: dict[str, Any]
    reason: str

    @model_validator(mode="after")
    def freeze_fields(self) -> "UnsupportedCombination":
        object.__setattr__(
            self,
            "fields",
            MappingProxyType(
                {
                    key: freeze_contract_payload(value)
                    for key, value in self.fields.items()
                }
            ),
        )
        return self


class SimplificationTemplate(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: str
    options: tuple[SimplificationOption, ...] = ()


class CapabilityContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str
    supported_intents: tuple[IntentName, ...] = ()
    supported_tool_families: tuple[str, ...] = ()
    required_field_descriptions: dict[str, FieldDescription] = Field(default_factory=dict)
    optional_parameters: dict[str, OptionalParameterSpec] = Field(default_factory=dict)
    validation_rules: tuple[ValidationRule, ...] = ()
    unsupported_combinations: tuple[UnsupportedCombination, ...] = ()
    simplification_templates: dict[str, SimplificationTemplate] = Field(default_factory=dict)

    @property
    def required_fields(self) -> list[str]:
        return list(self.required_field_descriptions)

    @property
    def optional_defaults(self) -> dict[str, Any]:
        return {
            name: clone_contract_payload(spec.default_value)
            for name, spec in self.optional_parameters.items()
        }

    @property
    def allowed_ranges(self) -> dict[str, CapabilityRange]:
        return {
            name: deepcopy(spec.allowed_range)
            for name, spec in self.optional_parameters.items()
            if spec.allowed_range is not None
        }

    def get_optional_parameter(self, name: str) -> OptionalParameterSpec:
        return deepcopy(self.optional_parameters[name])

    def get_allowed_range(self, name: str) -> CapabilityRange | None:
        parameter = self.optional_parameters.get(name)
        if parameter is None:
            return None
        return deepcopy(parameter.allowed_range)

    def get_simplification_options(self, category: str) -> list[SimplificationOption]:
        template = self.simplification_templates.get(category)
        if template is None:
            return []
        return [
            SimplificationOption.model_validate(option.model_dump(mode="python"))
            for option in template.options
        ]

    def describe_field(self, name: str) -> FieldDescription | None:
        if name in self.required_field_descriptions:
            return deepcopy(self.required_field_descriptions[name])
        parameter = self.optional_parameters.get(name)
        if parameter is None:
            return None
        return deepcopy(parameter.description)

    @model_validator(mode="after")
    def validate_contract_invariants(self) -> "CapabilityContract":
        object.__setattr__(
            self,
            "required_field_descriptions",
            MappingProxyType(dict(self.required_field_descriptions)),
        )
        object.__setattr__(
            self,
            "optional_parameters",
            MappingProxyType(dict(self.optional_parameters)),
        )
        object.__setattr__(
            self,
            "simplification_templates",
            MappingProxyType(dict(self.simplification_templates)),
        )

        overlapping_fields = set(self.required_field_descriptions).intersection(
            self.optional_parameters
        )
        if overlapping_fields:
            raise ValueError(
                "Required and optional capability fields must not overlap."
            )

        declared_fields = set(self.required_field_descriptions).union(
            self.optional_parameters
        )
        unknown_rule_fields = {
            rule.field_name
            for rule in self.validation_rules
            if rule.field_name not in declared_fields
        }
        if unknown_rule_fields:
            unknown_names = ", ".join(sorted(unknown_rule_fields))
            raise ValueError(
                f"Validation rules reference unknown capability fields: {unknown_names}."
            )

        unknown_combination_fields = {
            field_name
            for combination in self.unsupported_combinations
            for field_name in combination.fields
            if field_name not in declared_fields
        }
        if unknown_combination_fields:
            unknown_names = ", ".join(sorted(unknown_combination_fields))
            raise ValueError(
                "Unsupported combinations reference unknown capability fields: "
                f"{unknown_names}."
            )

        mismatched_template_categories = {
            category
            for category, template in self.simplification_templates.items()
            if template.category != category
        }
        if mismatched_template_categories:
            category_names = ", ".join(sorted(mismatched_template_categories))
            raise ValueError(
                "Simplification template keys must match their declared category: "
                f"{category_names}."
            )

        for parameter_name, parameter in self.optional_parameters.items():
            self._validate_optional_parameter_default(
                parameter_name=parameter_name,
                parameter=parameter,
            )
        return self

    @staticmethod
    def _validate_optional_parameter_default(
        *,
        parameter_name: str,
        parameter: OptionalParameterSpec,
    ) -> None:
        allowed_range = parameter.allowed_range
        if allowed_range is None:
            return

        default_value = parameter.default_value

        if allowed_range.allowed_values and default_value not in allowed_range.allowed_values:
            allowed_values = ", ".join(str(value) for value in allowed_range.allowed_values)
            raise ValueError(
                f"Optional parameter '{parameter_name}' has default '{default_value}' "
                f"outside allowed values: {allowed_values}."
            )

        if not isinstance(default_value, Real) or isinstance(default_value, bool):
            return

        if allowed_range.minimum is not None and default_value < allowed_range.minimum:
            raise ValueError(
                f"Optional parameter '{parameter_name}' has default {default_value} "
                f"below minimum {allowed_range.minimum}."
            )
        if allowed_range.maximum is not None and default_value > allowed_range.maximum:
            raise ValueError(
                f"Optional parameter '{parameter_name}' has default {default_value} "
                f"above maximum {allowed_range.maximum}."
            )


def build_default_capability_contract() -> CapabilityContract:
    return CapabilityContract(
        version="1.0",
        supported_intents=[
            "strategy_drafting",
            "backtest_execution",
            "results_explanation",
        ],
        supported_tool_families=[
            "backtest_tools",
            "education_tools",
        ],
        required_field_descriptions={
            "strategy_thesis": FieldDescription(
                label="Strategy thesis",
                description="Plain-language summary of the investing idea being tested.",
            ),
            "asset_universe": FieldDescription(
                label="Assets",
                description="Symbols included in the same-asset-class backtest.",
            ),
            "entry_logic": FieldDescription(
                label="Entry logic",
                description="What conditions open the position.",
            ),
            "exit_logic": FieldDescription(
                label="Exit logic",
                description="What conditions close the position.",
            ),
            "date_range": FieldDescription(
                label="Date range",
                description="Historical period used for the simulation.",
            ),
        },
        optional_parameters={
            "initial_capital": OptionalParameterSpec(
                default_value=10000.0,
                description=FieldDescription(
                    label="Initial capital",
                    description="Starting cash for the simulated backtest.",
                ),
                allowed_range=CapabilityRange(minimum=1000.0),
            ),
            "timeframe": OptionalParameterSpec(
                default_value="1D",
                description=FieldDescription(
                    label="Timeframe",
                    description="Bar interval used for the simulation.",
                ),
                allowed_range=CapabilityRange(
                    allowed_values=("1h", "2h", "4h", "6h", "12h", "1D")
                ),
            ),
            "fees": OptionalParameterSpec(
                default_value=0.0,
                description=FieldDescription(
                    label="Fees",
                    description="Per-trade fee assumption applied during execution.",
                ),
                allowed_range=CapabilityRange(minimum=0.0),
            ),
            "slippage": OptionalParameterSpec(
                default_value=0.0,
                description=FieldDescription(
                    label="Slippage",
                    description="Execution slippage assumption expressed as a fraction.",
                ),
                allowed_range=CapabilityRange(minimum=0.0, maximum=0.05),
            ),
            "engine_options": OptionalParameterSpec(
                default_value={},
                description=FieldDescription(
                    label="Engine options",
                    description="Reserved execution knobs exposed by the runtime contract.",
                ),
            ),
        },
        validation_rules=[
            ValidationRule(
                field_name="asset_universe",
                rule_type="max_length",
                message="Backtests support up to 5 symbols per run.",
            ),
            ValidationRule(
                field_name="date_range",
                rule_type="required_for_execution",
                message="A date range is required before a backtest can run.",
            ),
        ],
        unsupported_combinations=[],
        simplification_templates={
            "unsupported_time_granularity": SimplificationTemplate(
                category="unsupported_time_granularity",
                options=(
                    SimplificationOption(
                        label="Retry with daily bars",
                        replacement_values={"timeframe": "1D"},
                    ),
                    SimplificationOption(
                        label="Retry with 1-hour bars",
                        replacement_values={"timeframe": "1h"},
                    ),
                ),
            ),
            "unsupported_asset_mix": SimplificationTemplate(
                category="unsupported_asset_mix",
                options=(
                    SimplificationOption(
                        label="Run the strategy with equity symbols only",
                        replacement_values={"asset_class": "equity"},
                    ),
                    SimplificationOption(
                        label="Run the strategy with crypto symbols only",
                        replacement_values={"asset_class": "crypto"},
                    ),
                    SimplificationOption(
                        label="Split into separate equity and crypto runs",
                        replacement_values={"split_runs": True},
                    ),
                ),
            ),
            "unsupported_strategy_logic": SimplificationTemplate(
                category="unsupported_strategy_logic",
                options=(
                    SimplificationOption(
                        label="Simplify to RSI-only logic",
                        replacement_values={"simplify_logic": "rsi_only"},
                    ),
                ),
            ),
        },
    )
