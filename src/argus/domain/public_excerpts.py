"""Build and audit the frozen payload behind a public evidence receipt.

The pipeline is ``EvidenceArtifact -> PublicExcerptSnapshot -> PublicExcerptView``.
Only this module turns private records into a public payload, and it fails closed:
if the audit in :func:`audit_public_excerpt_payload` finds anything on the
never-expose list the receipt is never created.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import unicodedata
from typing import Any

from argus.api.public_excerpt_schemas import (
    PUBLIC_EXCERPT_OWNER_NOTE_MAX_LENGTH,
    PublicExcerptDateRange,
    PublicExcerptListItem,
    PublicExcerptMetric,
    PublicExcerptPayload,
    PublicExcerptSnapshot,
    PublicExcerptStrategyFact,
    PublicExcerptView,
    PublicExcerptVisual,
    PublicExcerptVisualPoint,
)
from argus.api.schemas import EvidenceArtifact
from argus.domain.credential_shapes import credential_shape_in

PUBLIC_EXCERPT_ID_BYTES = 24
PUBLIC_EXCERPT_PATH_PREFIX = "/r/"
MAX_VISUAL_POINTS = 500
MAX_ASSUMPTIONS = 8
MAX_METRICS = 8
MAX_SYMBOLS = 5
MAX_TEXT_LENGTH = 240

CROSSOVER_WINDOW_KEYS = ("fast_indicator", "fast_period", "slow_indicator", "slow_period")

# Owner-facing. A receipt exists to be a truthful frozen record, so a strategy this
# module cannot describe completely is refused rather than published partially.
_UNDESCRIBABLE_STRATEGY = (
    "Argus cannot describe this strategy on a shared page yet, so this result "
    "cannot be shared."
)

# §3 of the sharing spec, from decision memo §15.7. Absolute.
NEVER_EXPOSE_KEY_MARKERS = (
    "conversation_id",
    "conversation_ids",
    "message_id",
    "run_id",
    "job_id",
    "artifact_id",
    "idea_id",
    "version_id",
    "strategy_id",
    "decision_id",
    "user_id",
    "owner_id",
    "visitor",
    "route_receipt",
    "receipts",
    "provider",
    "model",
    "retry",
    "transcript",
    "broker",
    "account",
    "memory",
    "token",
    "latency",
    "cost_usd",
)

NEVER_EXPOSE_VALUE_MARKERS = (
    "openrouter",
    "alpaca",
    "perplexity",
    "supabase",
    "langgraph",
    "route_receipt",
    "system_prompt",
    "bearer ",
    "sk-",
)

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_SECRET_SHAPED_RE = re.compile(r"[A-Za-z0-9_\-]{24,}")
_WHITESPACE_RE = re.compile(r"\s+")
_CONTROL_CHARS = {"Cc", "Cf", "Cs", "Co", "Cn"}


class PublicExcerptSanitizationError(ValueError):
    """The payload could not be proven safe to publish, so nothing is published."""


class PublicExcerptOwnerNoteError(ValueError):
    """The owner note is not publishable as written."""


class PublicExcerptSourceError(ValueError):
    """The artifact cannot back a receipt."""


def new_public_excerpt_id() -> str:
    """An unguessable url token. 24 bytes of urlsafe entropy, no owner signal."""
    return secrets.token_urlsafe(PUBLIC_EXCERPT_ID_BYTES)


def public_excerpt_path(public_id: str) -> str:
    return f"{PUBLIC_EXCERPT_PATH_PREFIX}{public_id}"


def payload_digest(payload: PublicExcerptPayload) -> str:
    """Stable digest of the frozen payload. Any drift changes this string."""
    canonical = json.dumps(
        payload.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_owner_note(note: object) -> str | None:
    """Bound and clean the one free-text field a receipt carries.

    Every other field in the payload is structured, so this is the only channel
    through which a secret can reach a public Argus page. Refused rather than
    redacted: a receipt is frozen at creation, so a redaction marker would be
    permanent, and the owner is still here and can take the key out.
    """
    if note is None:
        return None
    if not isinstance(note, str):
        raise PublicExcerptOwnerNoteError("The note must be text.")
    # Control characters become spaces rather than vanishing, so removing a
    # newline cannot silently join two words into one.
    cleaned = "".join(
        " " if unicodedata.category(character) in _CONTROL_CHARS else character
        for character in note
    )
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    if not cleaned:
        return None
    if len(cleaned) > PUBLIC_EXCERPT_OWNER_NOTE_MAX_LENGTH:
        raise PublicExcerptOwnerNoteError("The note is too long to publish.")
    # Grammar first, length second. A credential is recognisable from its own
    # structure at any length, and the length guard exists only for opaque blobs
    # no issuer prefix names.
    if (
        _UUID_RE.search(cleaned)
        or credential_shape_in(cleaned)
        or _SECRET_SHAPED_RE.search(cleaned)
    ):
        raise PublicExcerptOwnerNoteError(
            "The note looks like it contains a key or a long code."
        )
    return cleaned


def build_public_excerpt_payload(
    *,
    artifact: EvidenceArtifact,
    run_chart: dict[str, Any] | None,
    run_config_snapshot: dict[str, Any] | None = None,
    owner_note: str | None,
    content_language: str,
) -> PublicExcerptPayload:
    """Assemble the closed payload from frozen records, then audit it."""
    if artifact.artifact_type != "backtest":
        raise PublicExcerptSourceError("Only completed backtest results are shareable.")
    source = artifact.payload if isinstance(artifact.payload, dict) else {}
    result_card = _mapping(source.get("result_card"))
    provenance = _mapping(source.get("provenance"))
    date_range = _date_range(result_card.get("date_range"))
    if date_range is None:
        raise PublicExcerptSourceError("The result has no tested date range.")
    payload = PublicExcerptPayload(
        idea_title=_text(artifact.title) or _text(result_card.get("title")) or "Backtest",
        asset_class=_asset_class(
            provenance.get("asset_class") or result_card.get("asset_class")
        ),
        symbols=_symbols(provenance.get("symbols") or result_card.get("symbols")),
        strategy_label=_text(result_card.get("strategy_label")),
        strategy_facts=_strategy_facts(run_config_snapshot),
        assumptions=_text_list(
            source.get("assumptions") or result_card.get("assumptions"),
            limit=MAX_ASSUMPTIONS,
        ),
        date_range=date_range,
        metrics=_metrics(result_card.get("rows")),
        benchmark_symbol=_text(provenance.get("benchmark_symbol")),
        benchmark_note=_text(result_card.get("benchmark_note")),
        visual=_visual(run_chart),
        owner_note=owner_note,
        content_language="es-419" if content_language == "es-419" else "en",
    )
    audit_public_excerpt_payload(
        payload,
        private_ids=_private_ids(artifact),
        skip_value_markers_for=("owner_note",),
    )
    return payload


def audit_public_excerpt_payload(
    payload: PublicExcerptPayload,
    *,
    private_ids: tuple[str, ...] = (),
    skip_value_markers_for: tuple[str, ...] = (),
) -> None:
    """Adversarial gate over the serialized payload.

    Checks the shape (no key outside the closed set), the keys (nothing named
    after a private record) and the values (no identifier, no provider or model
    metadata, no known private id).
    """
    serialized = payload.model_dump(mode="json")
    expected_keys = set(PublicExcerptPayload.model_fields)
    if set(serialized) != expected_keys:
        unexpected = sorted(set(serialized) - expected_keys)
        missing = sorted(expected_keys - set(serialized))
        raise PublicExcerptSanitizationError(
            f"Receipt payload shape drifted. Unexpected: {unexpected}. "
            f"Missing: {missing}."
        )
    audit_public_excerpt_document(
        serialized,
        private_ids=private_ids,
        skip_value_markers_for=skip_value_markers_for,
    )


def audit_public_excerpt_document(
    document: dict[str, Any],
    *,
    private_ids: tuple[str, ...] = (),
    skip_value_markers_for: tuple[str, ...] = (),
) -> None:
    """Audit an arbitrary would-be public document, keys and values alike.

    Separate from the typed gate so the never-expose rules can be attacked with
    shapes the schema would refuse to build, which is how a leak would actually
    arrive: through a field someone added later.
    """
    lowered_private_ids = tuple(
        value.lower() for value in private_ids if isinstance(value, str) and value
    )
    _audit_node(
        document,
        path=(),
        private_ids=lowered_private_ids,
        skip_value_markers_for=skip_value_markers_for,
    )


def snapshot_list_item(snapshot: PublicExcerptSnapshot) -> PublicExcerptListItem:
    """Owner-facing row. Carries no source id, only what the owner needs to act."""
    return PublicExcerptListItem(
        id=snapshot.id,
        public_id=snapshot.public_id,
        path=public_excerpt_path(snapshot.public_id),
        title=snapshot.payload.idea_title,
        symbols=list(snapshot.payload.symbols),
        date_range_display=snapshot.payload.date_range.display,
        created_at=snapshot.created_at,
        revoked_at=snapshot.revoked_at,
        revocation_reason=snapshot.revocation_reason,
    )


def snapshot_public_view(snapshot: PublicExcerptSnapshot) -> PublicExcerptView:
    """Projection for an unauthenticated viewer. Revoked receipts keep nothing."""
    if snapshot.revoked_at is not None:
        return PublicExcerptView(public_id=snapshot.public_id, status="revoked")
    return PublicExcerptView(
        public_id=snapshot.public_id,
        status="available",
        created_at=snapshot.created_at,
        payload=snapshot.payload,
    )


def revoked_public_view(public_id: str) -> PublicExcerptView:
    """The tombstone. Unknown and revoked ids are indistinguishable to a viewer."""
    return PublicExcerptView(public_id=public_id, status="revoked")


def _audit_node(
    node: Any,
    *,
    path: tuple[str, ...],
    private_ids: tuple[str, ...],
    skip_value_markers_for: tuple[str, ...],
) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            _audit_key(str(key), path=path)
            _audit_node(
                value,
                path=(*path, str(key)),
                private_ids=private_ids,
                skip_value_markers_for=skip_value_markers_for,
            )
        return
    if isinstance(node, list):
        for value in node:
            _audit_node(
                value,
                path=path,
                private_ids=private_ids,
                skip_value_markers_for=skip_value_markers_for,
            )
        return
    if isinstance(node, str):
        _audit_value(
            node,
            path=path,
            private_ids=private_ids,
            skip_value_markers_for=skip_value_markers_for,
        )


def _audit_key(key: str, *, path: tuple[str, ...]) -> None:
    lowered = key.lower()
    for marker in NEVER_EXPOSE_KEY_MARKERS:
        if marker in lowered:
            location = ".".join((*path, key)) or key
            raise PublicExcerptSanitizationError(
                f"Receipt payload field '{location}' names never-expose data."
            )


def _audit_value(
    value: str,
    *,
    path: tuple[str, ...],
    private_ids: tuple[str, ...],
    skip_value_markers_for: tuple[str, ...],
) -> None:
    location = ".".join(path) or "payload"
    if _UUID_RE.search(value):
        raise PublicExcerptSanitizationError(
            f"Receipt payload field '{location}' carries a record identifier."
        )
    # The note is validated when the owner writes it; this is the guard for every
    # other field, including one a later change adds.
    credential_kind = credential_shape_in(value)
    if credential_kind is not None:
        raise PublicExcerptSanitizationError(
            f"Receipt payload field '{location}' carries a {credential_kind}."
        )
    lowered = value.lower()
    for private_id in private_ids:
        if private_id and private_id in lowered:
            raise PublicExcerptSanitizationError(
                f"Receipt payload field '{location}' carries a private id."
            )
    if path and path[-1] in skip_value_markers_for:
        return
    for marker in NEVER_EXPOSE_VALUE_MARKERS:
        if marker in lowered:
            raise PublicExcerptSanitizationError(
                f"Receipt payload field '{location}' carries provider metadata."
            )


def _private_ids(artifact: EvidenceArtifact) -> tuple[str, ...]:
    source = artifact.payload if isinstance(artifact.payload, dict) else {}
    nested = _mapping(source.get("source"))
    candidates = (
        artifact.id,
        artifact.idea_id,
        artifact.idea_version_id,
        artifact.source_conversation_id,
        artifact.source_run_id,
        nested.get("run_id"),
        nested.get("conversation_id"),
        nested.get("strategy_id"),
    )
    return tuple(value for value in candidates if isinstance(value, str) and value)


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = _WHITESPACE_RE.sub(" ", value).strip()
    if not normalized:
        return None
    return normalized[:MAX_TEXT_LENGTH]


def _text_list(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for entry in value:
        normalized = _text(entry)
        if normalized is not None:
            items.append(normalized)
        if len(items) >= limit:
            break
    return items


def _symbols(value: object) -> list[str]:
    return [symbol.upper() for symbol in _text_list(value, limit=MAX_SYMBOLS)]


def _asset_class(value: object) -> str | None:
    return value if value in {"equity", "crypto", "currency_pair"} else None


def _date_range(value: object) -> PublicExcerptDateRange | None:
    mapping = _mapping(value)
    start = _text(mapping.get("start"))
    end = _text(mapping.get("end"))
    display = _text(mapping.get("display")) or (
        f"{start} to {end}" if start and end else None
    )
    if start is None or end is None or display is None:
        return None
    return PublicExcerptDateRange(start=start, end=end, display=display)


def _metrics(value: object) -> list[PublicExcerptMetric]:
    if not isinstance(value, list):
        return []
    metrics: list[PublicExcerptMetric] = []
    for entry in value:
        row = _mapping(entry)
        key = _text(row.get("key"))
        label = _text(row.get("label"))
        display = _text(row.get("value"))
        if key is None or label is None or display is None:
            continue
        metrics.append(PublicExcerptMetric(key=key, label=label, value=display))
        if len(metrics) >= MAX_METRICS:
            break
    return metrics


def _strategy_facts(config_snapshot: object) -> list[PublicExcerptStrategyFact]:
    """Freeze the parameters that define what was executed.

    The strategy label is a category name. For every shape except buy and hold it
    does not identify what produced the numbers: two RSI runs with different periods
    and thresholds, or two crossovers with different windows, would otherwise render
    as the same strategy with different results, which is the opposite of evidence.

    Dispatched on shape, not assembled from whichever fields happen to be present.
    Each shape below declares the complete set of parameters that decide its trades,
    and a shape whose set is not fully present projects nothing at all. Partial
    parameters are worse than none here: a viewer cannot tell that a receipt naming
    one window of a crossover is missing the other, so it would read as a truthful
    record of a strategy that never ran.
    """
    snapshot = _mapping(config_snapshot)
    resolved_strategy = _mapping(snapshot.get("resolved_strategy"))
    resolved_parameters = _mapping(snapshot.get("resolved_parameters"))
    # Two config_snapshot shapes reach here. The agent path nests the strategy under
    # resolved_strategy/resolved_parameters; the direct engine path stores the engine
    # config itself, whose parameters live under `parameters`. Reading only the first
    # left every run made through the second with no parameters at all.
    engine_parameters = _mapping(snapshot.get("parameters"))
    entry_rule = _mapping(resolved_strategy.get("entry_rule"))
    exit_rule = _mapping(resolved_strategy.get("exit_rule"))
    parameters = {**engine_parameters, **resolved_parameters}

    label, required, optional = _strategy_shape(
        snapshot=snapshot,
        resolved_strategy=resolved_strategy,
        entry_rule=entry_rule,
        exit_rule=exit_rule,
        parameters=parameters,
    )

    facts: list[PublicExcerptStrategyFact] = [
        PublicExcerptStrategyFact(key="strategy_type", value=label)
    ]
    for key in required:
        value = _strategy_fact_value(
            _strategy_source_value(
                key,
                parameters=parameters,
                resolved_strategy=resolved_strategy,
                entry_rule=entry_rule,
                exit_rule=exit_rule,
            )
        )
        if value is None:
            raise PublicExcerptSourceError(_UNDESCRIBABLE_STRATEGY)
        facts.append(PublicExcerptStrategyFact(key=key, value=value))
    for key in optional:
        value = _strategy_fact_value(
            _strategy_source_value(
                key,
                parameters=parameters,
                resolved_strategy=resolved_strategy,
                entry_rule=entry_rule,
                exit_rule=exit_rule,
            )
        )
        if value is not None:
            facts.append(PublicExcerptStrategyFact(key=key, value=value))
    return facts


def _strategy_shape(
    *,
    snapshot: dict[str, Any],
    resolved_strategy: dict[str, Any],
    entry_rule: dict[str, Any],
    exit_rule: dict[str, Any],
    parameters: dict[str, Any],
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Resolve the executed shape: its truthful name, then the set that defines it.

    Keyed on the typed rule before the execution type, because the rule is what the
    engine compiles and the execution type does not name a shape on its own:
    ``signal_strategy`` covers both a moving average crossover and an arbitrary rule
    spec, and naming a crossover "signal strategy" would be true of the runtime and
    useless to a reader.

    Raises rather than returning nothing for a shape it cannot describe. A caller that
    had to interpret an empty result published a page describing a strategy this
    module had declined to describe.
    """
    template = (_text(snapshot.get("template")) or "").lower()
    strategy_type = (_text(resolved_strategy.get("strategy_type")) or "").lower()
    rule_type = (_text(entry_rule.get("type")) or "").lower()
    identity = {template, strategy_type}

    if rule_type == "moving_average_crossover":
        return (
            "moving average crossover",
            _crossover_required_keys(entry_rule=entry_rule, exit_rule=exit_rule),
            # The entry side's direction. A crossover's exit direction is its opposite
            # by construction, so it is not a second fact.
            ("direction",),
        )
    if rule_type == "macd_crossover":
        return (
            "macd crossover",
            ("fast_period", "slow_period", "signal_period"),
            ("direction",),
        )
    if "dca_accumulation" in identity:
        return ("dca accumulation", ("cadence",), ())
    if "buy_and_hold" in identity:
        return ("buy and hold", (), ())
    if "buy_the_dip" in identity:
        # fixed_parameters in the capability registry: the trigger is hardcoded in
        # the engine, so there is nothing frozen to disclose, and nothing to borrow
        # from the indicator shape it shares an execution type with either.
        return ("buy the dip", (), ())
    if identity & {"indicator_threshold", "rsi_mean_reversion"}:
        name = (
            "rsi threshold"
            if template == "rsi_mean_reversion"
            else "indicator threshold"
        )
        return (
            name,
            ("indicator", "indicator_period", "entry_threshold", "exit_threshold"),
            ("direction",),
        )
    # A generic rule spec is a condition tree, and an unrecognised shape is unknown by
    # definition. Neither can be flattened into key and value pairs without inventing
    # something, so neither is shareable.
    raise PublicExcerptSourceError(_UNDESCRIBABLE_STRATEGY)


