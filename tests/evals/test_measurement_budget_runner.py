import json
from contextlib import nullcontext
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from tests.evals.measurement_budget_runner import run_budgeted_cases


@dataclass
class Provenance:
    candidate_sha: str = "offline-test"


class Stop(BaseException):
    pass


class Budget:
    def case(self, _case_id):
        return nullcontext()

    def snapshot(self):
        return {"spent_usd": "0"}

    def assert_complete(self):
        pass


@pytest.mark.parametrize("stop", [False, True])
def test_serial_measurement_retains_results_without_claiming_partial_completion(
    tmp_path, stop
):
    cases = [SimpleNamespace(id=str(index)) for index in range(3)]
    attempted = []

    def run(case):
        attempted.append(case.id)
        if stop and case.id == "1":
            raise Stop("sensitive provider detail")
        return {"id": case.id, "status": "passed"}

    progress = tmp_path / "progress.json"
    with pytest.raises(Stop) if stop else nullcontext():
        results = run_budgeted_cases(
            cases,
            run_case=run,
            budget=Budget(),
            provenance=Provenance(),
            progress_path=progress,
        )
        assert len(results) == len(cases)
    report = json.loads(progress.read_text())
    assert report["status"] == ("incomplete" if stop else "completed")
    assert attempted == (["0", "1"] if stop else ["0", "1", "2"])
    assert len(report["results"]) == (1 if stop else 3)
    assert report["interrupted_case_id"] == ("1" if stop else None)
    assert "sensitive" not in progress.read_text()
