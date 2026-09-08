"""Record real Perplexity Agent API responses under the retrieval parameters.

Run from the repository root at the committed head the recordings vouch for:

    poetry run python docs/reports/evidence/545/probe_retrieval_parameters.py \\
        --env-file .env --output-dir docs/reports/evidence/545/probes --probe all

Every probe goes through the repository's own client, prompt builder and spec
derivation, so the recorded request is byte for byte what production sends.
Each file holds the request body, the HTTP status, the raw response, the
parsed packet and the candidate SHA. The API key is read from the env file
and never written. Every probe is a paid provider call.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

PROBE_DIR = Path(__file__).resolve().parent


class RecordingHTTPTransport(httpx.HTTPTransport):
    """The real transport, with every exchange kept for the record."""

    def __init__(self) -> None:
        super().__init__()
        self.exchanges: list[dict[str, Any]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = super().handle_request(request)
        response.read()
        body: Any = None
        if request.content:
            body = json.loads(request.content.decode())
        try:
            document: Any = json.loads(response.content.decode())
        except ValueError:
            document = response.content.decode(errors="replace")[:2000]
        self.exchanges.append(
            {
                "method": request.method,
                "url": str(request.url),
                "request": body,
                "http_status": response.status_code,
                "response": document,
            }
        )
        return response


def _packet_summary(packet: Any) -> dict[str, Any]:
    return {
        "typed_answer": packet.typed_answer,
        "uncited_rows": packet.uncited_rows,
        "rows": [row.model_dump() for row in packet.rows],
        "sources": [source.model_dump() for source in packet.sources],
        "tool_results": list(packet.tool_results),
        "tickers": list(packet.tickers),
        "usage": json.loads(packet.usage.model_dump_json()),
        "answer_markdown": packet.answer_markdown,
    }


def _record(
    *,
    name: str,
    purpose: str,
    sha: str,
    transport: RecordingHTTPTransport,
    started: float,
    packet: Any = None,
    error: str | None = None,
    request_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "probe": name,
        "purpose": purpose,
        "candidate_sha": sha,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(time.monotonic() - started, 2),
        "request_overrides": request_overrides or {},
        "exchanges": transport.exchanges,
        "packet": _packet_summary(packet) if packet is not None else None,
        "error": error,
    }


def run_probe(name: str, *, sha: str) -> dict[str, Any]:
    """One probe, with the home market set only for the local-source call so
    every other recording shows the request a deployment without a declared
    market sends."""
    previous = os.environ.pop("ARGUS_RESEARCH_HOME_COUNTRY", None)
    if name.startswith("domain_filtered_"):
        os.environ["ARGUS_RESEARCH_HOME_COUNTRY"] = "DO"
    try:
        return _run_probe(name, sha=sha)
    finally:
        os.environ.pop("ARGUS_RESEARCH_HOME_COUNTRY", None)
        if previous is not None:
            os.environ["ARGUS_RESEARCH_HOME_COUNTRY"] = previous


def _run_probe(name: str, *, sha: str) -> dict[str, Any]:
    from argus.agent_runtime import research_grounded as grounded
    from argus.domain.research.config import PRIMARY_MODEL, retrieval_spec
    from argus.domain.research.contracts import ResearchUnavailableError
    from argus.domain.research.credentials import perplexity_api_key
    from argus.domain.research.perplexity_agent import (
        PerplexityAgentClient,
        _packet_from_response,
    )

    transport = RecordingHTTPTransport()
    client = PerplexityAgentClient(perplexity_api_key(), transport=transport)
    started = time.monotonic()
    nvda = [{"symbol": "NVDA", "name": "NVIDIA", "asset_class": "equity"}]

    if name == "fast_quote_typed":
        spec = retrieval_spec("fast", question_kind="live_quote", language_tag="en")
        prompt = grounded._research_prompt(
            message="What is Apple trading at right now?",
            subjects=[{"symbol": "AAPL", "name": "Apple", "asset_class": "equity"}],
            period=None,
            language="en",
            question_kind="live_quote",
        )
        purpose = "fast shape under the strict schema and the fallback chain"
    elif name == "typed_rows_current_external":
        spec = retrieval_spec(
            "balanced", question_kind="current_external", language_tag="en"
        )
        prompt = grounded._research_prompt(
            message="Why is NVIDIA stock moving this week?",
            subjects=nvda,
            period=None,
            language="en",
            question_kind="current_external",
            publisher_sources_required=True,
        )
        purpose = "#545: typed rows and dated publisher sources, one-week recency"
    elif name == "domain_filtered_local_source":
        spec = retrieval_spec(
            "balanced",
            question_kind="current_external",
            language_tag="es-419",
            local_sources=True,
        )
        prompt = grounded._research_prompt(
            message=(
                "¿Qué tasa de interés paga hoy el Banco Popular Dominicano por "
                "un certificado financiero a un año en pesos?"
            ),
            subjects=[],
            period=None,
            language="es-419",
            question_kind="current_external",
            publisher_sources_required=True,
        )
        purpose = "domain-filtered call citing a local source, DO location, es"
    elif name == "domain_filtered_rate_publishers_no_recency":
        # The same candidate publishers without the one-week recency filter:
        # a rate table is updated monthly, so a current-facts recency window
        # can exclude the very page that carries the figure.
        spec = retrieval_spec(
            "balanced",
            question_kind="current_external",
            language_tag="es-419",
            local_sources=True,
        ).model_copy(
            update={
                "source_domains": (
                    "popularenlinea.com",
                    "sb.gob.do",
                    "bancentral.gov.do",
                ),
                "recency": None,
            }
        )
        prompt = grounded._research_prompt(
            message=(
                "¿Qué tasa de interés pasiva promedio pagan los bancos "
                "dominicanos hoy por un certificado financiero a un año en pesos?"
            ),
            subjects=[],
            period=None,
            language="es-419",
            question_kind="current_external",
            publisher_sources_required=True,
        )
        purpose = (
            "mechanism demonstration: the same candidate rate publishers with no "
            "recency filter"
        )
    elif name == "domain_filtered_rate_publishers":
        # Not the seed list. A mechanism demonstration for the founder's list
        # decision: which candidate Dominican publishers actually carry a
        # retrievable rate. The regulator and the central bank publish every
        # bank's rates; a bank's own site may not.
        spec = retrieval_spec(
            "balanced",
            question_kind="current_external",
            language_tag="es-419",
            local_sources=True,
        ).model_copy(
            update={
                "source_domains": ("popularenlinea.com", "sb.gob.do", "bancentral.gov.do")
            }
        )
        prompt = grounded._research_prompt(
            message=(
                "¿Qué tasa de interés pasiva promedio pagan los bancos "
                "dominicanos hoy por un certificado financiero a un año en pesos?"
            ),
            subjects=[],
            period=None,
            language="es-419",
            question_kind="current_external",
            publisher_sources_required=True,
        )
        purpose = (
            "mechanism demonstration with candidate rate publishers, not the seed "
            "list: does a local rate arrive as a cited row"
        )
    elif name == "market_pulse_vaguest_rail":
        spec = retrieval_spec("balanced", question_kind="market_pulse", language_tag="en")
        prompt = ""
        purpose = (
            "#404 end to end: the rail's grounded path on the vaguest phrasing, "
            "including the concrete retry it fires on a figureless typed answer"
        )
    elif name in RETRY_VARIANTS:
        spec = retrieval_spec(
            "balanced", question_kind="market_pulse", language_tag="en"
        ).model_copy(
            update={
                "tools": ("finance_search",),
                "typed_output": name != "retry_variant_prose",
            }
        )
        prompt = grounded._survey_retry_prompt(
            question_kind="market_pulse",
            message="anything interesting moving today",
            language="en",
        )
        purpose = RETRY_VARIANTS[name]
    elif name == "market_pulse_retry_finance_only":
        # Operating rule 5: movers are a structured finance dataset. The
        # concrete retry asked with only the finance tool available, so the
        # model cannot spend its steps reconstructing the table from web prose.
        spec = retrieval_spec(
            "balanced", question_kind="market_pulse", language_tag="en"
        ).model_copy(update={"tools": ("finance_search",)})
        prompt = grounded._survey_retry_prompt(
            question_kind="market_pulse",
            message="anything interesting moving today",
            language="en",
        )
        purpose = "#404: the concrete survey retry with the finance tool alone"
    elif name in ("market_pulse_vaguest", "tool_choice_required"):
        spec = retrieval_spec("balanced", question_kind="market_pulse", language_tag="en")
        prompt = grounded._research_prompt(
            message="anything interesting moving today",
            subjects=[],
            period=None,
            language="en",
            question_kind="market_pulse",
        )
        purpose = (
            "#404: the vaguest market pulse under instructions and the schema"
            if name == "market_pulse_vaguest"
            else "#404: whether an undocumented tool_choice=required is accepted"
        )
    elif name == "models_fallback_forced":
        spec = retrieval_spec(
            "fast", question_kind="live_quote", language_tag="en"
        ).model_copy(update={"models": ("openai/does-not-exist-model", PRIMARY_MODEL)})
        prompt = grounded._research_prompt(
            message="What is Apple trading at right now?",
            subjects=[{"symbol": "AAPL", "name": "Apple", "asset_class": "equity"}],
            period=None,
            language="en",
            question_kind="live_quote",
        )
        purpose = "the fallback chain: an unavailable first model is passed over"
    elif name == "thorough_typed_background":
        spec = retrieval_spec(
            "thorough", question_kind="cross_company", language_tag="en"
        )
        prompt = grounded._research_prompt(
            message=(
                "Compare Netflix and Disney revenue growth over the last two "
                "fiscal years."
            ),
            subjects=[
                {"symbol": "NFLX", "name": "Netflix", "asset_class": "equity"},
                {"symbol": "DIS", "name": "Walt Disney", "asset_class": "equity"},
            ],
            period="last two fiscal years",
            language="en",
            question_kind="cross_company",
        )
        purpose = "thorough background run on the Anthropic path under the schema"
    else:
        raise SystemExit(f"unknown probe {name}")

    overrides: dict[str, Any] = {}
    try:
        if name == "market_pulse_vaguest_rail":
            return _rail_survey_record(
                name=name,
                purpose=purpose,
                sha=sha,
                transport=transport,
                started=started,
                client=client,
            )
        if name in RAW_OVERRIDES:
            body = client._request_body(prompt, spec)
            overrides = RAW_OVERRIDES[name]
            for key, value in overrides.items():
                if value is None:
                    body.pop(key, None)
                else:
                    body[key] = value
            document = client._post(body, timeout_seconds=spec.timeout_seconds)
            packet = _packet_from_response(document, latency_ms=0)
        elif spec.background:
            background_id = client.submit_background(prompt, spec)
            deadline = time.monotonic() + 600
            packet = None
            while time.monotonic() < deadline:
                time.sleep(5)
                poll = client.poll_background(background_id, spec=spec)
                if poll.terminal:
                    if poll.status != "completed":
                        raise ResearchUnavailableError(
                            "background", f"{poll.status}: {poll.failure_detail}"
                        )
                    packet = poll.packet
                    break
                # Keep the record small: only the submit and the terminal poll.
                transport.exchanges = transport.exchanges[:1]
            if packet is None:
                raise ResearchUnavailableError("timeout", "background deadline")
        else:
            packet = client.run_research(prompt, spec)
    except ResearchUnavailableError as exc:
        return _record(
            name=name,
            purpose=purpose,
            sha=sha,
            transport=transport,
            started=started,
            error=f"{exc.reason}: {exc.detail or ''}",
            request_overrides=overrides,
        )
    return _record(
        name=name,
        purpose=purpose,
        sha=sha,
        transport=transport,
        started=started,
        packet=packet,
        request_overrides=overrides,
    )


def _rail_survey_record(
    *,
    name: str,
    purpose: str,
    sha: str,
    transport: RecordingHTTPTransport,
    started: float,
    client: Any,
) -> dict[str, Any]:
    """Drive the rail's own grounded path, not the bare client, so the
    recording shows every provider exchange the turn makes and the sidecar
    the reader gets. Assets resolve against the live provider catalog, the
    way production verifies a survey's named tickers."""
    import asyncio

    from argus.agent_runtime import research_grounded as grounded
    from argus.agent_runtime.research_query import ResearchQueryExtraction
    from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
    from argus.agent_runtime.state.models import RunState, StrategySummary, UserState

    os.environ["ARGUS_MARKET_DATA_PROVIDER_MODE"] = "live_provider"
    grounded._client = lambda: client  # type: ignore[assignment]
    message = "anything interesting moving today"
    result = asyncio.run(
        grounded.grounded_result(
            query=ResearchQueryExtraction(question_kind="market_pulse", symbols=[]),
            subjects=[],
            shape="balanced",
            interpretation=StructuredInterpretation(
                intent="unsupported_or_out_of_scope",
                task_relation="new_task",
                user_goal_summary="question",
                semantic_turn_act="educational_question",
                requires_clarification=False,
                candidate_strategy_draft=StrategySummary(),
            ),
            state=RunState.new(current_user_message=message, recent_thread_history=[]),
            user=UserState(user_id="probe", language_preference="en"),
        )
    )
    record = _record(
        name=name, purpose=purpose, sha=sha, transport=transport, started=started
    )
    patch = result.stage_patch if result is not None else {}
    record["turn"] = {
        "message": message,
        "assistant_response": patch.get("assistant_response"),
        "research": patch.get("research"),
        "next_experiments": patch.get("next_experiments"),
    }
    return record


