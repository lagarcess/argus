"""Mem0-backed semantic recall behind the canonical provider protocol.

Composition layer, deliberately. The `argus.memory` package stays deterministic
and network-free, so the vendor client, its environment switches, and the
adapters that neuter it live here instead.

Mem0 ships as a batteries-included memory product. Argus uses exactly one of
those batteries, the vector index, and this module is where the rest are turned
off before the library can act on its defaults:

- extraction, dedup, and conflict resolution are unused, so the LLM seat holds
  a sentinel that raises instead of reaching any vendor;
- vendor telemetry is disabled before import, because the switch is read once
  at module import time;
- the history journal is process-local, so the only durable store is Supabase;
- vectors live in pgvector on the connection pool the memory subsystem already
  owns, so no second datastore and no second credential exist.

Index-only, by construction. The provider projects confirmed records and
answers searches with ranked canonical record ids and nothing else:
`ProviderHit` carries no content, so the service always rehydrates from the
canonical store. The index is derivative and disposable; losing it costs recall
quality and never costs a memory.
"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

from loguru import logger

from argus.llm.memory_embedding import MemoryEmbedder
from argus.memory.contracts import MemoryRecord, ProviderReconciliationStatus
from argus.memory.index_policy import index_eligibility, index_text
from argus.memory.provider import (
    ProviderCleanupResult,
    ProviderHit,
    ProviderProjectionResult,
    ProviderSearchResult,
    ProviderSearchStatus,
)
from argus.memory.subject import RegisteredMemoryOwner

DEFAULT_COLLECTION_NAME = "argus_memory_vectors"

# Mem0's history journal is a derivative audit log Argus never reads. Keeping
# it in process memory means the only durable memory store is Supabase.
EPHEMERAL_HISTORY_DB_PATH = ":memory:"

# Metadata key holding the canonical record id. It is the only join between the
# derivative index and canonical truth.
RECORD_ID_METADATA_KEY = "argus_record_id"

# Mem0 drops results below this similarity. Recall stays generous because the
# canonical store, not the index, decides what the user is allowed to see.
DEFAULT_SEARCH_THRESHOLD = 0.1

_FALSE_VALUES = frozenset(("false", "0", "no", "off"))


class Mem0ExtractionAttempted(AssertionError):
    """Mem0 tried to run an LLM. Argus owns extraction; this is a defect."""


def import_mem0_memory() -> Any:
    """Import Mem0 with vendor telemetry disabled, whatever the import order.

    Two belts. The environment switch is the one that matters when Argus is the
    first importer, because Mem0 reads it once at import time and builds its
    PostHog client immediately. But being first is not something this module can
    prove, so the already-bound flags are forced off afterwards too.
    """

    if os.environ.get("MEM0_TELEMETRY", "").strip().lower() not in _FALSE_VALUES:
        os.environ["MEM0_TELEMETRY"] = "False"
    from mem0 import Memory

    _force_telemetry_off()
    return Memory


def _force_telemetry_off() -> None:
    """Clear every binding of Mem0's telemetry flag, including from-imports.

    `mem0.memory.main` copies the boolean with a from-import, so patching the
    telemetry module alone would leave that copy live. Both names are cleared,
    which also stops the second "mem0migrations" vector collection Mem0 would
    otherwise create in our database purely to report usage.
    """

    import mem0.memory.main as mem0_main
    import mem0.memory.telemetry as mem0_telemetry

    mem0_telemetry.MEM0_TELEMETRY = False
    mem0_main.MEM0_TELEMETRY = False
    singleton = getattr(mem0_telemetry, "_oss_telemetry_instance", None)
    if singleton is not None and hasattr(singleton, "posthog"):
        singleton.posthog = None


def build_mem0_config(
    *,
    embedder: MemoryEmbedder,
    connection_pool: Any,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> dict[str, Any]:
    """The only Mem0 configuration Argus accepts."""

    return {
        "embedder": {
            "provider": "langchain",
            "config": {"model": langchain_embeddings_adapter(embedder)},
        },
        # Filling the LLM seat with a sentinel is the enforcement: any call
        # into Mem0's extraction pipeline raises here instead of reaching a
        # vendor or silently rewriting user-confirmed content.
        "llm": {
            "provider": "langchain",
            "config": {"model": extraction_disabled_chat_model()},
        },
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "connection_pool": connection_pool,
                "collection_name": collection_name,
                "embedding_model_dims": embedder.dimensions,
            },
        },
        "history_db_path": EPHEMERAL_HISTORY_DB_PATH,
    }


def build_mem0_memory(
    *,
    embedder: MemoryEmbedder,
    connection_pool: Any,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> Any:
    """Build the configured in-process Mem0 client."""

    memory_class = import_mem0_memory()
    return memory_class.from_config(
        build_mem0_config(
            embedder=embedder,
            connection_pool=connection_pool,
            collection_name=collection_name,
        )
    )


def extraction_disabled_chat_model() -> Any:
    """A chat model that occupies Mem0's LLM seat and refuses to generate."""

    from langchain.chat_models.base import BaseChatModel

    class _ExtractionDisabledChatModel(BaseChatModel):
        @property
        def _llm_type(self) -> str:
            return "argus-memory-extraction-disabled"

        def _generate(
            self,
            messages: Any,
            stop: Any = None,
            run_manager: Any = None,
            **kwargs: Any,
        ) -> Any:
            raise Mem0ExtractionAttempted(
                "Mem0 extraction is disabled; Argus owns memory extraction "
                "through its own task registry and storage through user "
                "confirmation."
            )

    return _ExtractionDisabledChatModel()


