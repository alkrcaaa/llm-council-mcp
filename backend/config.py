"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Council members - list of OpenRouter model identifiers
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Local OpenAI-compatible model endpoints (e.g. self-hosted vLLM).
# Any model identifier that matches a key here is routed to that endpoint
# instead of OpenRouter. "model_id" is the id the server itself expects
# (which may differ from the council-facing identifier below).
LOCAL_MODELS = {
    "local/qwen3.6-27b": {
        "base_url": os.getenv("QWEN_BASE_URL", "http://host.docker.internal:8002/v1").rstrip("/") + "/chat/completions",
        "model_id": os.getenv("QWEN_MODEL_ID", "/models/qwen3.6-27b"),
        "api_key": os.getenv("QWEN_API_KEY", "not-needed"),
    },
    # Headless `claude -p --restricted` shim (infra/local-models/claude_code_shim.py),
    # runs on the host - not free like Qwen, each call spends real API credit.
    "local/claude-code": {
        "base_url": os.getenv("CLAUDE_SHIM_BASE_URL", "http://host.docker.internal:8600/v1").rstrip("/") + "/chat/completions",
        "model_id": "claude-code",
        "api_key": os.getenv("CLAUDE_SHIM_SECRET", "not-needed"),
    },
    # Headless `agy --sandbox --print` shim (infra/local-models/antigravity_shim.py),
    # runs on the host - not free, each call spends real API credit.
    "local/antigravity": {
        "base_url": os.getenv("ANTIGRAVITY_SHIM_BASE_URL", "http://host.docker.internal:8601/v1").rstrip("/") + "/chat/completions",
        "model_id": "antigravity",
        "api_key": os.getenv("ANTIGRAVITY_SHIM_SECRET", "not-needed"),
    },
}

# Data directory for conversation storage
DATA_DIR = "data/conversations"
