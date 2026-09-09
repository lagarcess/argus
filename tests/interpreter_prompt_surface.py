"""Every piece of text this repo sends to an interpretation model.

Two channels reach the model: the instruction text in prompt builders, and the
schema field descriptions it fills in. Both steer interpretation for every turn,
so both are frozen together by `test_interpreter_prompt_freeze.py`.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

MEASURED_ROOTS = (
    "src/argus/agent_runtime",
    "src/argus/domain",
    "src/argus/llm",
    "src/argus/context",
    "src/argus/nlp",
)

FINGERPRINT_PATH = Path(".agent/interpreter_prompt_fingerprint.json")
_FIXED_RUNTIME_DATE = "2000-01-01"

_MESSAGE_CONSTRUCTORS = frozenset({"SystemMessage", "HumanMessage", "AIMessage"})
_PROMPT_FUNCTION_SUFFIXES = ("_prompt", "_instructions", "_directive", "_clause")
# String constants like DISCOVERY_ACT_GUIDANCE are concatenated into the
# interpreter's system prompt by name, so the prompt builder's own hash does
# not move when they change; they are hashed at their definition instead.
_GUIDANCE_CONSTANT_SUFFIX = "_GUIDANCE"


def _callee_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _joined_constants(node: ast.AST) -> str:
    """Concatenate every string constant under a node, in source order."""

    parts = [
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    ]
    return "".join(parts)


def _model_facing_strings(tree: ast.AST) -> list[tuple[str, str]]:
    """(kind, text) for every string this module hands to a model."""

    found: list[tuple[str, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.endswith(_PROMPT_FUNCTION_SUFFIXES):
                body = _joined_constants(node)
                if body:
                    found.append((f"def {node.name}", body))
            continue

        if isinstance(node, ast.Assign):
            target_names = [
                target.id for target in node.targets if isinstance(target, ast.Name)
            ]
            if (
                len(target_names) == 1
                and target_names[0].endswith(_GUIDANCE_CONSTANT_SUFFIX)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
                and node.value.value
            ):
                found.append((target_names[0], node.value.value))
            continue

        if not isinstance(node, ast.Call):
            continue

        callee = _callee_name(node)

        if callee in _MESSAGE_CONSTRUCTORS:
            text = _joined_constants(node)
            if text:
                found.append((callee, text))
            continue

        if callee == "Field":
            for keyword in node.keywords:
                if keyword.arg != "description":
                    continue
                text = _joined_constants(keyword.value)
                if text:
                    found.append(("Field.description", text))

    return found


def model_facing_surface(repository_root: Path) -> dict[str, dict[str, object]]:
    """Per-file digest of everything the interpretation model reads."""

    surface: dict[str, dict[str, object]] = {}

    for root in MEASURED_ROOTS:
        for path in sorted((repository_root / root).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue

            strings = _model_facing_strings(tree)
            if not strings:
                continue

            payload = chr(10).join(kind + chr(31) + text for kind, text in strings)
            relative = str(path.relative_to(repository_root))
            surface[relative] = {
                "entries": len(strings),
                "chars": sum(len(text) for _, text in strings),
                "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            }

    surface.update(_generated_model_facing_surface(repository_root))
    return surface


def _generated_model_facing_surface(
    repository_root: Path,
) -> dict[str, dict[str, object]]:
    """Measure emitted catalog/schema facts, including nonliteral enum values.

    Each explicit feature profile gets a fresh process, so a cached catalog,
    local environment or editable install cannot silently choose the surface.
    The actual rendered prompt uses a fixed clock value; only that changing
    runtime input is normalized, never registry values or schema choices.
    Older checkouts without the generated response factory retain their static
    surface; removing that factory from a measured branch removes these entries
    and therefore still fails the freeze gate.
    """

    module = repository_root / "src/argus/agent_runtime/llm_interpreter_types.py"
    if not module.is_file():
        return {}
    tree = ast.parse(module.read_text(encoding="utf-8"))
    if not any(
        isinstance(node, ast.FunctionDef)
        and node.name == "interpretation_response_model"
        for node in tree.body
    ):
        return {}
    generated: dict[str, list[dict[str, object]]] = {}
    profiles = [
        {
            "research_rail_enabled": research,
            "execution_realism_enabled": costs,
        }
        for research in (False, True)
        for costs in (False, True)
    ]
    for profile in profiles:
        completed = subprocess.run(
            [sys.executable, "-c", _GENERATED_SURFACE_SCRIPT, _FIXED_RUNTIME_DATE],
            cwd=repository_root,
            env={
                **os.environ,
                "PYTHONPATH": str(repository_root.resolve() / "src"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "ARGUS_RUN_LIVE_EVALS": "",
                "ARGUS_MARKET_DATA_PROVIDER_MODE": "synthetic_unit_fixture",
                "ARGUS_RESEARCH_RAIL_ENABLED": str(profile["research_rail_enabled"]).lower(),
                "ARGUS_ENABLE_EXECUTION_REALISM": str(profile["execution_realism_enabled"]).lower(),
                "OPENROUTER_API_KEY": "",
                "ALPACA_API_KEY": "",
                "ALPACA_SECRET_KEY": "",
                "PERPLEXITY_API_KEY": "",
            },
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if completed.returncode:
            raise RuntimeError(
                f"Generated model-facing surface could not be measured for {profile}:\n"
                + completed.stderr
            )
        for name, value in json.loads(completed.stdout).items():
            generated.setdefault(name, []).append({"profile": profile, "value": value})
    surface = {}
    for name, value in generated.items():
        payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        surface[name] = {
            "entries": len(profiles),
            "chars": len(payload),
            "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            "profiles": profiles,
            "runtime_date": _FIXED_RUNTIME_DATE,
        }
    return surface


_GENERATED_SURFACE_SCRIPT = """
import json
import sys
from datetime import date

def refuse_network(event, args):
    if event in ("socket.connect", "socket.getaddrinfo"):
        raise RuntimeError("network_forbidden_in_prompt_surface")

sys.addaudithook(refuse_network)

from argus.domain.capability_registry import get_tool_catalog
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime import llm_interpreter

fixed_day = date.fromisoformat(sys.argv[1])

class FixedDate(date):
    @classmethod
    def today(cls):
        return cls(fixed_day.year, fixed_day.month, fixed_day.day)

llm_interpreter.date = FixedDate

catalog = get_tool_catalog()
interpreter = llm_interpreter.OpenRouterStructuredInterpreter(
    contract=build_default_capability_contract(), tool_catalog=catalog,
)
print(json.dumps({
    "generated/tool_catalog.json": {
        "schemas": [declaration.tool_schema() for declaration in catalog.declarations],
        "capability_text": catalog.capability_text(),
    },
    "generated/interpretation_response_schema.json":
        interpreter.response_model.model_json_schema(),
    "generated/interpreter_system_prompt.json": interpreter._system_prompt(),
}, sort_keys=True))
"""


def load_fingerprint(repository_root: Path) -> dict[str, object]:
    return json.loads((repository_root / FINGERPRINT_PATH).read_text(encoding="utf-8"))


def surface_drift(
    recorded: dict[str, dict[str, object]],
    observed: dict[str, dict[str, object]],
) -> tuple[list[str], list[str], list[str]]:
    """(changed, added, removed) files, comparing digests only."""

    changed = sorted(
        name
        for name in recorded.keys() & observed.keys()
        if recorded[name]["sha256"] != observed[name]["sha256"]
    )
    return (
        changed,
        sorted(observed.keys() - recorded.keys()),
        sorted(recorded.keys() - observed.keys()),
    )
