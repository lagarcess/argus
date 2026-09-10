"""Serve existing writing outcomes through the actual read-only Argus API."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import socket
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from replay_data import load_inputs, source_numbers

ROOT = Path.cwd()
parser = argparse.ArgumentParser()
parser.add_argument("--report", type=Path, required=True)
parser.add_argument("--sha", required=True)
parser.add_argument("--api-port", type=int, default=8541)
parser.add_argument("--web-port", type=int, default=3221)
parser.add_argument("--synthetic-preflight", action="store_true")
args = parser.parse_args()
if subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() != args.sha:
    raise SystemExit("Reader checkout must match --sha")
if subprocess.check_output(
    ["git", "status", "--porcelain", "--", "src", "web"], text=True
).strip():
    raise SystemExit("Reader runtime source must be clean")
INPUT = load_inputs(ROOT, args.report, args.synthetic_preflight)

# An allowlist avoids reading linked .env files or inheriting unknown credentials.
environment = {
    key: value
    for key, value in os.environ.items()
    if key
    in {
        "PATH",
        "HOME",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "SYSTEMROOT",
        "VIRTUAL_ENV",
    }
}
os.environ.clear()
os.environ.update(environment)
os.environ.update(
    {
        "PYTHON_DOTENV_DISABLED": "1",
        "ARGUS_PERSISTENCE_MODE": "memory",
        "ARGUS_DEV_MEMORY_FALLBACK": "true",
        "ARGUS_CHECKPOINTER_MODE": "memory",
        "ARGUS_MOCK_AUTH": "true",
        "ARGUS_APP_ORIGIN": f"http://127.0.0.1:{args.web_port}",
        "ARGUS_CORS_ALLOW_ORIGINS": f"http://127.0.0.1:{args.web_port}",
        "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED": "false",
        "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED": "false",
        "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED": "false",
    }
)
import dotenv  # noqa: E402

dotenv.load_dotenv = lambda *unused, **kwargs: False
BLOCKED_NETWORK: list[str] = []
BLOCKED_MUTATIONS: list[str] = []
_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex
_dns = socket.getaddrinfo


def local(host: Any) -> bool:
    return host is None or str(host) in {"127.0.0.1", "::1", "localhost"}


def guard_address(address: Any) -> None:
    if isinstance(address, tuple) and not local(address[0]):
        BLOCKED_NETWORK.append("non_loopback_connect")
        raise RuntimeError("Offline replay forbids external network")


def connect(sock: socket.socket, address: Any) -> Any:
    guard_address(address)
    return _connect(sock, address)


def connect_ex(sock: socket.socket, address: Any) -> Any:
    guard_address(address)
    return _connect_ex(sock, address)


def dns(host: Any, *rest: Any, **kwargs: Any) -> Any:
    if not local(host):
        BLOCKED_NETWORK.append("non_loopback_dns")
        raise RuntimeError("Offline replay forbids external DNS")
    return _dns(host, *rest, **kwargs)


socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
socket.getaddrinfo = dns
sys.path.insert(0, str(ROOT / "src"))
from argus.api import state  # noqa: E402
from argus.api.main import app  # noqa: E402
from argus.api.schemas import BacktestRun, Conversation, Message  # noqa: E402
from argus.domain.backtest_message_projection import result_fact_bank  # noqa: E402
from argus.domain.result_readout_content import (  # noqa: E402
    READOUT_METADATA_KEYS,
    readout_metadata,
)
from starlette.responses import JSONResponse  # noqa: E402

CASES = []
user = state.store.get_or_create_dev_user()
for pair in INPUT["pairs"]:
    conversation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"final-writing/{pair['key']}"))
    run_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"final-writing/run/{pair['key']}"))
    stored = BacktestRun.model_validate(copy.deepcopy(pair["run"]))
    card = copy.deepcopy(stored.conversation_result_card)
    for key in READOUT_METADATA_KEYS:
        card.pop(key, None)
    metadata = {}
    for surface, outcome in pair["outcomes"].items():
        metadata[surface] = readout_metadata(
            surface=surface,
            text=outcome.get("accepted_text"),
            language=pair["language"],
            source=outcome.get("source") or "deterministic_fallback",
            fallback_used=not outcome["accepted"],
            failure_mode=outcome.get("failure_mode")
            or (None if outcome["accepted"] else "unavailable_measurement_outcome"),
        )
    card.update(metadata["quick_take"])
    stored = stored.model_copy(
        update={
            "id": run_id,
            "conversation_id": conversation_id,
            "conversation_result_card": card,
        }
    )
    facts = result_fact_bank(stored)
    rows = []
    for surface in ("quick_take", "breakdown"):
        message_metadata = {
            **metadata[surface],
            "result_run_id": run_id,
            "result_conversation_id": conversation_id,
            "result_fact_bank": facts,
        }
        if surface == "quick_take":
            message_metadata["result_card"] = card
        else:
            message_metadata.update(
                {
                    "artifact_presentation_kind": "breakdown",
                    "response_intent": {
                        "kind": "result_breakdown",
                        "facts": {"result_fact_bank": facts},
                    },
                }
            )
        rows.append(
            Message(
                id=str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL, f"final-writing/{pair['key']}/{surface}"
                    )
                ),
                conversation_id=conversation_id,
                role="assistant",
                content="",
                created_at=stored.created_at,
                metadata=message_metadata,
            )
        )
    state.store.backtest_runs[run_id] = stored
    state.store.backtest_run_owners[run_id] = user.id
    state.store.conversation_owners[conversation_id] = user.id
    state.store.messages[conversation_id] = rows
    state.store.conversations[conversation_id] = Conversation(
        id=conversation_id,
        title=f"Writing replay: {pair['key']}",
        title_source="user_renamed",
        language=pair["language"],
        created_at=stored.created_at,
        updated_at=stored.created_at,
        last_message_preview="Offline replay of measured writing outcomes",
    )
    CASES.append(
        {key: value for key, value in pair.items() if key != "run"}
        | {
            "conversation_id": conversation_id,
            "source_numbers": source_numbers(pair["run"]),
            "transport": metadata,
        }
    )


def stored_digest() -> str:
    payload = {
        "messages": {
            key: [m.model_dump(mode="json") for m in rows]
            for key, rows in state.store.messages.items()
        },
        "runs": {
            key: run.model_dump(mode="json")
            for key, run in state.store.backtest_runs.items()
        },
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


INITIAL_DIGEST = stored_digest()
READER_HASHES = {
    path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    for path in (
        "src/argus/api/artifact_presentation.py",
        "src/argus/domain/result_readout_content.py",
        "src/argus/domain/backtest_message_projection.py",
    )
}


@app.middleware("http")
async def offline_only(request: Any, call_next: Any) -> Any:
    if request.url.path == "/replay-proof":
        return JSONResponse(
            {
                "reader_sha": args.sha,
                "measurement_checkouts": INPUT["measurement_checkouts"],
                "report_path": INPUT["report_path"],
                "report_sha256": INPUT["report_sha256"],
                "fixture_sha256": INPUT["fixture_sha256"],
                "cases": CASES,
                "synthetic_browser_preflight": args.synthetic_preflight,
                "loaded_reader_hashes": READER_HASHES,
                "blocked_network": BLOCKED_NETWORK,
                "blocked_mutations": BLOCKED_MUTATIONS,
                "model_calls": 0,
                "backtest_calls": 0,
                "market_data_calls": 0,
                "stored_artifacts_unchanged": stored_digest() == INITIAL_DIGEST,
                "stored_artifacts_sha256": INITIAL_DIGEST,
            }
        )
    # Settings is the only allowed mutation, and targets the local mock profile.
    if request.method not in {"GET", "HEAD", "OPTIONS"} and not (
        request.method == "PATCH" and request.url.path == "/api/v1/me"
    ):
        BLOCKED_MUTATIONS.append(f"{request.method} {request.url.path}")
        return JSONResponse(
            {"detail": "Offline replay prohibits this mutation"}, status_code=403
        )
    return await call_next(request)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=args.api_port)
