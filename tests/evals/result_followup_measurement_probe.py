"""One #606 subprocess, importing the selected source tree after env admission."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import sys
from contextlib import ExitStack
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import patch


def compose_case(case: dict[str, Any], *, language: str, live: bool) -> dict[str, Any]:
    """Use actual composition and sidecars; only offline model replies are authored.

    Fixed authored asset-history dates are part of the input packet on both
    sides. This measures the result composer, not asset discovery or the engine.
    """
    from argus.agent_runtime import result_conversation as conversation
    from argus.agent_runtime.result_followup_answers import (
        result_answer_sidecars,
        result_next_experiments,
    )
    from argus.api.schemas import BacktestRun
    from argus.domain.backtest_message_projection import result_fact_bank
    from argus.domain.research.contracts import ResearchUsage
    from argus.domain.research.perplexity_agent import (
        PerplexityAgentClient,
        StructuredAgentResult,
    )
    from argus.llm.openrouter import (
        _json_schema_payload,
        begin_openrouter_route_receipt_capture,
        end_openrouter_route_receipt_capture,
        openrouter_profile_for_task,
        openrouter_structured_model_candidates,
    )

    metadata = result_fact_bank(BacktestRun.model_validate(case["run"]))
    rows = result_next_experiments(
        metadata, language=language, source_run_id=case["run"]["id"]
    )
    if not rows:
        raise ValueError("fixture_has_no_runnable_test_rows")
    requests: list[dict[str, Any]] = []
    draft = {
        "language": language,
        "text": case["offline_answer"][language],
        "figures": [],
        "next_steps": [
            {"kind": rows["rows"][0]["kind"], "text": ""},
            {"kind": "question", "text": case["offline_question"][language]},
        ],
    }

    class OfflineAgent:
        def run_structured(self, prompt: str, spec: Any, **kwargs: Any) -> Any:
            class RequestCaptured(Exception):
                pass

            def capture(payload: dict[str, Any], **unused: Any) -> Any:
                requests.append({"provider": "perplexity_agent", "payload": payload})
                raise RequestCaptured

            client = PerplexityAgentClient("offline-placeholder")
            with patch.object(client, "_post", side_effect=capture):
                try:
                    client.run_structured(prompt, spec, **kwargs)
                except RequestCaptured:
                    pass
            return StructuredAgentResult(
                draft=draft,
                sources=(),
                usage=ResearchUsage(model=spec.models[0], cost_usd=0),
                tool_results=(),
                provider_response_id="offline_authored",
            )

    async def offline_chat(**kwargs: Any) -> Any:
        for model in openrouter_structured_model_candidates(None, task=kwargs["task"]):
            payload = _json_schema_payload(
                model=model,
                messages=kwargs["messages"],
                schema_model=kwargs["schema_model"],
                schema_name=kwargs["schema_name"],
                profile=openrouter_profile_for_task(kwargs["task"]),
            )
            requests.append(
                {"provider": "openrouter", "payload": payload, "task": kwargs["task"]}
            )
        return kwargs["schema_model"].model_validate(draft)

    def network_refused(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("offline_network_forbidden")

    token = begin_openrouter_route_receipt_capture()
    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "argus.domain.market_data.asset_history_start",
                side_effect=lambda symbol, asset_class: date.fromisoformat(
                    case["history_starts"][symbol]
                ),
            )
        )
        if not live:
            stack.enter_context(patch("httpx.Client.send", side_effect=network_refused))
            stack.enter_context(
                patch("httpx.AsyncClient.send", side_effect=network_refused)
            )
            stack.enter_context(
                patch("socket.socket.connect", side_effect=network_refused)
            )
        try:
            answer = asyncio.run(
                conversation.compose_result_conversation_answer(
                    metadata=metadata,
                    user_message=case["prompts"][language],
                    language=language,
                    next_test_rows=rows["rows"],
                    research=case["research"],
                    **(
                        {}
                        if live
                        else {
                            "client": OfflineAgent(),
                            "invoke_json_schema_func": offline_chat,
                        }
                    ),
                )
            )
        finally:
            receipts = [
                asdict(receipt) for receipt in end_openrouter_route_receipt_capture(token)
            ]
    return {
        "evidence_kind": "live_model_on_authored_results"
        if live
        else "offline_request_shape_only",
        "semantic_review": "pending_manual_review" if live else "not_measured",
        "case_id": case["id"],
        "language": language,
        "research_requested": case["research"],
        "source_fixture_kind": case["source"]["kind"],
        "loaded_prompt_module": str(Path(conversation.__file__).resolve()),
        "loaded_prompt_module_sha256": hashlib.sha256(
            Path(conversation.__file__).read_bytes()
        ).hexdigest(),
        "metadata": metadata,
        "history_starts": case["history_starts"],
        "facts": conversation.run_headline_facts(metadata),
        "accepted_text": answer.text,
        "answer_source": answer.source,
        "failure_mode": answer.failure_mode,
        "accepted_steps": [asdict(step) for step in answer.next_steps],
        "sidecars": result_answer_sidecars(answer, rows, offer_tests=case["offer_tests"]),
        "offered_test_rows": rows,
        "requests": requests,
        "route_receipts": receipts,
        "provider_calls": None if live else 0,
    }


def native_suite(root: Path) -> dict[str, Any]:
    """Execute the complete native measurement entrypoint exactly once."""
    import pytest

    from tests.evals import test_measurement_eval_live as native
    from tests.evals.measurement_eval_scorecard import SCORECARD_DIR
    from tests.test_interpreter_prompt_freeze import FINGERPRINT_PATH

    directory = root / SCORECARD_DIR
    before = set(directory.glob("*.json"))
    failures: list[str] = []
    try:
        with pytest.MonkeyPatch.context() as monkeypatch:
            native.test_measurement_live_eval_suite_writes_scorecard(monkeypatch)
    except Exception as exc:
        failures.append(f"native_suite:{type(exc).__name__}")
    after = set(directory.glob("*.json")) - before
    if len(after) != 1:
        return {"failed_checks": [*failures, "native_scorecard_missing_or_ambiguous"]}
    path = after.pop()
    current = json.loads(path.read_text())
    fingerprint = json.loads((root / FINGERPRINT_PATH).read_text())
    frozen_path = root / fingerprint["last_measured"]["scorecard"]
    frozen = json.loads(frozen_path.read_text())
    prior = {row["id"]: row for row in frozen["results"]}
    comparisons = [
        {
            "id": row["id"],
            "frozen_status": prior.get(row["id"], {}).get("status"),
            "measured_status": row["status"],
            "failed_checks": row.get("failed_checks", []),
        }
        for row in current["results"]
    ]
    return {
        "failed_checks": failures,
        "scorecard_path": str(path),
        "scorecard": current,
        "frozen_scorecard_path": str(frozen_path),
        "frozen_totals": frozen["totals"],
        "case_comparison": comparisons,
    }


def main(payload: dict[str, Any]) -> None:
    # Do not import Argus, the native suite, or configuration before this step.
    if payload["live"]:
        from dotenv import load_dotenv

        from tests.evals.measurement_eval_scorecard import assert_eval_env_file_untracked

        env_file = Path(payload["env_file"])
        root = Path(payload["repository_root"])
        assert_eval_env_file_untracked(env_file, repository_root=root)
        load_dotenv(env_file, override=False)
        os.environ["ARGUS_EVAL_ENV_FILE"] = str(env_file)
        os.environ["ARGUS_RUN_LIVE_EVALS"] = "1"
        # Preloading the authorized file must be the only dotenv source.
        os.environ["PYTHON_DOTENV_DISABLED"] = "1"
        from tests.evals.measurement_spend_guard import guard_http, read_budget
        from tests.promotion_evidence_configuration import (
            assert_release_configuration_matches,
            measured_release_configuration,
        )

        configuration = measured_release_configuration(
            payload["expected_head"], repository_root=root
        )
        assert_release_configuration_matches(
            configuration,
            shipped_sha=payload["expected_head"],
            repository_root=root,
            evidence="issue606",
        )
        if not payload.get("native") and payload["case"]["research"]:
            from argus.domain.research.credentials import perplexity_api_key

            if not perplexity_api_key():
                raise ValueError("research_credentials_required")
        with guard_http(
            Path(payload["ledger"]), payload["rates"], live=True, scope=payload["scope"]
        ):
            result = (
                native_suite(root)
                if payload.get("native")
                else compose_case(
                    payload["case"], language=payload["language"], live=True
                )
            )
        budget = read_budget(Path(payload["ledger"]))
        result.update(
            release_configuration=configuration,
            candidate_sha=payload["expected_head"],
            baseline=payload.get("baseline"),
            variant=payload.get("variant"),
            fixture_sha256=payload["fixture_sha256"],
            python_version=platform.python_version(),
            provider_trace=[
                request
                for request in budget["requests"]
                if request["scope"] == payload["scope"]
            ],
        )
    else:
        result = compose_case(payload["case"], language=payload["language"], live=False)
    Path(payload["output"]).write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n"
    )


if __name__ == "__main__":
    main(json.load(sys.stdin))
