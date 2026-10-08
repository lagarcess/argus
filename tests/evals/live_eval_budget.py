"""Hard spend bound for the live measurement eval.

A case starts only while the remaining budget covers the most it can cost,
and what it did cost is charged from its receipts afterwards. The bound is
enforced rather than estimated: every OpenRouter post a turn can make reserves
a permit in the runtime's own turn scope, and a request guard refuses any post
whose task, model or size falls outside the priced table before it is sent. A
token is at least one byte under every byte-level tokenizer, so a request's
UTF-8 size bounds the prompt tokens it can bill. Money is Decimal throughout.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from argus.agent_runtime.turn_execution import (
    DEFAULT_TURN_CALL_ALLOWANCE,
    LAST_RESORT_REPAIR_CALL_GRANT,
)
from argus.domain.research.config import research_rail_enabled
from argus.llm.openrouter import openrouter_model_candidates
from argus.llm.openrouter_tasks import OPENROUTER_PROFILES, OpenRouterTask

from tests.evals.measurement_eval_scorecard import SKIPPED_BUDGET_STATUS

BUDGET_ENV = "ARGUS_LIVE_EVAL_BUDGET_USD"

_MILLION = Decimal(1_000_000)
_USD = Decimal("0.000001")
# OpenRouter reports cost to this precision; a receipt within it agrees with
# the table.
_RECEIPT_TOLERANCE_USD = Decimal("0.00001")

# Largest primary read measured offline on 2026-10-08 over every fixture case
# (x-ai/grok-4.3 and anthropic/claude-haiku-4.5 wire payloads): 61,734 bytes,
# 3.9 to 4.9 bytes per billed prompt token in the accepted measurement.
INPUT_CAP_BYTES = 98_304
# The prose judge posts its rubric, the case prompt, the reply and what renders
# beside it; across every committed receipt its task's prompt peaks at 2,519
# tokens, about 12,300 bytes at 4.9 bytes per token. The cap is 2.6 times that.
# A judge request over it is refused before it is sent, and the case is then
# incomplete, never a pass.
JUDGE_INPUT_CAP_BYTES = 32_768
JUDGE_SCHEMA_NAME = "ArgusProseJudgeResponse"

# A candidate model is posted once, and once more without `reasoning` after a
# 400 (argus.llm.openrouter._post_openrouter_json_schema).
POSTS_PER_CANDIDATE = 2

# Tasks a measured turn is allowed to post; the guard refuses every other task
# before it is sent, so no unlisted profile can bill.
BOUNDED_TASKS: frozenset[OpenRouterTask] = frozenset(
    {
        "interpretation",
        "interpretation_repair",
        "asset_mention_preflight",
        "field_fidelity",
        "capability_conflict",
        "clarification",
        "chat_composer",
        "discovery_extraction",
        "discovery_voicing",
        "discovery_model_knowledge",
        "knowledge_route",
        "knowledge_voicing",
    }
)
_REPAIR_TASK: OpenRouterTask = "interpretation_repair"
_ROUTING_RESERVED_TASK: OpenRouterTask = "knowledge_route"
_RECOVERY_RESERVED_TASK: OpenRouterTask = "knowledge_voicing"
_JUDGE_TASK: OpenRouterTask = "chat_composer"


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


class UnpricedCallError(ValueError):
    """A task or model the table cannot bound."""


class LiveEvalRequestRefused(RuntimeError):
    """Raised by the request guard before a post leaves the process. Its class
    name is the receipt's failure_mode, which is how a refusal is told apart
    from a provider failure that may have billed."""


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


def request_size_bytes(payload: Mapping[str, object]) -> int:
    return len(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


@dataclass(frozen=True)
class BoundTable:
    """The pinned prices and the input cap, and every bound derived from them."""

    prices: Mapping[str, TokenPrice]
    input_cap_bytes: int
    judge_input_cap_bytes: int | None = None

    def cap_bytes(self, *, judge: bool) -> int:
        """The input cap of a judge post or of any turn post."""
        if judge and self.judge_input_cap_bytes is not None:
            return self.judge_input_cap_bytes
        return self.input_cap_bytes

    def post_bound_usd(self, task: str, model: str, *, judge: bool = False) -> Decimal:
        """The most one post of `task` to `model` can bill: every input byte
        under its cap billed as a token, and the profile's max_tokens of
        output."""
        bounded_task = _bounded_task(task)
        if bounded_task is None:
            raise UnpricedCallError(f"task {task!r} is outside the bounded task set")
        price = self.prices.get(model)
        if price is None:
            raise UnpricedCallError(f"model {model!r} has no pinned price")
        max_tokens = OPENROUTER_PROFILES[bounded_task].max_tokens
        return _token_cost(
            prompt_tokens=self.cap_bytes(judge=judge),
            completion_tokens=max_tokens,
            price=price,
        )

    def task_candidates_from_env(self) -> dict[str, tuple[str, ...]]:
        """Every model a bounded task can resolve to in this environment,
        primary then fallback, the way the runtime resolves them. Refuses an
        unpriced or unconfigured tier before any call."""
        candidates: dict[str, tuple[str, ...]] = {}
        for task in sorted(BOUNDED_TASKS):
            models = tuple(openrouter_model_candidates(task=task))
            if not models:
                raise UnpricedCallError(f"task {task!r} has no configured model")
            for model in models:
                self.post_bound_usd(task, model)
            candidates[task] = models
        return candidates

    def judge_candidates_from_env(self, judge_model: str | None) -> tuple[str, ...]:
        models = tuple(openrouter_model_candidates(judge_model or None, task=_JUDGE_TASK))
        if not models:
            raise UnpricedCallError("the prose judge has no configured model")
        for model in models:
            self.post_bound_usd(_JUDGE_TASK, model)
        return models

    def turn_bound_usd(
        self,
        task_candidates: Mapping[str, tuple[str, ...]],
        *,
        research_reachable: bool,
    ) -> Decimal:
        """The most one turn inside turn_execution_scope can bill.

        The corridor grants DEFAULT_TURN_CALL_ALLOWANCE permits to any task and
        the last-resort repair grant adds LAST_RESORT_REPAIR_CALL_GRANT permits
        for interpretation_repair only. The knowledge_route and
        knowledge_voicing reservations are granted only on the research rail
        (reserve_provider_call grants the route only while
        research_rail_enabled(), and only the rail's no-lookup answer enters
        research_recovery_scope), so they count only when research is
        reachable when the bound is set. Every post reserves one permit
        (argus.agent_runtime.turn_execution.reserve_provider_call). Nothing
        else can bill: refuse_unbounded_rails keeps every other paid provider
        unreachable.
        """
        dearest = max(
            self.post_bound_usd(task, model)
            for task, models in task_candidates.items()
            for model in models
        )
        bound = Decimal(DEFAULT_TURN_CALL_ALLOWANCE) * dearest + Decimal(
            LAST_RESORT_REPAIR_CALL_GRANT
        ) * self._dearest_post(task_candidates, _REPAIR_TASK)
        if research_reachable:
            bound += self._dearest_post(
                task_candidates, _ROUTING_RESERVED_TASK
            ) + self._dearest_post(task_candidates, _RECOVERY_RESERVED_TASK)
        return bound

    def judge_bound_usd(self, judge_candidates: tuple[str, ...]) -> Decimal:
        """The judge runs in its own turn scope, so its posts are the smaller
        of the corridor and one invoke's candidate ladder."""
        posts = min(
            DEFAULT_TURN_CALL_ALLOWANCE, POSTS_PER_CANDIDATE * len(judge_candidates)
        )
        return Decimal(posts) * max(
            self.post_bound_usd(_JUDGE_TASK, model, judge=True)
            for model in judge_candidates
        )

    def request_guard(self) -> Callable[[str, dict[str, object]], dict[str, object]]:
        """A guard for argus.llm.openrouter.openrouter_request_guard that
        refuses a post the bound does not cover."""

        def guard(task: str, payload: dict[str, object]) -> dict[str, object]:
            if _bounded_task(task) is None:
                raise LiveEvalRequestRefused(
                    f"task {task!r} is outside the bounded task set"
                )
            model = str(payload.get("model") or "")
            if model not in self.prices:
                raise LiveEvalRequestRefused(f"model {model!r} has no pinned price")
            size = request_size_bytes(payload)
            cap = self.cap_bytes(
                judge=task == _JUDGE_TASK and _schema_name(payload) == JUDGE_SCHEMA_NAME
            )
            if size > cap:
                raise LiveEvalRequestRefused(
                    f"request of {size} bytes exceeds the {cap} byte input cap"
                )
            return payload

        return guard

    def receipt_charge_usd(self, receipt: Mapping[str, Any]) -> Decimal:
        """What a receipt costs the budget: the provider's figure when it
        reported one, nothing when no post left the process, and the full post
        bound when a post may have billed without saying how much."""
        if receipt.get("outcome") == "skipped":
            return Decimal(0)
        if receipt.get("failure_mode") == LiveEvalRequestRefused.__name__:
            return Decimal(0)
        raw_cost = receipt.get("usage_cost_usd")
        if raw_cost is not None:
            try:
                return Decimal(str(raw_cost))
            except InvalidOperation:
                pass
        return self.post_bound_usd(
            str(receipt.get("task")), str(receipt.get("model")), judge=_judged(receipt)
        )

    def receipt_bound_violation(self, receipt: Mapping[str, Any]) -> str | None:
        """Why a receipt shows the bound's assumptions broken, or None.

        The checks are the assumptions the bound rests on: the guard's size
        cap holds the prompt tokens, the profile's max_tokens holds the
        completion (reasoning included), and the pinned rates dominate the
        provider's bill.
        """
        if receipt.get("outcome") == "skipped":
            return None
        task = str(receipt.get("task"))
        model = str(receipt.get("model"))
        usage = receipt.get("token_usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        cap = self.cap_bytes(judge=_judged(receipt))
        if prompt_tokens > cap:
            return f"prompt_tokens {prompt_tokens} exceeds the {cap} input cap"
        bounded_task = _bounded_task(task)
        if bounded_task is not None:
            max_tokens = OPENROUTER_PROFILES[bounded_task].max_tokens
            if completion_tokens > max_tokens:
                return f"completion_tokens {completion_tokens} exceeds max_tokens {max_tokens}"
        raw_cost = receipt.get("usage_cost_usd")
        if raw_cost is None or not usage:
            return None
        price = self.prices.get(model)
        if price is None:
            return f"model {model!r} billed without a pinned price"
        priced = _token_cost(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, price=price
        )
        cost = Decimal(str(raw_cost))
        if cost > priced + _RECEIPT_TOLERANCE_USD:
            return f"cost {cost} exceeds the pinned rate's {_money(priced)}"
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "input_cap_bytes": self.input_cap_bytes,
            "judge_input_cap_bytes": self.cap_bytes(judge=True),
            "price_table_usd_per_million": {
                model: {
                    "input": str(price.input_usd_per_million),
                    "output": str(price.output_usd_per_million),
                    "source": price.source,
                }
                for model, price in sorted(self.prices.items())
            },
        }

    def _dearest_post(
        self, task_candidates: Mapping[str, tuple[str, ...]], task: str
    ) -> Decimal:
        return max(self.post_bound_usd(task, model) for model in task_candidates[task])