# Candidate wording for the retrieval instructions, tried against the retry
# that refused to call the finance tool under the shipped wording.
INSTRUCTIONS_RETRIEVAL_FIRST = (
    "You are the retrieval service of a finance calculator. Call the available "
    "tools before answering: every current figure you state must come from a "
    "tool result in this response, never from memory. Reply in the requested "
    "JSON shape. answer_markdown is the prose for the reader: no links, no list "
    "of sources, no mention of tools, providers or models. Every figure "
    "answer_markdown states appears once in rows, with the URL of the tool "
    "result or page it was read from. Only when the tools return no figure at "
    "all, say so in one sentence."
)

RETRY_VARIANTS = {
    "retry_variant_prose": (
        "isolation: the same finance-only retry with no instructions and no "
        "schema, the pre-lane request shape"
    ),
    "retry_variant_no_instructions": (
        "isolation: the strict schema without the instructions text"
    ),
    "retry_variant_instructions_v2": (
        "isolation: the strict schema with retrieval-first instructions"
    ),
}

# Raw request overrides applied after the client builds the body; None
# removes the key.
RAW_OVERRIDES: dict[str, dict[str, Any]] = {
    "tool_choice_required": {"tool_choice": "required"},
    "retry_variant_no_instructions": {"instructions": None},
    "retry_variant_instructions_v2": {"instructions": INSTRUCTIONS_RETRIEVAL_FIRST},
}

