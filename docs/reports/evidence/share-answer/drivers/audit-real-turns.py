"""Attack copies of the two saved real rail turns; no new retrieval or writes."""

import json
import runpy
import subprocess
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[5]
PRIVATE = ROOT / "temp/share-answer-qa"
runpy.run_path(str(Path(__file__).with_name("start-api.py")))

from argus.api import state  # noqa: E402
from argus.api.public_excerpt_schemas import PublicExcerptTurnsPayload  # noqa: E402
from argus.api.public_excerpt_selection import (  # noqa: E402
    _context,
    _job,
    _project,
    _question,
)
from argus.api.schemas import User  # noqa: E402
from argus.domain.job_settlement import RESEARCH_OPERATION_SCOPE  # noqa: E402
from argus.domain.public_excerpts import (  # noqa: E402
    NEVER_EXPOSE_KEY_MARKERS,
    PublicExcerptSourceError,
    audit_public_excerpt_document,
    payload_digest,
)
from argus.domain.research.contracts import (  # noqa: E402
    ResearchUsage,
    combined_research_usage,
)
from argus.domain.supabase_gateway import SupabaseGateway  # noqa: E402

state.supabase_gateway = SupabaseGateway.from_env()
results = []
for case in ("en-focused", "es-419"):
    saved = json.loads((PRIVATE / f"research-{case}.json").read_text())
    context = _context(User.model_validate(saved["me"]["user"]), saved["conversation_id"])
    baseline = next(m for m in context.messages if m.id == saved["message_id"])
    leaf, _, _ = _project(context, baseline, None)
    serialized = leaf.model_dump(mode="json")
    audit_public_excerpt_document(serialized)
    assert serialized["answer"] == baseline.content
    assert serialized["sources"] == baseline.metadata["research"]["sources"]
    checks = []
    cases = (
        ("no_typed_sources", "missing_sources", "sources"),
        ("unlisted_url", "unlisted_url", "answer"),
        ("memory", "memory_used", None),
        ("degraded", "degraded", None),
        ("fast", "unsupported_shape", None),
        ("find", "unsupported_shape", None),
        ("question", "unsafe_text", "question"),
        ("answer", "unsafe_text", "answer"),
        ("owner_note", "unsafe_text", "owner_note"),
    )
    for name, reason, field in cases:
        trial = deepcopy(context)
        message = next(m for m in trial.messages if m.id == baseline.id)
        question = _question(trial, message, _job(trial, message))
        note = None
        if name == "no_typed_sources":
            message.metadata["research"]["sources"] = []
            message.content += " https://example.org/one https://example.org/two https://example.org/three"
        elif name == "unlisted_url":
            message.content += " https://example.org/absent"
        elif name == "memory":
            message.metadata["memory_recalls"] = [{"id": str(uuid4())}]
        elif name == "degraded":
            message.metadata["research"]["degraded"] = {
                "code": "research_unavailable_timeout"
            }
        elif name in {"fast", "find"}:
            message.metadata["research"]["shape"] = name
        elif name == "question":
            question.content += f" {uuid4()}"
        elif name == "answer":
            message.content += f" {uuid4()}"
        else:
            note = f"{uuid4()}"
        try:
            _project(trial, message, note)
        except PublicExcerptSourceError as error:
            assert (error.reason, error.field) == (reason, field), name
            checks.append({"case": name, "reason": error.reason, "field": error.field})
        else:
            raise AssertionError(f"Accepted adversarial {name}")
    # Extra private runtime metadata cannot extend the closed public shape.
    trial = deepcopy(context)
    message = next(m for m in trial.messages if m.id == baseline.id)
    for marker in NEVER_EXPOSE_KEY_MARKERS:
        message.metadata[f"qa_{marker}"] = str(uuid4())
    projected, _, _ = _project(trial, message, None)
    assert projected.model_dump(mode="json") == serialized
    # Integration changes private spend accounting, not public answer content.
    digest = payload_digest(PublicExcerptTurnsPayload(turns=[leaf]))
    usage_checks = []
    invoice = ResearchUsage(
        invocations=1, model="private-model", latency_ms=100, cost_usd=0.01
    )
    usages = {
        "summed": combined_research_usage([invoice, invoice]),
        "unknown": combined_research_usage(
            [invoice, ResearchUsage(invocations=None, cost_usd=None)]
        ),
        "cache_hit": ResearchUsage(),
    }
    for name, usage in usages.items():
        trial = deepcopy(context)
        message = next(m for m in trial.messages if m.id == baseline.id)
        message.metadata["research"]["usage"] = usage.model_dump(mode="json")
        message.metadata["research"]["provider"] = "private-provider"
        message.metadata["research"]["cache_hit"] = name == "cache_hit"
        projected, _, _ = _project(trial, message, None)
        assert projected.model_dump(mode="json") == serialized
        assert payload_digest(PublicExcerptTurnsPayload(turns=[projected])) == digest
        usage_checks.append({"case": name, "payload_and_digest_unchanged": True})
    failure_checks = []
    for reason in ("missing_public_sources", "empty_answer", "malformed_response"):
        trial = deepcopy(context)
        message = next(m for m in trial.messages if m.id == baseline.id)
        code = f"research_unavailable_{reason}"
        message.metadata["research"]["degraded"] = {"code": code}
        # Retaining valid publisher sources cannot make a degraded turn eligible.
        try:
            _project(trial, message, None)
        except PublicExcerptSourceError as error:
            assert error.reason == "degraded", code
            failure_checks.append({"case": code, "reason": error.reason})
        else:
            raise AssertionError(f"Accepted degraded {code}")
    trial = deepcopy(context)
    message = next(m for m in trial.messages if m.id == baseline.id)
    question = _question(trial, message, _job(trial, message))
    message.metadata = {"conversation_mode": "guide"}
    message.content = "Research unavailable."
    trial.jobs.append(
        {
            "id": str(uuid4()),
            "user_id": trial.user.id,
            "conversation_id": trial.conversation.id,
            "operation_scope": RESEARCH_OPERATION_SCOPE,
            "status": "failed",
            "request_message_id": question.id,
            "execution_metadata": {"research_result_message_id": message.id},
        }
    )
    try:
        _project(trial, message, None)
    except PublicExcerptSourceError as error:
        assert error.reason == "not_completed"
        failure_checks.append({"case": "billed_thorough_failure", "reason": error.reason})
    else:
        raise AssertionError("Accepted failed background research")
    results.append(
        {
            "language": saved["language"],
            "source": "Saved real rail turn, in-memory adversarial copies",
            "source_sha": saved["candidate_sha"],
            "sources": len(serialized["sources"]),
            "answer_preserved": True,
            "sources_preserved": True,
            "private_metadata_does_not_expand_payload": True,
            "refusals": checks,
            "integration_usage_checks": usage_checks,
            "integration_failure_checks": failure_checks,
        }
    )
output = {
    "candidate_sha": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip(),
    "new_provider_calls": 0,
    "writes": 0,
    "results": results,
}
(ROOT / "docs/reports/evidence/share-answer/real-turn-adversarial.json").write_text(
    json.dumps(output, indent=2)
)
print(
    json.dumps(
        {
            "languages": len(results),
            "refusals": sum(len(r["refusals"]) for r in results),
            "integration_usage_checks": sum(
                len(r["integration_usage_checks"]) for r in results
            ),
            "integration_failure_checks": sum(
                len(r["integration_failure_checks"]) for r in results
            ),
            "writes": 0,
            "new_provider_calls": 0,
        }
    )
)
