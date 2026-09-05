"""Dynamic configuration management for LLM Council.

This module handles loading, saving, and validating model configuration.
Configuration is stored in a JSON file and can be modified via API endpoints.
"""

import json
import os
from typing import Dict, Any, List, Optional
from pathlib import Path

# Configuration file path (relative to project root)
CONFIG_FILE = "data/council_config.json"

# Default configuration (used when no config file exists)
DEFAULT_CONFIG = {
    "council_models": [
        "openai/gpt-5.1",
        "google/gemini-3-pro-preview",
        "anthropic/claude-sonnet-4.5",
        "x-ai/grok-4",
        "local/qwen3.6-27b",
    ],
    "chairman_model": "google/gemini-3-pro-preview",
    "multi_chairman_models": [
        "google/gemini-2.5-flash",
        "anthropic/claude-sonnet-4.5",
        "openai/gpt-4.1",
    ],
    # Model pools for dynamic routing (optimized for each question type)
    "routing_pools": {
        "coding": [
            "anthropic/claude-sonnet-4.5",
            "openai/gpt-5.1",
            "deepseek/deepseek-chat",
            "openai/gpt-4.1",
        ],
        "creative": [
            "anthropic/claude-sonnet-4.5",
            "google/gemini-3-pro-preview",
            "openai/gpt-5.1",
            "x-ai/grok-4",
        ],
        "factual": [
            "google/gemini-3-pro-preview",
            "openai/gpt-5.1",
            "anthropic/claude-sonnet-4.5",
            "openai/gpt-4.1",
        ],
        "analysis": [
            "openai/gpt-5.1",
            "anthropic/claude-sonnet-4.5",
            "openai/o3",
            "google/gemini-3-pro-preview",
        ],
    },
    # Tier-based escalation configuration
    "tier1_models": [
        "google/gemini-2.5-flash",
        "openai/gpt-4.1-mini",
        "anthropic/claude-haiku-3.5",
        "deepseek/deepseek-chat",
    ],
    "tier2_models": [
        "anthropic/claude-sonnet-4.5",
        "openai/gpt-5.1",
        "google/gemini-3-pro-preview",
        "openai/o3",
    ],
    # Escalation thresholds
    "escalation_confidence_threshold": 6.0,
    "escalation_min_confidence_threshold": 4,
    "escalation_agreement_threshold": 0.5,
}

# Minimum number of council models required
MIN_COUNCIL_MODELS = 2


def _ensure_config_dir() -> None:
    """Ensure the data directory exists."""
    config_path = Path(CONFIG_FILE)
    config_path.parent.mkdir(parents=True, exist_ok=True)


