"""The prompt gate must measure generated facts the model actually receives."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from faker import Faker

from tests.interpreter_prompt_surface import model_facing_surface, surface_drift

CATALOG_SURFACE = "generated/tool_catalog.json"
RESPONSE_SURFACE = "generated/interpretation_response_schema.json"
PROMPT_SURFACE = "generated/interpreter_system_prompt.json"
GENERATED_SURFACES = (CATALOG_SURFACE, RESPONSE_SURFACE, PROMPT_SURFACE)


@pytest.fixture
def generated_repository(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    """A real importable checkout whose generated values are not Python literals."""

    for package in (
        "argus", "argus/domain", "argus/agent_runtime", "argus/agent_runtime/capabilities"
    ):
        directory = tmp_path / "src" / package
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src/argus/domain/capability_registry.py").write_text(
        _CATALOG_MODULE, encoding="utf-8"
    )
    (tmp_path / "src/argus/agent_runtime/llm_interpreter_types.py").write_text(
        _RESPONSE_MODULE, encoding="utf-8"
    )
    (tmp_path / "src/argus/agent_runtime/llm_interpreter.py").write_text(
        _INTERPRETER_MODULE, encoding="utf-8"
    )
    (tmp_path / "src/argus/agent_runtime/capabilities/contract.py").write_text(
        "def build_default_capability_contract():\n    return object()\n",
        encoding="utf-8",
    )
    fake = Faker()
    data: dict[str, object] = {
        "description": fake.sentence(),
        "minimum": 0,
        "capability_text": fake.sentence(),
        "intents": ["explain", "calculate"],
        "research_description": fake.sentence(),
        "strategy_capability": fake.sentence(),
    }
    _write_data(tmp_path, data)
    return tmp_path, data


def _write_data(root: Path, data: dict[str, object]) -> None:
    (root / "catalog.json").write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.parametrize(
    ("field", "replacement", "changed_surfaces"),
    [
        ("description", "Return the supplied value unchanged.", (CATALOG_SURFACE, PROMPT_SURFACE)),
        ("minimum", 1, GENERATED_SURFACES),
        ("capability_text", "Only the declared operation is available.", (CATALOG_SURFACE, PROMPT_SURFACE)),
        ("intents", ["explain", "calculate", "cannot"], (RESPONSE_SURFACE,)),
    ],
)
def test_generated_contract_changes_cannot_escape_fingerprint(
    generated_repository: tuple[Path, dict[str, object]],
    field: str,
    replacement: object,
    changed_surfaces: tuple[str, ...],
) -> None:
    root, data = generated_repository
    before = model_facing_surface(root)
    _write_data(root, {**data, field: replacement})
    after = model_facing_surface(root)

    # Python source and Field.description strings did not change. The actual
    # catalog/schema changed, so the model-facing gate must still refuse it.
    changed, added, removed = surface_drift(before, after)
    assert changed == sorted(changed_surfaces)
    assert added == removed == []


def test_generated_surface_is_stable_across_fresh_processes_and_json_key_order(
    generated_repository: tuple[Path, dict[str, object]],
) -> None:
    root, data = generated_repository
    before = model_facing_surface(root)
    _write_data(root, dict(reversed(list(data.items()))))
    after = model_facing_surface(root)

    assert CATALOG_SURFACE in before
    assert RESPONSE_SURFACE in before
    assert PROMPT_SURFACE in before
    assert before == after


def test_generated_surface_reads_the_requested_checkout(
    generated_repository: tuple[Path, dict[str, object]],
    tmp_path: Path,
) -> None:
    import shutil

    root, data = generated_repository
    other = tmp_path / "other-checkout"
    shutil.copytree(root / "src", other / "src")
    _write_data(other, {**data, "capability_text": "Another checkout's catalog."})

    original = model_facing_surface(root)
    alternate = model_facing_surface(other)
    assert CATALOG_SURFACE in original
    assert CATALOG_SURFACE in alternate
    assert original[CATALOG_SURFACE] != alternate[CATALOG_SURFACE]


def test_generated_surface_refuses_network_during_import(
    generated_repository: tuple[Path, dict[str, object]],
) -> None:
    root, _ = generated_repository
    module = root / "src/argus/domain/capability_registry.py"
    module.write_text(
        module.read_text(encoding="utf-8")
        + '\nimport socket\nsocket.getaddrinfo("example.invalid", 443)\n',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="network_forbidden_in_prompt_surface"):
        model_facing_surface(root)


def test_generated_profiles_ignore_ambient_feature_flags(
    generated_repository: tuple[Path, dict[str, object]], monkeypatch,
) -> None:
    root, _ = generated_repository
    for name in ("ARGUS_RESEARCH_RAIL_ENABLED", "ARGUS_ENABLE_EXECUTION_REALISM"):
        monkeypatch.setenv(name, "true")
    enabled = model_facing_surface(root)
    for name in ("ARGUS_RESEARCH_RAIL_ENABLED", "ARGUS_ENABLE_EXECUTION_REALISM"):
        monkeypatch.setenv(name, "false")
    disabled = model_facing_surface(root)

    assert enabled == disabled
    for name in GENERATED_SURFACES:
        assert {
            (profile["research_rail_enabled"], profile["execution_realism_enabled"])
            for profile in enabled[name]["profiles"]
        } == {(False, False), (False, True), (True, False), (True, True)}
        assert enabled[name]["entries"] == 4
        assert enabled[name]["runtime_date"]


def test_disabled_environment_cannot_hide_enabled_catalog_changes(
    generated_repository: tuple[Path, dict[str, object]], monkeypatch,
) -> None:
    root, data = generated_repository
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    before = model_facing_surface(root)
    _write_data(root, {**data, "research_description": "A changed retrieval contract."})
    after = model_facing_surface(root)

    changed, added, removed = surface_drift(before, after)
    assert changed == sorted((CATALOG_SURFACE, PROMPT_SURFACE))
    assert added == removed == []


def test_rendered_prompt_captures_dynamic_strategy_capability_facts(
    generated_repository: tuple[Path, dict[str, object]],
) -> None:
    root, data = generated_repository
    before = model_facing_surface(root)
    _write_data(root, {**data, "strategy_capability": "A changed strategy contract."})
    after = model_facing_surface(root)

    assert surface_drift(before, after) == ([PROMPT_SURFACE], [], [])


def test_rendered_prompt_normalizes_only_the_runtime_clock(
    generated_repository: tuple[Path, dict[str, object]],
) -> None:
    root, _ = generated_repository
    before = model_facing_surface(root)
    module = root / "src/argus/agent_runtime/llm_interpreter.py"
    module.write_text(
        module.read_text(encoding="utf-8")
        + '\nfrom datetime import date as ActualDate\n'
        + 'date = type("AnotherDay", (), {"today": lambda: ActualDate(2099, 12, 31)})\n',
        encoding="utf-8",
    )
    after = model_facing_surface(root)

    assert PROMPT_SURFACE in before
    assert before == after


def test_removing_generated_factory_is_a_measured_surface_removal(
    generated_repository: tuple[Path, dict[str, object]],
) -> None:
    root, _ = generated_repository
    before = model_facing_surface(root)
    module = root / "src/argus/agent_runtime/llm_interpreter_types.py"
    module.write_text(
        module.read_text(encoding="utf-8").replace(
            "def interpretation_response_model", "def removed_response_factory"
        ),
        encoding="utf-8",
    )
    after = model_facing_surface(root)

    assert surface_drift(before, after) == ([], [], sorted(GENERATED_SURFACES))


def test_static_surface_still_works_for_a_checkout_before_the_tool_registry(
    tmp_path: Path,
) -> None:
    module = tmp_path / "src/argus/agent_runtime/llm_interpreter_types.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        'from pydantic import BaseModel, Field\n'
        'class Response(BaseModel):\n'
        '    value: str = Field(description="A structured value.")\n',
        encoding="utf-8",
    )

    surface = model_facing_surface(tmp_path)
    assert list(surface) == [str(module.relative_to(tmp_path))]
    assert surface[str(module.relative_to(tmp_path))]["entries"] == 1


_CATALOG_MODULE = '''
import json
import os
from pathlib import Path

def data():
    return json.loads((Path(__file__).resolve().parents[3] / "catalog.json").read_text())

class Declaration:
    def tool_schema(self):
        values = data()
        return {"name": "echo", "description": values["description"],
                "parameters": {"type": "object", "properties": {
                    "amount": {"type": "number", "minimum": values["minimum"]}}}}

class Catalog:
    def __init__(self):
        self.declarations = (Declaration(),)
        if os.getenv("ARGUS_RESEARCH_RAIL_ENABLED") == "true":
            self.declarations += (ResearchDeclaration(),)
    def capability_text(self):
        return data()["capability_text"] + json.dumps([
            declaration.tool_schema() for declaration in self.declarations
        ], sort_keys=True)

class ResearchDeclaration(Declaration):
    def tool_schema(self):
        return {**super().tool_schema(), "name": "retrieve",
                "description": data()["research_description"]}

def get_tool_catalog():
    return Catalog()
'''

_RESPONSE_MODULE = '''
from pydantic import create_model, Field
from typing import Literal
from argus.domain.capability_registry import data

def interpretation_response_model(tool_catalog=None):
    return create_model("Response", intent=(Literal[tuple(data()["intents"])], ...),
                        amount=(float, Field(ge=data()["minimum"])))
'''

_INTERPRETER_MODULE = '''
import os
from datetime import date
from argus.domain.capability_registry import data
from argus.agent_runtime.llm_interpreter_types import interpretation_response_model

class OpenRouterStructuredInterpreter:
    def __init__(self, *, contract, tool_catalog):
        self.tool_catalog = tool_catalog
        self.response_model = interpretation_response_model(tool_catalog)

    def _system_prompt(self):
        return ("Runtime date " + date.today().isoformat() + ". "
                + self.tool_catalog.capability_text() + data()["strategy_capability"]
                + " Execution costs: " + os.getenv("ARGUS_ENABLE_EXECUTION_REALISM", ""))
'''