_ADAPTER_CLASS: type | None = None


def _embeddings_adapter_class() -> type:
    """Build the Embeddings-derived adapter class once, on first use."""

    global _ADAPTER_CLASS
    if _ADAPTER_CLASS is None:
        from langchain.embeddings.base import Embeddings

        class _Adapter(Embeddings):  # type: ignore[misc]
            """Presents an Argus embedder through Mem0's expected interface."""

            def __init__(self, embedder: MemoryEmbedder) -> None:
                self._embedder = embedder

            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                return [self._embedder.embed(text) for text in texts]

            def embed_query(self, text: str) -> list[float]:
                return self._embedder.embed(text)

        _ADAPTER_CLASS = _Adapter
    return _ADAPTER_CLASS


def langchain_embeddings_adapter(embedder: MemoryEmbedder) -> Any:
    """Wrap an Argus embedder in the LangChain interface Mem0 accepts."""

    return _embeddings_adapter_class()(embedder)


class Mem0MemoryProvider:
    """Derivative semantic index over confirmed memories only."""

    def __init__(
        self,
        *,
        embedder: MemoryEmbedder,
        connection_pool: Any = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        search_threshold: float = DEFAULT_SEARCH_THRESHOLD,
        memory: Any | None = None,
    ) -> None:
        self._embedder = embedder
        self._search_threshold = search_threshold
        self._memory = (
            memory
            if memory is not None
            else build_mem0_memory(
                embedder=embedder,
                connection_pool=connection_pool,
                collection_name=collection_name,
            )
        )

    def project(
        self,
        owner: RegisteredMemoryOwner,
        record: MemoryRecord,
    ) -> ProviderProjectionResult:
        """Index one confirmed record, or decline without touching Mem0."""

        decision = index_eligibility(owner, record)
        if not decision.allowed:
            # Declining is not a failure: canonical truth already holds the
            # record, and the index simply never learns about it.
            logger.warning(
                "Memory record refused by the index gate",
                refusal=decision.refusal.value if decision.refusal else None,
            )
            return ProviderProjectionResult(
                status=ProviderReconciliationStatus.NOT_APPLICABLE
            )
        result = self._memory.add(
            messages=[{"role": "user", "content": index_text(record)}],
            user_id=owner.owner_id,
            metadata={RECORD_ID_METADATA_KEY: record.id},
            # Argus owns extraction; Mem0 stores exactly the confirmed text.
            infer=False,
        )
        provider_ref = _first_result_id(result)
        if provider_ref is None:
            return ProviderProjectionResult(
                status=ProviderReconciliationStatus.RECONCILIATION_REQUIRED
            )
        return ProviderProjectionResult(
            status=ProviderReconciliationStatus.SYNCHRONIZED,
            provider_ref=provider_ref,
            **self._usage_fields(),
        )

    def search(
        self,
        owner: RegisteredMemoryOwner,
        query: str,
        limit: int,
    ) -> ProviderSearchResult:
        """Answer with ranked canonical record ids; never with content."""

        raw = self._memory.search(
            query,
            top_k=limit,
            filters={"user_id": owner.owner_id},
            threshold=self._search_threshold,
        )
        return ProviderSearchResult(
            status=ProviderSearchStatus.ANSWERED,
            hits=_hits_from(raw, limit=limit),
            **self._usage_fields(),
        )

    def delete(
        self,
        owner: RegisteredMemoryOwner,
        provider_ref: str,
    ) -> ProviderCleanupResult:
        del owner
        self._memory.delete(provider_ref)
        return ProviderCleanupResult(status=ProviderReconciliationStatus.SYNCHRONIZED)

    def reset(self, owner: RegisteredMemoryOwner) -> ProviderCleanupResult:
        self._memory.delete_all(user_id=owner.owner_id)
        return ProviderCleanupResult(status=ProviderReconciliationStatus.SYNCHRONIZED)

    def _usage_fields(self) -> dict[str, Any]:
        usage = self._embedder.last_usage()
        fields: dict[str, Any] = {}
        if isinstance(usage.total_tokens, int) and usage.total_tokens >= 0:
            fields["usage_units"] = usage.total_tokens
        if isinstance(usage.reported_cost_usd, Decimal):
            fields["reported_cost_usd"] = usage.reported_cost_usd
        return fields


def _first_result_id(result: Any) -> str | None:
    entries = result.get("results") if isinstance(result, dict) else None
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        candidate = entry.get("id")
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def _hits_from(raw: Any, *, limit: int) -> tuple[ProviderHit, ...]:
    """Project Mem0 results onto canonical ids, discarding indexed content."""

    entries = raw.get("results") if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        return ()
    hits: list[ProviderHit] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        record_id = _record_id_of(entry)
        score = _score_of(entry)
        if record_id is None or score is None or record_id in seen:
            continue
        seen.add(record_id)
        hits.append(ProviderHit(record_id=record_id, score=score))
        if len(hits) >= limit:
            break
    return tuple(hits)


def _record_id_of(entry: dict[str, Any]) -> str | None:
    metadata = entry.get("metadata")
    if not isinstance(metadata, dict):
        return None
    record_id = metadata.get(RECORD_ID_METADATA_KEY)
    return record_id if isinstance(record_id, str) and record_id else None


def _score_of(entry: dict[str, Any]) -> float | None:
    score = entry.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return None
    numeric = float(score)
    # NaN and infinities would violate the provider hit contract.
    if numeric != numeric or numeric in (float("inf"), float("-inf")):
        return None
    return max(0.0, numeric)