def _crossover_required_keys(
    *,
    entry_rule: dict[str, Any],
    exit_rule: dict[str, Any],
) -> tuple[str, ...]:
    """The crossover facts a receipt owes, entry side plus exit side when they differ.

    The rule compiler builds entry and exit independently and never requires them to
    match, so reading the windows from the entry rule alone can state an exit that did
    not run. When the exit rule is absent the engine derives it by flipping the entry
    direction, so the windows are the entry's and there is nothing extra to say.
    """
    if not exit_rule:
        return CROSSOVER_WINDOW_KEYS
    if (_text(exit_rule.get("type")) or "").lower() != "moving_average_crossover":
        # A crossover entry paired with some other kind of exit is a shape this module
        # has no faithful projection for.
        raise PublicExcerptSourceError(_UNDESCRIBABLE_STRATEGY)
    differs = any(
        _strategy_fact_value(exit_rule.get(key))
        != _strategy_fact_value(entry_rule.get(key))
        for key in CROSSOVER_WINDOW_KEYS
    )
    if not differs:
        return CROSSOVER_WINDOW_KEYS
    return (*CROSSOVER_WINDOW_KEYS, *(f"exit_{key}" for key in CROSSOVER_WINDOW_KEYS))


def _strategy_source_value(
    key: str,
    *,
    parameters: dict[str, Any],
    resolved_strategy: dict[str, Any],
    entry_rule: dict[str, Any],
    exit_rule: dict[str, Any],
) -> object:
    """Where each fact is frozen from, most specific source first."""
    candidates: tuple[object, ...]
    if key == "cadence":
        candidates = (
            parameters.get("dca_cadence"),
            resolved_strategy.get("cadence"),
            parameters.get("cadence"),
        )
    elif key == "indicator":
        candidates = (
            parameters.get("indicator"),
            entry_rule.get("indicator"),
            exit_rule.get("indicator"),
        )
    elif key == "indicator_period":
        candidates = (
            parameters.get("indicator_period"),
            entry_rule.get("period"),
            entry_rule.get("indicator_period"),
            exit_rule.get("period"),
        )
    elif key == "entry_threshold":
        candidates = (
            parameters.get("entry_threshold"),
            parameters.get("indicator_entry_threshold"),
            entry_rule.get("threshold"),
        )
    elif key == "exit_threshold":
        candidates = (
            parameters.get("exit_threshold"),
            parameters.get("indicator_exit_threshold"),
            exit_rule.get("threshold"),
        )
    elif key == "direction":
        candidates = (
            entry_rule.get("direction"),
            resolved_strategy.get("direction"),
        )
    elif key.startswith("exit_") and key[len("exit_") :] in CROSSOVER_WINDOW_KEYS:
        # Only the exit rule may speak for the exit side.
        candidates = (exit_rule.get(key[len("exit_") :]),)
    else:
        # fast_indicator, fast_period, slow_indicator, slow_period, signal_period:
        # the typed rule is the only place these are frozen.
        candidates = (entry_rule.get(key), parameters.get(key))
    for candidate in candidates:
        if candidate not in (None, ""):
            return candidate
    return None


