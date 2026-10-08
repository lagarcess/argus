"""Per-post spend guard for the live measurement eval.

Every billable OpenRouter post is reserved at the most it can cost before it
leaves the process, from the actual outgoing request: its UTF-8 body bytes for
the input, its `max_tokens` for the output, at the pinned ceiling price of the
exact model it targets. The reservation is taken under one lock, so concurrent
posts in threads or async tasks can never together reserve past the budget. A
post the budget cannot cover is refused before it is sent: it costs nothing,
its case is incomplete, the run stops, and no further case or rerun starts.
After the response, the reservation is replaced by the provider's reported
cost; a post whose cost is unknown keeps its full reservation charged. Money is
Decimal throughout.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from argus.domain.research.config import research_rail_enabled

from tests.evals.measurement_eval_scorecard import SKIPPED_BUDGET_STATUS

BUDGET_ENV = "ARGUS_LIVE_EVAL_BUDGET_USD"

_MILLION = Decimal(1_000_000)
_USD = Decimal("0.000001")
_OPENROUTER_HOST = "openrouter.ai"


@dataclass(frozen=True)
class TokenPrice:
    input_usd_per_million: Decimal
    output_usd_per_million: Decimal
    source: str


_ACCEPTED_MEASUREMENT = (
    "docs/reports/evidence/current-reason-date-range/accepted-measurement/"
    "live-measurement.json"
)

# Ceilings, not list prices: each row dominates every committed receipt for the
# model (tests/evals/test_live_eval_budget.py replays them). Input is priced at
# the dearest prompt-token rate the receipts show, so cache writes stay under it.
PRICE_TABLE_USD_PER_MILLION: dict[str, TokenPrice] = {
    "x-ai/grok-4.3": TokenPrice(
        Decimal("1.25"),
        Decimal("2.50"),
        f"least-squares fit over 244 receipts in {_ACCEPTED_MEASUREMENT}, "
        "exact to 1e-17 (input 1.25, output 2.50, cached input 0.20)",
    ),
    "anthropic/claude-haiku-4.5": TokenPrice(
        Decimal("1.25"),
        Decimal("5.00"),
        f"least-squares fit over 29 receipts in {_ACCEPTED_MEASUREMENT}, exact "
        "(input 1.00, output 5.00, cache write 1.25, cache read 0.10); input "
        "pinned at the cache-write rate",
    ),
    "deepseek/deepseek-v4-flash": TokenPrice(
        Decimal("0.50"),
        Decimal("2.00"),
        "ceiling over 3,230 receipts across docs/reports/evidence (the accepted "
        "measurement fits 0.12 input, 0.16 output; older scorecards bill up to "
        "four times that)",
    ),
    "qwen/qwen3.5-9b": TokenPrice(
        Decimal("0.20"),
        Decimal("1.20"),
        "ceiling over 253 receipts across docs/reports/evidence (the accepted "
        "measurement fits 0.07 input, 0.70 output)",
    ),
    "openai/gpt-oss-120b": TokenPrice(
        Decimal("0.50"),
        Decimal("2.00"),
        "ceiling over 54 receipts across docs/reports/evidence (2026-08-15 "
        "recognition-contract and later scorecards); receipts fit no single "
        "rate, the dearest blended rate observed is 0.40",
    ),
}


# Output tokens a post can bill, as a multiple of its request's max_tokens.
# Across 19,601 committed receipts, completion_tokens (which carries reasoning:
# the pinned rates fit every receipt's bill from prompt and completion tokens
# alone) never exceeded the request's max_tokens for grok-4.3, haiku-4.5,
# gpt-oss-120b or qwen3.5-9b. deepseek-v4-flash billed 901 against 900 once
# (2026-08-21 candidate scorecard, discovery_voicing) and its requests carry no
# reasoning budget to bound it from, so it is reserved at twice max_tokens.
OUTPUT_TOKEN_MULTIPLE: dict[str, Decimal] = {"deepseek/deepseek-v4-flash": Decimal(2)}


class LiveEvalRequestRefused(RuntimeError):
    """Raised before a post leaves the process: the budget cannot cover its
    reservation, or the post cannot be reserved at all."""


def live_eval_budget_usd(environ: Mapping[str, str]) -> Decimal:
    raw = (environ.get(BUDGET_ENV) or "").strip()
    if not raw:
        raise RuntimeError(f"{BUDGET_ENV} is required for requested live evals")
    try:
        budget = Decimal(raw)
    except InvalidOperation as exc:
        raise RuntimeError(f"{BUDGET_ENV} must be a decimal amount, got {raw!r}") from exc
    if not budget.is_finite() or budget <= 0:
        raise RuntimeError(f"{BUDGET_ENV} must be a positive finite amount, got {raw!r}")
    return budget


def refuse_unbounded_rails(environ: Mapping[str, str]) -> None:
    """A budgeted run cannot start while a provider the bound does not cover is
    reachable.

    The research rail and the result follow-up both run the Perplexity Agent
    (argus.agent_runtime.research_grounded, argus.agent_runtime.result_conversation),
    whose input no setting in the repo caps and whose invoice lands in the stage
    patch, never in a route receipt. The rail is a flag; the follow-up and the
    direct search need only the Perplexity key, so the key must be absent too.
    The OpenRouter web-search provider posts outside the receipt path as well.
    """
    if research_rail_enabled():
        raise RuntimeError(
            "ARGUS_RESEARCH_RAIL_ENABLED must be off for a budgeted live eval: "
            "research spend is neither bounded nor visible to the harness"
        )
    if (environ.get("PERPLEXITY_API_KEY") or "").strip():
        raise RuntimeError(
            "PERPLEXITY_API_KEY must be unset for a budgeted live eval: the result "
            "follow-up research and the direct search bill outside the bound"
        )
    if (environ.get("ARGUS_DISCOVERY_SEARCH_PROVIDER") or "").strip().lower() == (
        "openrouter_web_search"
    ):
        raise RuntimeError(
            "ARGUS_DISCOVERY_SEARCH_PROVIDER=openrouter_web_search posts outside "
            "the route receipts and cannot be budgeted"
        )


def _token_cost(
    *, prompt_tokens: int, completion_tokens: Decimal | int, price: TokenPrice
) -> Decimal:
    return (
        Decimal(prompt_tokens) * price.input_usd_per_million
        + Decimal(completion_tokens) * price.output_usd_per_million
    ) / _MILLION


def priced_usd(model: str, *, prompt_tokens: int, completion_tokens: int) -> Decimal:
    """What the pinned ceiling says a post billing these tokens could cost."""
    return _token_cost(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        price=PRICE_TABLE_USD_PER_MILLION[model],
    )


def post_reservation_usd(body: bytes) -> tuple[str, Decimal]:
    """The model a request targets and the most it can bill.

    Input: every byte of the request body counts as a billable prompt token.
    The body carries the messages (system included), the response schema, and
    any tools; a token covers at least one byte of the text it encodes, and the
    JSON framing only adds bytes. Committed receipts bill at least 3.86 bytes
    per prompt token (docs/reports/evidence/live-eval-per-call-guard).
    Output: the request's max_tokens (or max_completion_tokens), times the
    model's OUTPUT_TOKEN_MULTIPLE.
    """
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise LiveEvalRequestRefused("request body is not JSON") from exc
    model = str(payload.get("model") or "")
    price = PRICE_TABLE_USD_PER_MILLION.get(model)
    if price is None:
        raise LiveEvalRequestRefused(f"model {model!r} has no pinned price")
    if payload.get("plugins") or model.endswith(":online") or payload.get("stream"):
        raise LiveEvalRequestRefused(
            "web search and streamed posts bill outside the bound"
        )
    max_tokens = payload.get("max_tokens") or payload.get("max_completion_tokens")
    if not isinstance(max_tokens, int) or max_tokens <= 0:
        raise LiveEvalRequestRefused("request sets no max_tokens to bound its output")
    multiple = OUTPUT_TOKEN_MULTIPLE.get(model, Decimal(1))
    return model, _token_cost(
        prompt_tokens=len(body), completion_tokens=multiple * max_tokens, price=price
    )


@dataclass(frozen=True)
class Reservation:
    post: int
    case_id: str | None
    task: str
    model: str
    body_bytes: int
    reserved_usd: Decimal


@dataclass
class SpendLedger:
    """One budget for the whole run; every change happens under its lock."""

    budget_usd: Decimal
    stopped_reason: str | None = None
    posts: list[dict[str, Any]] = field(default_factory=list)
    _outstanding: dict[int, Decimal] = field(default_factory=dict)
    _settled_usd: Decimal = Decimal(0)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def committed_usd(self) -> Decimal:
        with self._lock:
            return self._settled_usd + sum(self._outstanding.values(), Decimal(0))

    @property
    def spent_usd(self) -> Decimal:
        with self._lock:
            return self._settled_usd

    def refusals(self) -> int:
        with self._lock:
            return sum(1 for post in self.posts if post["refused"])

    def stop(self, reason: str) -> None:
        with self._lock:
            self.stopped_reason = self.stopped_reason or reason

    def reserve(self, *, task: str, case_id: str | None, body: bytes) -> Reservation:
        """Reserve the post's maximum cost, or refuse it before it is sent."""
        try:
            model, cost = post_reservation_usd(body)
        except LiveEvalRequestRefused as exc:
            self._refuse(
                task=task, case_id=case_id, model=None, size=len(body), reason=str(exc)
            )
            raise
        with self._lock:
            committed = self._settled_usd + sum(self._outstanding.values(), Decimal(0))
            reason = self.stopped_reason or (
                None
                if committed + cost <= self.budget_usd
                else f"remaining {_money(self.budget_usd - committed)} USD does not "
                f"cover the {_money(cost)} USD reservation"
            )
            if reason is None:
                post = len(self.posts)
                self._outstanding[post] = cost
                self.posts.append(
                    {
                        "post": post,
                        "case_id": case_id,
                        "task": task,
                        "model": model,
                        "body_bytes": len(body),
                        "reserved_usd": _money(cost),
                        "actual_usd": None,
                        "charged_usd": None,
                        "refused": False,
                    }
                )
                return Reservation(post, case_id, task, model, len(body), cost)
        self._refuse(
            task=task, case_id=case_id, model=model, size=len(body), reason=reason
        )
        raise LiveEvalRequestRefused(reason)

    def settle(self, reservation: Reservation, actual_usd: Decimal | None) -> None:
        """Replace the reservation with the reported cost; an unknown cost
        keeps the full reservation charged. A bill above the reservation
        breaks the bound's premise, so the run stops."""
        charged = reservation.reserved_usd if actual_usd is None else actual_usd
        with self._lock:
            self._outstanding.pop(reservation.post, None)
            self._settled_usd += charged
            record = self.posts[reservation.post]
            record["actual_usd"] = None if actual_usd is None else _money(actual_usd)
            record["charged_usd"] = _money(charged)
            if actual_usd is not None and actual_usd > reservation.reserved_usd:
                self.stopped_reason = self.stopped_reason or (
                    f"post {reservation.post} billed {_money(actual_usd)} USD over its "
                    f"{_money(reservation.reserved_usd)} USD reservation"
                )

    def _refuse(
        self, *, task: str, case_id: str | None, model: str | None, size: int, reason: str
    ) -> None:
        with self._lock:
            self.stopped_reason = self.stopped_reason or reason
            self.posts.append(
                {
                    "post": len(self.posts),
                    "case_id": case_id,
                    "task": task,
                    "model": model,
                    "body_bytes": size,
                    "reserved_usd": _money(Decimal(0)),
                    "actual_usd": None,
                    "charged_usd": _money(Decimal(0)),
                    "refused": True,
                    "refusal": reason,
                }
            )


