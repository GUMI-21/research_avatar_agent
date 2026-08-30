"""Small, explicit pricing table for local run-cost estimates."""

from dataclasses import dataclass
from decimal import Decimal


MILLION = Decimal("1000000")
USD_PRECISION = Decimal("0.000001")


@dataclass(frozen=True)
class ModelPricing:
    input: Decimal
    cached_input: Decimal
    output: Decimal
    cache_write: Decimal | None = None


def _price(
    input_rate: str,
    cached_rate: str,
    output_rate: str,
    cache_write_rate: str | None = None,
) -> ModelPricing:
    return ModelPricing(
        input=Decimal(input_rate),
        cached_input=Decimal(cached_rate),
        output=Decimal(output_rate),
        cache_write=Decimal(cache_write_rate) if cache_write_rate else None,
    )


# USD per one million tokens. Update independently from provider adapters.
MODEL_PRICING: dict[tuple[str, str], ModelPricing] = {
    ("openai", "gpt-5.6-luna"): _price("0.20", "0.02", "1.20", "0.25"),
    ("openai", "gpt-5.6-terra"): _price("2.00", "0.20", "12.00", "2.50"),
    ("openai", "gpt-5.6-sol"): _price("4.00", "0.40", "20.00", "5.00"),
    ("gemini", "gemini-3.5-flash"): _price("1.50", "0.15", "9.00"),
    ("gemini", "gemini-2.5-flash"): _price("0.30", "0.03", "2.50"),
    ("gemini", "gemini-2.5-flash-lite"): _price("0.10", "0.01", "0.40"),
    ("deepseek", "deepseek-v4-flash"): _price("0.14", "0.0028", "0.28"),
    ("deepseek", "deepseek-v4-pro"): _price("0.435", "0.003625", "0.87"),
}

# 计算token花费
def estimate_cost_usd(
    provider: str | None,
    model: str | None,
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    cache_read_tokens: int | None,
    cache_write_tokens: int | None,
) -> Decimal | None:
    pricing = MODEL_PRICING.get((provider or "", model or ""))
    if pricing is None or input_tokens is None or output_tokens is None:
        return None

    cached = min(cache_read_tokens or 0, input_tokens)
    written = min(cache_write_tokens or 0, input_tokens - cached)
    uncached = input_tokens - cached - written
    write_rate = pricing.cache_write or pricing.input
    cost = (
        Decimal(uncached) * pricing.input
        + Decimal(cached) * pricing.cached_input
        + Decimal(written) * write_rate
        + Decimal(output_tokens) * pricing.output
    ) / MILLION
    return cost.quantize(USD_PRECISION)
