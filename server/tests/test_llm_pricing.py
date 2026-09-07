"""Tests for deterministic provider-token cost estimates."""

import unittest
from decimal import Decimal

from app.core.llm_pricing import estimate_cost_usd


class LLMPriceTest(unittest.TestCase):
    def test_openai_standard_and_cached_tokens(self) -> None:
        cost = estimate_cost_usd(
            "openai",
            "gpt-5.6-luna",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            cache_read_tokens=100_000,
            cache_write_tokens=100_000,
        )

        self.assertEqual(cost, Decimal("1.387000"))

    def test_deepseek_cache_hit_uses_lower_rate(self) -> None:
        cost = estimate_cost_usd(
            "deepseek",
            "deepseek-v4-flash",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            cache_read_tokens=250_000,
            cache_write_tokens=None,
        )

        self.assertEqual(cost, Decimal("0.385700"))

    def test_unknown_model_is_unavailable(self) -> None:
        cost = estimate_cost_usd(
            "openai",
            "unknown",
            input_tokens=10,
            output_tokens=10,
            cache_read_tokens=None,
            cache_write_tokens=None,
        )

        self.assertIsNone(cost)


if __name__ == "__main__":
    unittest.main()