_PENDING_TASK: ContextVar[str] = ContextVar(
    "live_eval_pending_task", default="unrecorded"
)
_CURRENT_CASE: ContextVar[str | None] = ContextVar("live_eval_current_case", default=None)


def record_task(task: str, payload: dict[str, object]) -> dict[str, object]:
    """An openrouter_request_guard that names the task of the post about to be
    sent, so the ledger can record it; it never changes the request."""
    _PENDING_TASK.set(str(task))
    return payload


def reported_cost_usd(response: httpx.Response) -> Decimal | None:
    """The provider's reported cost of a completed post, or None."""
    if response.status_code != 200:
        return None
    try:
        usage = response.json().get("usage") or {}
        cost = usage.get("cost")
        return None if cost is None or isinstance(cost, bool) else Decimal(str(cost))
    except (ValueError, AttributeError, InvalidOperation):
        return None


def _is_openrouter(request: httpx.Request) -> bool:
    return request.url.host.endswith(_OPENROUTER_HOST)


@contextmanager
def metered_openrouter(ledger: SpendLedger) -> Iterator[None]:
    """Meter every httpx post to OpenRouter, sync and async, at the transport:
    fallbacks, retries, the judge and any SDK client all pass through here."""
    sync_send = httpx.Client.send
    async_send = httpx.AsyncClient.send

    def reserve(request: httpx.Request) -> Reservation:
        return ledger.reserve(
            task=_PENDING_TASK.get(), case_id=_CURRENT_CASE.get(), body=request.content
        )

    def send(self: httpx.Client, request: httpx.Request, **kwargs: Any) -> httpx.Response:
        if not _is_openrouter(request):
            return sync_send(self, request, **kwargs)
        reservation = reserve(request)
        try:
            response = sync_send(self, request, **kwargs)
        except BaseException:
            ledger.settle(reservation, None)
            raise
        ledger.settle(reservation, reported_cost_usd(response))
        return response

    async def asend(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: Any
    ) -> httpx.Response:
        if not _is_openrouter(request):
            return await async_send(self, request, **kwargs)
        reservation = reserve(request)
        try:
            response = await async_send(self, request, **kwargs)
        except BaseException:
            ledger.settle(reservation, None)
            raise
        ledger.settle(reservation, reported_cost_usd(response))
        return response

    httpx.Client.send = send  # type: ignore[method-assign]
    httpx.AsyncClient.send = asend  # type: ignore[method-assign]
    try:
        yield
    finally:
        httpx.Client.send = sync_send  # type: ignore[method-assign]
        httpx.AsyncClient.send = async_send  # type: ignore[method-assign]