PINNED = BoundTable(
    prices=PRICE_TABLE_USD_PER_MILLION,
    input_cap_bytes=INPUT_CAP_BYTES,
    judge_input_cap_bytes=JUDGE_INPUT_CAP_BYTES,
)


@dataclass(frozen=True)
class CaseBound:
    turns: int
    turn_usd: Decimal
    judge_usd: Decimal

    @property
    def total_usd(self) -> Decimal:
        return Decimal(self.turns) * self.turn_usd + self.judge_usd

    def as_dict(self) -> dict[str, Any]:
        return {
            "turns": self.turns,
            "turn_usd": _money(self.turn_usd),
            "judge_usd": _money(self.judge_usd),
            "total_usd": _money(self.total_usd),
        }


def case_bound(
    *,
    turns: int,
    judged: bool,
    turn_usd: Decimal,
    judge_usd: Decimal,
) -> CaseBound:
    return CaseBound(
        turns=turns, turn_usd=turn_usd, judge_usd=judge_usd if judged else Decimal(0)
    )


@dataclass
class BudgetLedger:
    budget_usd: Decimal
    spent_usd: Decimal = Decimal(0)
    stopped_reason: str | None = None
    charges: list[dict[str, Any]] = field(default_factory=list)

    @property
    def remaining_usd(self) -> Decimal:
        return self.budget_usd - self.spent_usd

    def covers(self, bound_usd: Decimal) -> bool:
        return self.stopped_reason is None and self.remaining_usd >= bound_usd

    def charge(self, amount_usd: Decimal, *, case_id: str, attempt: int) -> None:
        self.spent_usd += amount_usd
        self.charges.append(
            {"case_id": case_id, "attempt": attempt, "usd": _money(amount_usd)}
        )

    def stop(self, reason: str) -> None:
        if self.stopped_reason is None:
            self.stopped_reason = reason


