"""A declared test-only identity tool for public receipt contract tests."""

from argus.domain.tool_contracts import (
    LocalizedText,
    ToolCardPresentation,
    ToolFact,
    ToolOutcome,
)
from argus.domain.tool_declaration import (
    ToolCardBinding,
    ToolDeclaration,
    ToolPolicy,
    ToolProgressTemplate,
)
from pydantic import BaseModel, ConfigDict


class IdentityArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    known: float
    unknown: float | None = None


class IdentityResult(BaseModel):
    value: float


def identity(arguments: IdentityArguments) -> IdentityResult:
    return IdentityResult(value=arguments.known)


def present(arguments: IdentityArguments, outcome: ToolOutcome) -> ToolCardPresentation:
    return ToolCardPresentation(
        title=LocalizedText(locale_key="chat.tools.identity.title"),
        answer=ToolFact(
            name="value",
            label=LocalizedText(locale_key="chat.tools.identity.value"),
            value=outcome.result["value"],
        )
        if outcome.status == "succeeded"
        else None,
    )


def identity_declaration(*, public_receipt="typed_facts") -> ToolDeclaration:
    return ToolDeclaration(
        name="identity_value",
        description="Return the given test value.",
        handler=identity,
        policy=ToolPolicy(public_receipt=public_receipt),
        progress=ToolProgressTemplate("chat.tools.identity.progress", ("known",)),
        card=ToolCardBinding("identity_value", 1, present),
    )