def run_metered_cases(
    cases: Iterable[Any],
    *,
    run_case: Callable[[Any], dict[str, Any]],
    ledger: SpendLedger,
    rerun_failed: bool = True,
) -> list[dict[str, Any]]:
    """Run cases until the ledger stops. A case with a refused post is
    incomplete; a failed case runs once more only while the run goes on."""
    results: list[dict[str, Any]] = []
    for case in cases:
        if ledger.stopped_reason is not None:
            results.append(_skipped_for_budget(case, ledger.stopped_reason))
            continue
        result = _metered_attempt(case, run_case, ledger, attempt=1)
        if (
            rerun_failed
            and result["status"] == "failed"
            and ledger.stopped_reason is None
        ):
            first = result
            result = _metered_attempt(case, run_case, ledger, attempt=2)
            result["budget"]["first_attempt"] = {
                "status": first["status"],
                "failed_checks": list(first["failed_checks"]),
                "infrastructure_errors": list(first["infrastructure_errors"]),
                "charged_usd": first["budget"]["charged_usd"],
            }
        results.append(result)
    return results


def _metered_attempt(
    case: Any,
    run_case: Callable[[Any], dict[str, Any]],
    ledger: SpendLedger,
    *,
    attempt: int,
) -> dict[str, Any]:
    refused_before = ledger.refusals()
    first_post = len(ledger.posts)
    token = _CURRENT_CASE.set(str(case.id))
    try:
        result = run_case(case)
    finally:
        _CURRENT_CASE.reset(token)
    posts = ledger.posts[first_post:]
    charged = sum(
        (Decimal(post["charged_usd"] or post["reserved_usd"]) for post in posts),
        Decimal(0),
    )
    if ledger.refusals() > refused_before:
        # A refused post never ran, so the case measured nothing for it.
        result["status"] = SKIPPED_BUDGET_STATUS
        result["failed_checks"] = [
            *result.get("failed_checks", []),
            f"budget:{ledger.stopped_reason}",
        ]
    result["budget"] = {
        "attempts": attempt,
        "posts": len(posts),
        "reserved_usd": _money(
            sum((Decimal(post["reserved_usd"]) for post in posts), Decimal(0))
        ),
        "charged_usd": _money(charged),
    }
    return result


