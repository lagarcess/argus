"""Guard coverage of the two readout composers without widening other APIs."""

from pathlib import Path

import pytest

from tests.interpreter_prompt_surface import model_facing_surface


def _write(root: Path, name: str, source: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_inline_readout_system_prompt_changes_its_fingerprint(tmp_path: Path) -> None:
    owner = "src/argus/agent_runtime/stages/explain.py"
    source = 'messages = [{"role": "system", "content": "Explain the ride."}]'
    _write(tmp_path, owner, source)
    first = model_facing_surface(tmp_path)
    assert owner in first
    _write(tmp_path, owner, source.replace("ride", "drawdown"))
    assert model_facing_surface(tmp_path)[owner] != first[owner]


def test_breakdown_prompt_and_schema_are_covered_without_other_api_prose(
    tmp_path: Path,
) -> None:
    owner = "src/argus/api/chat/breakdown.py"
    source = """
def messages():
    return [{"role": "system", "content": "Explain the stored result."}]
class Draft:
    text = Field(description="Complete grounded explanation.")
"""
    _write(tmp_path, owner, source)
    _write(tmp_path, "src/argus/api/chat/unrelated.py", source)
    first = model_facing_surface(tmp_path)
    assert set(first) == {owner}
    assert first[owner]["entries"] == 2
    _write(tmp_path, owner, source.replace("Complete grounded", "Concise grounded"))
    assert model_facing_surface(tmp_path)[owner] != first[owner]


def test_unrelated_inline_runtime_dictionary_does_not_expand_fingerprint(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "src/argus/agent_runtime/unrelated.py",
        'data = {"role": "system", "content": "Not a readout owner."}',
    )
    assert model_facing_surface(tmp_path) == {}


def test_shared_readout_instruction_constant_is_fingerprinted(tmp_path: Path) -> None:
    owner = "src/argus/domain/result_readout_grounding.py"
    source = 'READOUT_GROUNDING_INSTRUCTIONS = "Use stored figures only."'
    _write(tmp_path, owner, source)
    first = model_facing_surface(tmp_path)
    assert owner in first
    _write(tmp_path, owner, source.replace("stored figures", "supplied numbers"))
    assert model_facing_surface(tmp_path)[owner] != first[owner]


@pytest.mark.parametrize(
    "owner",
    [
        "src/argus/domain/result_readout_fact_sheet.py",
        "src/argus/domain/result_readout_fact_definitions.py",
    ],
)
def test_readout_fact_meanings_are_measured_but_docstrings_are_not(
    tmp_path: Path, owner: str
) -> None:
    source = '''"""Internal implementation notes."""
FACT_DEFINITIONS = {"executed_fills": ("count", "Executed fills, not closed trades.")}
def build():
    """Implementation detail."""
    return {"meaning": "Annualized volatility."}
'''
    _write(tmp_path, owner, source)
    first = model_facing_surface(tmp_path)
    assert owner in first
    _write(tmp_path, owner, source.replace("Annualized volatility", "Daily volatility"))
    assert model_facing_surface(tmp_path)[owner] != first[owner]
    _write(tmp_path, owner, source.replace("Implementation detail", "Private helper"))
    assert model_facing_surface(tmp_path)[owner] == first[owner]
