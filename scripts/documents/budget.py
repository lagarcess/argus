from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from argus.llm.openrouter import openrouter_profile_for_task, openrouter_request_guard


def rate(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("invalid_price") from None
    if not result.is_finite() or result < 0:
        raise ValueError("invalid_price")
    return result


@dataclass(frozen=True)
class PriceEnvelope:
    model: str
    provider: str
    context_tokens: int
    output_tokens: int
    prompt: Decimal
    completion: Decimal

    @property
    def maximum_cost(self) -> Decimal:
        # Full uncached context also bounds image tokens; output is over-reserved.
        return self.context_tokens * self.prompt + self.output_tokens * self.completion

    def evidence(self) -> dict:
        return dict(
            model=self.model,
            provider=self.provider,
            context_tokens=self.context_tokens,
            output_tokens=self.output_tokens,
            prompt_usd_per_token=str(self.prompt),
            completion_usd_per_token=str(self.completion),
            maximum_request_usd=str(self.maximum_cost),
        )


def price_envelope(model: str, endpoints: list[dict]) -> PriceEnvelope:
    profile = openrouter_profile_for_task("document_extraction")
    envelopes = []
    for endpoint in endpoints:
        try:
            prices = endpoint["pricing"]
            prompt, completion = rate(prices["prompt"]), rate(prices["completion"])
            for name, value in prices.items():
                if name in {"prompt", "completion", "discount"}:
                    continue
                if name == "input_cache_read":
                    if rate(value) > prompt:
                        raise ValueError("unbounded_cache_price")
                elif rate(value) != 0:
                    raise ValueError("unbounded_additional_price")
            context = endpoint["context_length"]
            if not isinstance(context, int) or isinstance(context, bool) or context <= 0:
                raise ValueError("missing_context_limit")
            if not {"structured_outputs", "max_tokens"}.issubset(
                endpoint["supported_parameters"]
            ):
                continue
            output = endpoint.get("max_completion_tokens")
            if output is not None and output < profile.max_tokens:
                continue
            provider = endpoint["tag"]
            if not isinstance(provider, str) or not provider:
                continue
            envelopes.append(
                PriceEnvelope(
                    model, provider, context, profile.max_tokens, prompt, completion
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    if not envelopes:
        raise ValueError("no_bounded_endpoint")
    return min(envelopes, key=lambda item: item.maximum_cost)


@dataclass
class BenchmarkBudget:
    envelope: PriceEnvelope
    cap: Decimal
    max_attempts: int
    reserved: Decimal = field(default=Decimal(0), init=False)
    attempted: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        if not self.cap.is_finite() or self.cap <= 0 or self.max_attempts <= 0:
            raise ValueError("invalid_spend_cap")
        if self.envelope.maximum_cost * self.max_attempts > self.cap:
            raise ValueError("run_exceeds_cap")

    def evidence(self) -> dict:
        return self.envelope.evidence() | dict(
            approved_cap_usd=str(self.cap),
            maximum_run_usd=str(self.envelope.maximum_cost * self.max_attempts),
            reserved_usd=str(self.reserved),
            attempts=len(self.attempted),
            attempted_fixtures=sorted(self.attempted),
        )

    @contextmanager
    def attempt(self, fixture_id: str, save: Callable[[], None]) -> Iterator[None]:
        def authorize(task: str, payload: dict) -> dict:
            if fixture_id in self.attempted:
                raise ValueError("already_attempted")
            if (
                len(self.attempted) >= self.max_attempts
                or self.reserved + self.envelope.maximum_cost > self.cap
            ):
                raise ValueError("spend_cap_reached")
            provider = payload.get("provider", {})
            privacy = dict(
                require_parameters=True,
                data_collection="deny",
                zdr=True,
                allow_fallbacks=False,
            )
            if (
                task != "document_extraction"
                or payload.get("model") != self.envelope.model
                or payload.get("max_tokens") != self.envelope.output_tokens
                or not isinstance(provider, dict)
                or any(provider.get(k) != v for k, v in privacy.items())
                or any(
                    k in payload
                    for k in ("tools", "plugins", "models", "route", "reasoning")
                )
            ):
                raise ValueError("unexpected_benchmark_request")
            guarded = payload | {
                "provider": provider
                | dict(
                    only=[self.envelope.provider],
                    max_price=dict(
                        prompt=float(self.envelope.prompt * 1_000_000),
                        completion=float(self.envelope.completion * 1_000_000),
                        request=0,
                        image=0,
                    ),
                )
            }
            self.attempted.add(fixture_id)
            self.reserved += self.envelope.maximum_cost
            save()
            return guarded

        with openrouter_request_guard(authorize):
            yield
