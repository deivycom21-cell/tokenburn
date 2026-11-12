"""Bundled price table — no network calls, ever.

Prices in USD per million tokens based on Anthropic published pricing.
Last updated: 2024-11. Approximate; use API docs for billing questions.
"""

# (prefix_in_model_id, input, output, cache_write, cache_read)
_PRICE_TABLE: list[tuple[str, float, float, float, float]] = [
    ("claude-opus-4",    15.00, 75.00, 18.750, 1.875),
    ("claude-3-opus",    15.00, 75.00, 18.750, 1.875),
    ("claude-sonnet-4",   3.00, 15.00,  3.750, 0.300),
    ("claude-3-6-sonnet", 3.00, 15.00,  3.750, 0.300),
    ("claude-3-5-sonnet", 3.00, 15.00,  3.750, 0.300),
    ("claude-3-sonnet",   3.00, 15.00,  3.750, 0.300),
    ("claude-haiku-4",    0.80,  4.00,  1.000, 0.080),
    ("claude-3-5-haiku",  0.80,  4.00,  1.000, 0.080),
    ("claude-3-haiku",    0.25,  1.25,  0.300, 0.030),
]

_DEFAULT: tuple[float, float, float, float] = (3.00, 15.00, 3.750, 0.300)


def get_price(model: str) -> dict[str, float]:
    """Return USD-per-million-token rates for a model (bundled, no network)."""
    ml = model.lower()
    for prefix, inp, out, cw, cr in _PRICE_TABLE:
        if prefix in ml:
            return {"input": inp, "output": out, "cache_write": cw, "cache_read": cr}
    inp, out, cw, cr = _DEFAULT
    return {"input": inp, "output": out, "cache_write": cw, "cache_read": cr}


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """Return API-equivalent cost in USD for the given token counts."""
    p = get_price(model)
    M = 1_000_000
    return (
        input_tokens * p["input"] / M
        + output_tokens * p["output"] / M
        + cache_write_tokens * p["cache_write"] / M
        + cache_read_tokens * p["cache_read"] / M
    )
