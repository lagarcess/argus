"""Emit browser fixtures through a real test-only declaration, without money math."""

import asyncio
import json
from pathlib import Path

from argus.agent_runtime.tools.registered_backtest import (
    backtest_execution_result,
    get_backtest_declaration,
)
from argus.domain.tool_contracts import (
    LocalizedText,
    ToolCall,
    ToolCardPresentation,
    ToolFact,
    ToolInputFact,
    ToolOutcome,
)
from argus.domain.tool_declaration import (
    ExactlyOneUnknown,
    ToolCardBinding,
    ToolDeclaration,
    ToolPolicy,
    ToolProgressTemplate,
)
from pydantic import BaseModel, ConfigDict

from tests.agent_runtime.test_registered_backtest_presentation import _completed_final


class EchoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    known: float | None = None
    other: float | None = None
    unknown: float | None = None


class EchoReturn(BaseModel):
    value: float | None


def echo(arguments: EchoArguments) -> EchoReturn:
    return EchoReturn(value=arguments.known)


def label(key: str, **facts: str) -> LocalizedText:
    return LocalizedText(locale_key=key, interpolation_args=facts)


def present(arguments: EchoArguments, outcome: ToolOutcome) -> ToolCardPresentation:
    return ToolCardPresentation(
        title=label("tools.card.title"),
        answer=ToolFact(
            name="answer",
            label=label("tools.card.solved_value"),
            value=(outcome.result or {}).get("value"),
        ),
        inputs=[
            ToolInputFact(
                name=name,
                label=label("tools.card.named_input", name=name),
                value=value,
                visibility="public",
            )
            for name, value in arguments.model_dump().items()
        ],
    )


DECLARATION = ToolDeclaration(
    name="test_echo",
    description="Return the supplied known value unchanged.",
    handler=echo,
    policy=ToolPolicy(editable_fields=("known", "other"), public_receipt="typed_facts"),
    progress=ToolProgressTemplate("tools.progress.value", ("known",)),
    card=ToolCardBinding("test_echo", 1, present),
    rules=(ExactlyOneUnknown(("known", "other", "unknown")),),
)


async def main() -> None:
    fixture = {}
    for name, known, other, revision, call_id in (
        ("initial", 0, 0, 0, "call-one"),
        ("sibling", 40, 0, 0, "call-two"),
        ("edited", 42, 7, 1, "call-one"),
        ("zero", 0, 7, 2, "call-one"),
    ):
        call = ToolCall(
            tool_name=DECLARATION.name,
            call_id=call_id,
            arguments={"known": known, "other": other, "unknown": None},
        )
        fixture[name] = DECLARATION.result_card(
            call=call,
            outcome=await DECLARATION.invoke(call.arguments),
            artifact_id=f"artifact-{call_id}",
            input_revision=revision,
        ).model_dump(mode="json")
    output = Path("docs/reports/evidence/registry/tool-cards.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(fixture, indent=2) + "\n")
    progress = DECLARATION.progress_facts(
        EchoArguments(known=0, other=0), call_id="call-one"
    )
    output.with_name("tool-progress.json").write_text(
        progress.model_dump_json(indent=2) + "\n"
    )
    backtests = {}
    declaration = get_backtest_declaration()
    for language in ("en", "es-419"):
        final, _, _ = _completed_final(language)
        card = declaration.result_card(
            call=ToolCall(
                tool_name=declaration.name,
                call_id="backtest-call",
                arguments={
                    "strategy": {"asset_universe": final["result_card"]["symbols"]}
                },
            ),
            outcome=ToolOutcome(
                status="succeeded",
                result=backtest_execution_result(final).model_dump(mode="json"),
            ),
            artifact_id="backtest-artifact",
        )
        backtests[language] = {
            "card": card.model_dump(mode="json"),
        }
    output.with_name("backtest-cards.json").write_text(
        json.dumps(backtests, indent=2) + "\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
