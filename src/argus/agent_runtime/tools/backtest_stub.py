from __future__ import annotations

from copy import deepcopy
from typing import Any


class StubBacktestTool:
    def __init__(self, responses: list[dict[str, Any]]):
        self._responses = [deepcopy(response) for response in responses]
        self.calls: list[dict[str, Any]] = []

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(deepcopy(payload))
        if not self._responses:
            raise RuntimeError("StubBacktestTool has no remaining responses.")
        return deepcopy(self._responses.pop(0))