PROBES = (
    "fast_quote_typed",
    "typed_rows_current_external",
    "domain_filtered_local_source",
    "domain_filtered_rate_publishers",
    "domain_filtered_rate_publishers_no_recency",
    "market_pulse_vaguest",
    "market_pulse_vaguest_rail",
    "market_pulse_retry_finance_only",
    "retry_variant_prose",
    "retry_variant_no_instructions",
    "retry_variant_instructions_v2",
    "models_fallback_forced",
    "tool_choice_required",
    "thorough_typed_background",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=PROBE_DIR / "probes")
    parser.add_argument("--probe", nargs="+", default=["all"])
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    # Recordings are untracked until they are committed, so only tracked
    # modifications make the head something the recording cannot vouch for.
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], text=True
    ).strip()
    if dirty and not args.allow_dirty:
        raise SystemExit("Recordings vouch for a committed head; commit first")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    load_dotenv(args.env_file, override=False)
    if not os.getenv("PERPLEXITY_API_KEY", "").strip():
        raise SystemExit("PERPLEXITY_API_KEY is not configured in the env file")
    names = list(PROBES) if args.probe == ["all"] else args.probe
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        record = run_probe(name, sha=sha)
        path = args.output_dir / f"{name}.json"
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
        packet = record["packet"] or {}
        print(
            json.dumps(
                {
                    "probe": name,
                    "elapsed_s": record["elapsed_s"],
                    "error": record["error"],
                    "typed_answer": packet.get("typed_answer"),
                    "rows": len(packet.get("rows", [])),
                    "uncited_rows": packet.get("uncited_rows"),
                    "sources": [s["url"] for s in packet.get("sources", [])][:5],
                    "served_model": (packet.get("usage") or {}).get("model"),
                    "cost_usd": (packet.get("usage") or {}).get("cost_usd"),
                    "tool_results": packet.get("tool_results"),
                }
            )
        )


if __name__ == "__main__":
    main()
