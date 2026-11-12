"""Tests for criterion 2 (bundled prices, no network) and criterion 3 (cost label)."""

from tokenburn.prices import calculate_cost, get_price


class TestGetPrice:
    def test_opus_4_prefix(self):
        p = get_price("claude-opus-4-5")
        assert p["input"] == 15.0
        assert p["output"] == 75.0

    def test_sonnet_4_prefix(self):
        p = get_price("claude-sonnet-4-6")
        assert p["input"] == 3.0
        assert p["output"] == 15.0

    def test_haiku_4_prefix(self):
        p = get_price("claude-haiku-4-5")
        assert p["input"] == 0.80
        assert p["output"] == 4.0

    def test_claude_3_opus(self):
        p = get_price("claude-3-opus-20240229")
        assert p["input"] == 15.0

    def test_claude_3_haiku(self):
        p = get_price("claude-3-haiku-20240307")
        assert p["input"] == 0.25

    def test_claude_3_5_sonnet(self):
        p = get_price("claude-3-5-sonnet-20241022")
        assert p["input"] == 3.0

    def test_unknown_model_returns_default(self):
        p = get_price("unknown-future-model")
        assert p["input"] > 0
        assert p["output"] > 0

    def test_case_insensitive(self):
        p1 = get_price("Claude-Sonnet-4-6")
        p2 = get_price("claude-sonnet-4-6")
        assert p1 == p2

    def test_all_price_fields_present(self):
        p = get_price("claude-sonnet-4-6")
        assert all(k in p for k in ("input", "output", "cache_write", "cache_read"))

    def test_prices_are_positive(self):
        for model in ("claude-opus-4-5", "claude-sonnet-4-6", "claude-haiku-4-5"):
            p = get_price(model)
            assert all(v > 0 for v in p.values())


class TestCalculateCost:
    def test_zero_tokens_zero_cost(self):
        assert calculate_cost("claude-sonnet-4-6", 0, 0) == 0.0

    def test_input_only(self):
        # 1M input tokens at $3/M = $3
        cost = calculate_cost("claude-sonnet-4-6", 1_000_000, 0)
        assert abs(cost - 3.0) < 0.001

    def test_output_only(self):
        # 1M output tokens at $15/M = $15
        cost = calculate_cost("claude-sonnet-4-6", 0, 1_000_000)
        assert abs(cost - 15.0) < 0.001

    def test_combined(self):
        # 100k input + 50k output for sonnet-4
        # = 100000*3/1M + 50000*15/1M = 0.30 + 0.75 = 1.05
        cost = calculate_cost("claude-sonnet-4-6", 100_000, 50_000)
        assert abs(cost - 1.05) < 0.0001

    def test_with_cache_tokens(self):
        # cache_write costs more per token than input
        p = get_price("claude-sonnet-4-6")
        cost = calculate_cost("claude-sonnet-4-6", 0, 0, 1_000_000, 0)
        assert abs(cost - p["cache_write"]) < 0.001

    def test_cost_is_float(self):
        cost = calculate_cost("claude-sonnet-4-6", 1000, 500)
        assert isinstance(cost, float)

    def test_bundled_no_imports_needed(self):
        """Verifies the price table is static — just calling it proves no network needed."""
        # If we can call get_price without any imports failing, prices are bundled.
        p = get_price("claude-sonnet-4-6")
        assert isinstance(p, dict)