def run_budgeted_cases(
    cases: Iterable[Any],
    *,
    run_case: Callable[[Any], dict[str, Any]],
    bound_for: Callable[[Any], CaseBound],
    ledger: BudgetLedger,
    table: BoundTable = PINNED,
    rerun_failed: bool = True,
) -> list[dict[str, Any]]:
    """Run each case while the budget covers its bound, charging what it cost.

    A case whose final status is `failed` runs once more, and only while the
    budget still covers the bound. A receipt that breaks the bound's
    assumptions stops the run: the rest of the cases are skipped for budget.
    """
    results: list[dict[str, Any]] = []
    for case in cases:
        bound = bound_for(case)
        if not ledger.covers(bound.total_usd):
            results.append(_skipped_for_budget(case, bound, ledger))
            continue
        first = _charged_attempt(case, run_case, bound, ledger, table, attempt=1)
        final = first
        if (
            rerun_failed
            and first["status"] == "failed"
            and ledger.covers(bound.total_usd)
        ):
            final = _charged_attempt(case, run_case, bound, ledger, table, attempt=2)
            final["budget"]["first_attempt"] = {
                "status": first["status"],
                "failed_checks": list(first["failed_checks"]),
                "infrastructure_errors": list(first["infrastructure_errors"]),
                "charged_usd": first["budget"]["charged_usd"],
            }
        results.append(final)
    return results


