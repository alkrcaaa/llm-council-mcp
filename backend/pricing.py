"""Model pricing data and cost calculation utilities.

Pricing data is sourced from OpenRouter's pricing page.
Prices are in USD per 1 million tokens.

Note: Prices may change over time. Update this file periodically
or consider fetching from OpenRouter's API for real-time pricing.
"""

from typing import Dict, Any

# Pricing per 1M tokens (input/output) - Updated November 2024
# Format: "provider/model": {"input": price_per_1M, "output": price_per_1M}
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # OpenAI Models
    "openai/gpt-5.1": {"input": 2.50, "output": 10.00},
    "openai/gpt-4.1": {"input": 2.00, "output": 8.00},
    "openai/gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "openai/gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "openai/gpt-4o": {"input": 2.50, "output": 10.00},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "openai/gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "openai/o1": {"input": 15.00, "output": 60.00},
    "openai/o1-mini": {"input": 3.00, "output": 12.00},
    "openai/o1-preview": {"input": 15.00, "output": 60.00},
    "openai/o3": {"input": 20.00, "output": 80.00},
    "openai/o4-mini": {"input": 1.10, "output": 4.40},

    # Anthropic Models
    "anthropic/claude-sonnet-4.5": {"input": 3.00, "output": 15.00},
    "anthropic/claude-opus-4.5": {"input": 15.00, "output": 75.00},
    "anthropic/claude-haiku-3.5": {"input": 0.80, "output": 4.00},
    "anthropic/claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
    "anthropic/claude-3-opus": {"input": 15.00, "output": 75.00},
    "anthropic/claude-3-sonnet": {"input": 3.00, "output": 15.00},
    "anthropic/claude-3-haiku": {"input": 0.25, "output": 1.25},

    # Google Models
    "google/gemini-3-pro-preview": {"input": 1.25, "output": 5.00},
    "google/gemini-2.5-pro": {"input": 1.25, "output": 5.00},
    "google/gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "google/gemini-pro": {"input": 0.50, "output": 1.50},
    "google/gemini-pro-1.5": {"input": 1.25, "output": 5.00},
    "google/gemini-flash-1.5": {"input": 0.075, "output": 0.30},

    # xAI Models
    "x-ai/grok-4": {"input": 3.00, "output": 15.00},
    "x-ai/grok-3": {"input": 3.00, "output": 15.00},
    "x-ai/grok-2": {"input": 2.00, "output": 10.00},
    "x-ai/grok-beta": {"input": 5.00, "output": 15.00},

    # Meta Models
    "meta-llama/llama-4-maverick": {"input": 0.20, "output": 0.60},
    "meta-llama/llama-4-scout": {"input": 0.10, "output": 0.30},
    "meta-llama/llama-3.1-405b-instruct": {"input": 2.70, "output": 2.70},
    "meta-llama/llama-3.1-70b-instruct": {"input": 0.52, "output": 0.75},
    "meta-llama/llama-3.1-8b-instruct": {"input": 0.055, "output": 0.055},

    # DeepSeek Models
    "deepseek/deepseek-r1": {"input": 0.55, "output": 2.19},
    "deepseek/deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek/deepseek-coder": {"input": 0.14, "output": 0.28},

    # Mistral Models
    "mistralai/mistral-large": {"input": 2.00, "output": 6.00},
    "mistralai/mistral-medium": {"input": 2.70, "output": 8.10},
    "mistralai/mistral-small": {"input": 0.20, "output": 0.60},
    "mistralai/mixtral-8x7b-instruct": {"input": 0.24, "output": 0.24},

    # Cohere Models
    "cohere/command-r-plus": {"input": 2.50, "output": 10.00},
    "cohere/command-r": {"input": 0.15, "output": 0.60},

    # Local / self-hosted models
    "local/qwen3.6-27b": {"input": 0.0, "output": 0.0},  # self-hosted GPU, no per-token API cost
    "local/claude-code": {"input": 3.00, "output": 15.00},  # real API cost via claude-code-shim; approximated as Sonnet pricing
    "local/antigravity": {"input": 1.25, "output": 5.00},  # real API cost via antigravity-shim; approximated as Gemini 3 Pro pricing
}

# Default pricing for unknown models (conservative estimate)
DEFAULT_PRICING = {"input": 5.00, "output": 15.00}


def get_model_pricing(model: str) -> Dict[str, float]:
    """
    Get pricing for a specific model.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o" or "local/qwen3.6-27b@owasp-security")

    Returns:
        Dict with 'input' and 'output' prices per 1M tokens
    """
    base_model = model.split("@")[0] if "@" in model else model
    return MODEL_PRICING.get(base_model, DEFAULT_PRICING)


def calculate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int
) -> Dict[str, Any]:
    """
    Calculate the cost for a model query.

    Args:
        model: OpenRouter model identifier
        prompt_tokens: Number of input/prompt tokens
        completion_tokens: Number of output/completion tokens

    Returns:
        Dict with cost breakdown:
        - input_cost: Cost for prompt tokens (USD)
        - output_cost: Cost for completion tokens (USD)
        - total_cost: Total cost (USD)
        - prompt_tokens: Input token count
        - completion_tokens: Output token count
        - total_tokens: Total token count
        - pricing: The pricing rates used
    """
    pricing = get_model_pricing(model)

    # Convert from per-1M-tokens to actual cost
    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]
    total_cost = input_cost + output_cost

    return {
        "input_cost": round(input_cost, 6),
        "output_cost": round(output_cost, 6),
        "total_cost": round(total_cost, 6),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "pricing": pricing,
    }


def format_cost(cost: float) -> str:
    """
    Format a cost value for display.

    Args:
        cost: Cost in USD

    Returns:
        Formatted string (e.g., "$0.0012" or "<$0.0001")
    """
    if cost < 0.0001:
        return "<$0.0001"
    elif cost < 0.01:
        return f"${cost:.4f}"
    elif cost < 1.00:
        return f"${cost:.3f}"
    else:
        return f"${cost:.2f}"


def aggregate_costs(cost_list: list) -> Dict[str, Any]:
    """
    Aggregate multiple cost entries into a summary.

    Args:
        cost_list: List of cost dicts from calculate_cost()

    Returns:
        Aggregated cost summary
    """
    if not cost_list:
        return {
            "total_input_cost": 0,
            "total_output_cost": 0,
            "total_cost": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "model_count": 0,
        }

    total_input = sum(c.get("input_cost", 0) for c in cost_list)
    total_output = sum(c.get("output_cost", 0) for c in cost_list)
    total_prompt = sum(c.get("prompt_tokens", 0) for c in cost_list)
    total_completion = sum(c.get("completion_tokens", 0) for c in cost_list)

    return {
        "total_input_cost": round(total_input, 6),
        "total_output_cost": round(total_output, 6),
        "total_cost": round(total_input + total_output, 6),
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_tokens": total_prompt + total_completion,
        "model_count": len(cost_list),
    }
