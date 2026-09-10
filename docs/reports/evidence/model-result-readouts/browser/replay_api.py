"""Provider-free readout transport replay. No fixture here is new model evidence.

The older META Quick take/result card comes from committed issue 411 evidence.
All Breakdown rows and all v1 readout envelopes are synthetic browser fixtures.
Run from the repository root with .venv/bin/python path/to/this/file.py.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

ROOT = Path.cwd()
WEB_PORT = int(os.getenv("READOUT_REPLAY_WEB_PORT", "3219"))
API_PORT = int(os.getenv("READOUT_REPLAY_API_PORT", "8539"))

# This is deliberately before ANY Argus import. No inherited credential or
# linked dotenv value may participate in a browser transport replay.
for key in tuple(os.environ):
    if any(part in key.upper() for part in ("KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL", "DATABASE", "SUPABASE", "POSTHOG", "ALPACA", "OPENROUTER")):
        os.environ[key] = ""
os.environ.update({
    "PYTHON_DOTENV_DISABLED": "1",
    "ARGUS_PERSISTENCE_MODE": "memory",
    "ARGUS_DEV_MEMORY_FALLBACK": "true",
    "ARGUS_CHECKPOINTER_MODE": "memory",
    "ARGUS_MOCK_AUTH": "true",
    "ARGUS_CORS_ALLOW_ORIGINS": f"http://127.0.0.1:{WEB_PORT},http://localhost:{WEB_PORT}",
    "ARGUS_APP_ORIGIN": f"http://127.0.0.1:{WEB_PORT}",
    "ARGUS_BACKTEST_JOBS_SHADOW_ENABLED": "false",
    "ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED": "false",
    "ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED": "false",
    "DATABASE_URL": "",
    "SUPABASE_URL": "",
    "SUPABASE_SERVICE_ROLE_KEY": "",
    "SUPABASE_ANON_KEY": "",
    "OPENROUTER_API_KEY": "",
    "ARGUS_PROD_OPENROUTER_API_KEY": "",
    "ARGUS_GUEST_ACCESS_OPENROUTER_API_KEY": "",
})
import dotenv  # noqa: E402

dotenv.load_dotenv = lambda *args, **kwargs: False

BLOCKED_NETWORK: list[str] = []
BLOCKED_GENERATION: list[str] = []
_connect = socket.socket.connect
_getaddrinfo = socket.getaddrinfo


def _local(host: Any) -> bool:
    return str(host) in {"127.0.0.1", "::1", "localhost", "None"}


def _guard_connect(sock: socket.socket, address: Any) -> Any:
    if isinstance(address, tuple) and not _local(address[0]):
        BLOCKED_NETWORK.append("non_loopback_connect")
        raise RuntimeError("Replay forbids non-loopback network connections")
    return _connect(sock, address)


def _guard_dns(host: Any, *args: Any, **kwargs: Any) -> Any:
    if not _local(host):
        BLOCKED_NETWORK.append("non_loopback_dns")
        raise RuntimeError("Replay forbids non-loopback DNS resolution")
    return _getaddrinfo(host, *args, **kwargs)


socket.socket.connect = _guard_connect
socket.getaddrinfo = _guard_dns
sys.path.insert(0, str(ROOT / "src"))
from argus.api import state as api_state  # noqa: E402
from argus.api.main import app  # noqa: E402
from argus.api.schemas import Conversation, Message  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402

SOURCE = ROOT / "docs/reports/evidence/411/browser/en-discovery-messages.json"
RESULT_ID = "b215f293-81d5-427c-ae11-e0cab659f63e"
CASES = {
    "legacy": "00000000-0000-4000-8000-000000005391",
    "new-en": "00000000-0000-4000-8000-000000005392",
    "new-es": "00000000-0000-4000-8000-000000005393",
}
TEXT = {
    "en": {
        "quick_take": "META's gain comfortably exceeded SPY's, but holding it meant accepting a rough ride. The 18.35% worst drop is a reminder that a strong finish did not make this a smooth experience.",
        "breakdown": "The annualized return was 117.25%, while volatility was 38.17%. Those figures describe a large gain with substantial swings along the way.\n\nFor scale, an 18.35% fall applied to the $10,000 starting capital is about $1,835. This is an illustration of the drop's size, not the actual loss from the portfolio's later peak. The recorded Sharpe ratio was 2.22, and the run recorded one trade.",
    },
    "es-419": {
        "quick_take": "La ganancia de META superó ampliamente a SPY, aunque mantener la inversión exigió soportar un recorrido agitado. La peor caída de 18.35% recuerda que un buen resultado final no implica una experiencia tranquila.",
        "breakdown": "El rendimiento anualizado fue de 117.25% y la volatilidad fue de 38.17%. Estas cifras describen una ganancia grande acompañada de oscilaciones importantes.\n\nPara ponerlo en escala, una caída de 18.35% aplicada al capital inicial de $10,000 equivale a unos $1,835. Es una ilustración del tamaño de la caída, no la pérdida real desde un máximo posterior de la cartera. El índice de Sharpe registrado fue de 2.22 y la simulación registró una operación.",
    },
}


def _envelope(language: str, surface: str) -> dict[str, Any]:
    return {"schema_version": "result_readout/v1", "surface": surface, "language": language, "text": TEXT[language][surface]}


def _seed() -> None:
    source = json.loads(SOURCE.read_text())
    result = next(row for row in source["items"] if row["id"] == RESULT_ID)
    user = api_state.store.get_or_create_dev_user()
    for case, conversation_id in CASES.items():
        # Retain the genuine persisted old result content/card/metrics. IDs are
        # local aliases; no original conversation is queried or rewritten.
        raw = json.dumps(result).replace(result["conversation_id"], conversation_id)
        row = json.loads(raw)
        language = "es-419" if case == "new-es" else "en"
        metadata = row["metadata"]
        if case != "legacy":
            envelope = _envelope(language, "quick_take")
            metadata["result_readout_content"] = envelope
            metadata["result_card"]["result_readout_content"] = copy.deepcopy(envelope)
            metadata.update(result_readout_source="llm_explain_stage", result_readout_fallback_used=False)
        breakdown_metadata = {
            "chat_action": {"type": "show_breakdown", "label": "Explain result", "payload": {"run_id": metadata["result_run_id"]}},
            "response_intent": {"kind": "result_breakdown", "facts": {"result_fact_bank": copy.deepcopy(metadata["result_fact_bank"])}},
        }
        if case != "legacy":
            breakdown_metadata.update(result_readout_content=_envelope(language, "breakdown"), result_readout_source="llm_breakdown_stage", result_readout_fallback_used=False)
        breakdown = {
            "id": conversation_id[:-1] + "7",
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": "SYNTHETIC PRIVATE BREAKDOWN PROSE MUST NEVER APPEAR",
            "created_at": "2026-09-03T02:07:00Z",
            "metadata": breakdown_metadata,
        }
        messages = [Message.model_validate(row), Message.model_validate(breakdown)]
        api_state.store.conversation_owners[conversation_id] = user.id
        api_state.store.messages[conversation_id] = messages
        api_state.store.conversations[conversation_id] = Conversation(
            id=conversation_id,
            title=f"Readout replay: {case} (fixture)",
            title_source="user_renamed",
            language=language,
            created_at=messages[0].created_at,
            updated_at=messages[-1].created_at,
            last_message_preview="Provider-free transport fixture",
        )


_seed()


def _stored_message_digest() -> str:
    rows = {
        key: [message.model_dump(mode="json") for message in messages]
        for key, messages in api_state.store.messages.items()
    }
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


INITIAL_MESSAGE_DIGEST = _stored_message_digest()
LOADED_READER_HASHES = {
    name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    for name in (
        "src/argus/api/artifact_presentation.py",
        "src/argus/domain/result_readout_content.py",
    )
}


@app.middleware("http")
async def prohibit_generation(request: Any, call_next: Any) -> Any:
    if request.url.path == "/replay-proof":
        return JSONResponse({"blocked_network": BLOCKED_NETWORK, "blocked_generation_requests": BLOCKED_GENERATION, "generation_requests_allowed": 0, "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(), "cases": CASES, "texts": TEXT, "synthetic_envelopes_and_breakdowns": True, "stored_messages_unchanged": _stored_message_digest() == INITIAL_MESSAGE_DIGEST, "initial_message_digest": INITIAL_MESSAGE_DIGEST, "loaded_reader_source_hashes": LOADED_READER_HASHES})
    if request.method == "POST" and ("chat" in request.url.path or "backtest" in request.url.path):
        BLOCKED_GENERATION.append(request.url.path)
        return JSONResponse({"detail": "Provider-free replay prohibits generation"}, status_code=403)
    return await call_next(request)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=API_PORT)