def budget_summary(
    ledger: BudgetLedger,
    results: Iterable[Mapping[str, Any]],
    *,
    table: BoundTable = PINNED,
) -> dict[str, Any]:
    rows = list(results)
    skipped = [r for r in rows if r.get("status") == SKIPPED_BUDGET_STATUS]
    ran = [r for r in rows if r.get("status") != SKIPPED_BUDGET_STATUS]
    bounds = sum(
        (
            Decimal(str((r.get("budget") or {}).get("bound", {}).get("total_usd") or 0))
            for r in rows
        ),
        Decimal(0),
    )
    return {
        "budget_usd": _money(ledger.budget_usd),
        "spent_usd": _money(ledger.spent_usd),
        "remaining_usd": _money(ledger.remaining_usd),
        "complete": not skipped and ledger.stopped_reason is None,
        "stopped_reason": ledger.stopped_reason,
        **table.as_dict(),
        "sum_of_case_bounds_usd": _money(bounds),
        "cases": {
            "completed": len(ran),
            "failed": sum(1 for r in ran if r.get("status") == "failed"),
            "rerun": sum(1 for r in ran if (r.get("budget") or {}).get("attempts") == 2),
            "skipped_budget": len(skipped),
        },
        "charges": list(ledger.charges),
    }


def _charged_attempt(
    case: Any,
    run_case: Callable[[Any], dict[str, Any]],
    bound: CaseBound,
    ledger: BudgetLedger,
    table: BoundTable,
    *,
    attempt: int,
) -> dict[str, Any]:
    result = run_case(case)
    receipts = [r for r in result.get("route_receipts") or [] if isinstance(r, Mapping)]
    charged = sum((table.receipt_charge_usd(r) for r in receipts), Decimal(0))
    violation = next(
        (
            reason
            for r in receipts
            if (reason := table.receipt_bound_violation(r)) is not None
        ),
        None,
    )
    if violation is not None:
        charged = max(charged, bound.total_usd)
        ledger.stop(f"{result['id']}: {violation}")
    ledger.charge(charged, case_id=str(result["id"]), attempt=attempt)
    refused = sorted(
        {
            str(r.get("task"))
            for r in receipts
            if r.get("failure_mode") == LiveEvalRequestRefused.__name__
        }
    )
    if refused:
        # A post the bound would not cover never ran, so the case measured
        # nothing for it: incomplete, never a product failure or a pass, and
        # never rerun.
        result["status"] = SKIPPED_BUDGET_STATUS
        result["failed_checks"] = [
            *result.get("failed_checks", []),
            *(f"budget:request_refused:{task}" for task in refused),
        ]
    result["budget"] = {
        "bound": bound.as_dict(),
        "charged_usd": _money(charged),
        "attempts": attempt,
        "bound_violation": violation,
    }
    return result


def _skipped_for_budget(
    case: Any, bound: CaseBound, ledger: BudgetLedger
) -> dict[str, Any]:
    reason = ledger.stopped_reason or (
        f"remaining {_money(ledger.remaining_usd)} USD does not cover the "
        f"{_money(bound.total_usd)} USD bound"
    )
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
        "budget": {
            "bound": bound.as_dict(),
            "charged_usd": _money(Decimal(0)),
            "attempts": 0,
            "skipped_reason": reason,
        },
    }


def _schema_name(payload: Mapping[str, object]) -> str | None:
    response_format = payload.get("response_format")
    if not isinstance(response_format, Mapping):
        return None
    schema = response_format.get("json_schema")
    return str(schema.get("name")) if isinstance(schema, Mapping) else None


def _judged(receipt: Mapping[str, Any]) -> bool:
    return (
        receipt.get("task") == _JUDGE_TASK
        and receipt.get("schema_name") == JUDGE_SCHEMA_NAME
    )


def _bounded_task(task: str) -> OpenRouterTask | None:
    for bounded in BOUNDED_TASKS:
        if bounded == task:
            return bounded
    return None


def _token_cost(
    *, prompt_tokens: int, completion_tokens: int, price: TokenPrice
) -> Decimal:
    return (
        Decimal(prompt_tokens) * price.input_usd_per_million
        + Decimal(completion_tokens) * price.output_usd_per_million
    ) / _MILLION


def _money(value: Decimal) -> str:
    return str(value.quantize(_USD))