def load_config() -> Dict[str, Any]:
    """
    Load configuration from the JSON file.

    If the config file doesn't exist, returns the default configuration.

    Returns:
        Dict containing:
        - council_models: List of model identifiers for the council
        - chairman_model: Model identifier for the chairman
        - multi_chairman_models: List of model identifiers for multi-chairman synthesis
        - routing_pools: Dict mapping question categories to model lists
    """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Validate and merge with defaults for any missing keys
                return {
                    "council_models": config.get("council_models", DEFAULT_CONFIG["council_models"]),
                    "chairman_model": config.get("chairman_model", DEFAULT_CONFIG["chairman_model"]),
                    "multi_chairman_models": config.get("multi_chairman_models", DEFAULT_CONFIG["multi_chairman_models"]),
                    "routing_pools": config.get("routing_pools", DEFAULT_CONFIG["routing_pools"]),
                    "tier1_models": config.get("tier1_models", DEFAULT_CONFIG["tier1_models"]),
                    "tier2_models": config.get("tier2_models", DEFAULT_CONFIG["tier2_models"]),
                    "escalation_confidence_threshold": config.get("escalation_confidence_threshold", DEFAULT_CONFIG["escalation_confidence_threshold"]),
                    "escalation_min_confidence_threshold": config.get("escalation_min_confidence_threshold", DEFAULT_CONFIG["escalation_min_confidence_threshold"]),
                    "escalation_agreement_threshold": config.get("escalation_agreement_threshold", DEFAULT_CONFIG["escalation_agreement_threshold"]),
                }
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load config file, using defaults: {e}")
            return DEFAULT_CONFIG.copy()

    return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save configuration to the JSON file.

    Args:
        config: Dict containing council_models, chairman_model, and optionally multi_chairman_models

    Returns:
        The saved configuration

    Raises:
        ValueError: If configuration is invalid
    """
    # Validate before saving
    validation_error = validate_config(config)
    if validation_error:
        raise ValueError(validation_error)

    _ensure_config_dir()

    # Extract only the fields we care about
    config_to_save = {
        "council_models": config["council_models"],
        "chairman_model": config["chairman_model"],
        "multi_chairman_models": config.get("multi_chairman_models", DEFAULT_CONFIG["multi_chairman_models"]),
        "routing_pools": config.get("routing_pools", DEFAULT_CONFIG["routing_pools"]),
        "tier1_models": config.get("tier1_models", DEFAULT_CONFIG["tier1_models"]),
        "tier2_models": config.get("tier2_models", DEFAULT_CONFIG["tier2_models"]),
        "escalation_confidence_threshold": config.get("escalation_confidence_threshold", DEFAULT_CONFIG["escalation_confidence_threshold"]),
        "escalation_min_confidence_threshold": config.get("escalation_min_confidence_threshold", DEFAULT_CONFIG["escalation_min_confidence_threshold"]),
        "escalation_agreement_threshold": config.get("escalation_agreement_threshold", DEFAULT_CONFIG["escalation_agreement_threshold"]),
    }

    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_to_save, f, indent=2)

    return config_to_save


def validate_config(config: Dict[str, Any]) -> Optional[str]:
    """
    Validate configuration.

    Args:
        config: Configuration dict to validate

    Returns:
        Error message if invalid, None if valid
    """
    # Check council_models exists and is a list
    if "council_models" not in config:
        return "council_models is required"

    if not isinstance(config["council_models"], list):
        return "council_models must be a list"

    # Check minimum number of models
    if len(config["council_models"]) < MIN_COUNCIL_MODELS:
        return f"At least {MIN_COUNCIL_MODELS} council models are required"

    # Check all models are non-empty strings
    for i, model in enumerate(config["council_models"]):
        if not isinstance(model, str) or not model.strip():
            return f"council_models[{i}] must be a non-empty string"

    # Check chairman_model exists and is a non-empty string
    if "chairman_model" not in config:
        return "chairman_model is required"

    if not isinstance(config["chairman_model"], str) or not config["chairman_model"].strip():
        return "chairman_model must be a non-empty string"

    # Validate multi_chairman_models if provided
    if "multi_chairman_models" in config:
        if not isinstance(config["multi_chairman_models"], list):
            return "multi_chairman_models must be a list"

        if len(config["multi_chairman_models"]) < MIN_COUNCIL_MODELS:
            return f"At least {MIN_COUNCIL_MODELS} multi-chairman models are required"

        for i, model in enumerate(config["multi_chairman_models"]):
            if not isinstance(model, str) or not model.strip():
                return f"multi_chairman_models[{i}] must be a non-empty string"

    return None


def get_council_models() -> List[str]:
    """
    Get the current list of council models.

    Returns:
        List of model identifiers
    """
    config = load_config()
    return config["council_models"]


def get_chairman_model() -> str:
    """
    Get the current chairman model.

    Returns:
        Model identifier string
    """
    config = load_config()
    return config["chairman_model"]


def get_multi_chairman_models() -> List[str]:
    """
    Get the current list of multi-chairman models for ensemble synthesis.

    Returns:
        List of model identifiers for multi-chairman synthesis
    """
    config = load_config()
    return config.get("multi_chairman_models", DEFAULT_CONFIG["multi_chairman_models"])


def get_routing_pools() -> Dict[str, List[str]]:
    """
    Get the current routing pools for dynamic model routing.

    Returns:
        Dict mapping question category names to lists of model identifiers
    """
    config = load_config()
    return config.get("routing_pools", DEFAULT_CONFIG["routing_pools"])


def get_tier1_models() -> List[str]:
    """
    Get the current list of Tier 1 (fast/cheap) models for escalation.

    Returns:
        List of model identifiers for Tier 1
    """
    config = load_config()
    return config.get("tier1_models", DEFAULT_CONFIG["tier1_models"])


def get_tier2_models() -> List[str]:
    """
    Get the current list of Tier 2 (premium/expensive) models for escalation.

    Returns:
        List of model identifiers for Tier 2
    """
    config = load_config()
    return config.get("tier2_models", DEFAULT_CONFIG["tier2_models"])


def get_escalation_thresholds() -> Dict[str, float]:
    """
    Get the current escalation thresholds.

    Returns:
        Dict with:
        - confidence_threshold: Minimum avg confidence before escalation
        - min_confidence_threshold: Minimum any-model confidence before escalation
        - agreement_threshold: Minimum agreement ratio before escalation
    """
    config = load_config()
    return {
        "confidence_threshold": config.get("escalation_confidence_threshold", DEFAULT_CONFIG["escalation_confidence_threshold"]),
        "min_confidence_threshold": config.get("escalation_min_confidence_threshold", DEFAULT_CONFIG["escalation_min_confidence_threshold"]),
        "agreement_threshold": config.get("escalation_agreement_threshold", DEFAULT_CONFIG["escalation_agreement_threshold"]),
    }


def reset_to_defaults() -> Dict[str, Any]:
    """
    Reset configuration to defaults.

    Returns:
        The default configuration
    """
    return save_config(DEFAULT_CONFIG.copy())


# List of popular models for the frontend dropdown suggestions
AVAILABLE_MODELS = [
    # OpenAI
    "openai/gpt-5.1",
    "openai/gpt-4.1",
    "openai/gpt-4.1-mini",
    "openai/gpt-4.1-nano",
    "openai/o3",
    "openai/o4-mini",
    # Anthropic
    "anthropic/claude-sonnet-4.5",
    "anthropic/claude-opus-4.5",
    "anthropic/claude-haiku-3.5",
    # Google
    "google/gemini-3-pro-preview",
    "google/gemini-2.5-flash",
    "google/gemini-2.5-pro",
    # xAI
    "x-ai/grok-4",
    "x-ai/grok-3",
    # Meta
    "meta-llama/llama-4-maverick",
    "meta-llama/llama-4-scout",
    # DeepSeek
    "deepseek/deepseek-r1",
    "deepseek/deepseek-chat",
    # Mistral
    "mistralai/mistral-large",
    "mistralai/mistral-medium",
    # Local / self-hosted (routed outside OpenRouter, see backend/config.py LOCAL_MODELS)
    "local/qwen3.6-27b",
    "local/claude-code",  # costs real API credit per call - not in the default council, add manually
    "local/antigravity",  # costs real API credit per call - not in the default council, add manually
]