def _strategy_fact_value(value: object) -> str | None:
    """Plain scalars only. A nested structure is not a fact a viewer can read."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        # Whole numbers read as periods and thresholds, not as decimals.
        return str(int(value)) if value.is_integer() else f"{value:g}"
    if isinstance(value, str):
        normalized = _text(value)
        if normalized is None:
            return None
        return normalized[:48].replace("_", " ")
    return None


def _visual(chart: object) -> PublicExcerptVisual | None:
    mapping = _mapping(chart)
    if mapping.get("kind") != "portfolio_equity":
        return None
    series = _visual_series(mapping.get("series"))
    if len(series) < 2:
        return None
    base_value = mapping.get("base_value")
    return PublicExcerptVisual(
        kind="portfolio_equity",
        currency=_text(mapping.get("currency")),
        base_value=float(base_value) if isinstance(base_value, int | float) else None,
        series=series,
    )


def _visual_series(value: object) -> list[PublicExcerptVisualPoint]:
    if not isinstance(value, list):
        return []
    points: list[PublicExcerptVisualPoint] = []
    for entry in value:
        row = _mapping(entry)
        time = _text(row.get("time"))
        observed = row.get("value")
        if time is None or not isinstance(observed, int | float):
            continue
        points.append(PublicExcerptVisualPoint(time=time, value=float(observed)))
    return _downsample(points)


def _downsample(
    points: list[PublicExcerptVisualPoint],
) -> list[PublicExcerptVisualPoint]:
    """Keep the payload small on a phone without moving the endpoints."""
    if len(points) <= MAX_VISUAL_POINTS:
        return points
    stride = len(points) / (MAX_VISUAL_POINTS - 1)
    sampled = [points[int(index * stride)] for index in range(MAX_VISUAL_POINTS - 1)]
    sampled.append(points[-1])
    return sampled
