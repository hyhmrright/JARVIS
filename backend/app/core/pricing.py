"""Static LLM pricing table for cost estimation.

Prices are USD per 1 million tokens: (input_price, output_price).
Update this dict as provider pricing changes.
"""

PRICING: dict[str, dict[str, tuple[float, float]]] = {
    "deepseek": {
        "deepseek-chat": (0.27, 1.10),
        "deepseek-reasoner": (0.55, 2.19),
    },
    "openai": {
        "gpt-4o": (2.50, 10.00),
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4-turbo": (10.00, 30.00),
        "o1": (15.00, 60.00),
        "o1-mini": (1.10, 4.40),
    },
    "anthropic": {
        "claude-opus-4-5": (15.00, 75.00),
        "claude-sonnet-4-6": (3.00, 15.00),
        "claude-haiku-4-5-20251001": (0.80, 4.00),
        "claude-3-5-haiku-20241022": (0.80, 4.00),
        "claude-3-5-sonnet-20241022": (3.00, 15.00),
    },
    "zhipuai": {
        "glm-4": (0.10, 0.10),
        "glm-4-flash": (0.00, 0.00),
        "glm-4-plus": (0.14, 0.14),
        "glm-4.5": (0.14, 0.14),
    },
    "ollama": {},  # local inference = free
}


def estimate_cost(provider: str, model: str, tokens_in: int, tokens_out: int) -> float:
    """Return estimated USD cost. Returns 0.0 for unknown provider/model."""
    prices = PRICING.get(provider, {}).get(model)
    if not prices:
        return 0.0
    in_price, out_price = prices
    return (tokens_in * in_price + tokens_out * out_price) / 1_000_000