def _skipped_for_budget(case: Any, reason: str) -> dict[str, Any]:
    expected_fail = getattr(case, "expected_fail", None)
    return {
        "id": case.id,
        "category": case.category,
        "status": SKIPPED_BUDGET_STATUS,
        "failed_checks": [f"budget:{reason}"],
        "expected_fail": (
            None
            if expected_fail is None
            else {
                "issue": expected_fail.issue,
                "reason": expected_fail.reason,
                "allowed_failures": list(expected_fail.allowed_failures),
            }
        ),
        "typed_outcome": None,
        "prose_judge": None,
        "infrastructure_errors": [],
        "route_receipts": [],
        "budget": {"attempts": 0, "posts": 0, "skipped_reason": reason},
    }


def budget_summary(
    ledger: SpendLedger, results: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    rows = list(results)
    skipped = [r for r in rows if r.get("status") == SKIPPED_BUDGET_STATUS]
    ran = [r for r in rows if r.get("status") != SKIPPED_BUDGET_STATUS]
    return {
        "guard": "per_post_reservation",
        "budget_usd": _money(ledger.budget_usd),
        "spent_usd": _money(ledger.spent_usd),
        "remaining_usd": _money(ledger.budget_usd - ledger.committed_usd),
        "complete": not skipped and ledger.stopped_reason is None,
        "stopped_reason": ledger.stopped_reason,
        "price_table_usd_per_million": {
            model: {
                "input": str(price.input_usd_per_million),
                "output": str(price.output_usd_per_million),
                "output_token_multiple": str(OUTPUT_TOKEN_MULTIPLE.get(model, 1)),
                "source": price.source,
            }
            for model, price in sorted(PRICE_TABLE_USD_PER_MILLION.items())
        },
        "cases": {
            "completed": len(ran),
            "failed": sum(1 for r in ran if r.get("status") == "failed"),
            "rerun": sum(1 for r in ran if (r.get("budget") or {}).get("attempts") == 2),
            "skipped_budget": len(skipped),
        },
        "posts": list(ledger.posts),
    }


def _money(value: Decimal) -> str:
    return str(value.quantize(_USD))
