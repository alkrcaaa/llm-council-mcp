"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv(override=True)

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Council members - list of model identifiers
COUNCIL_MODELS = [
    "local/antigravity@red-team-reasoning",
    "custom/gemini-3-6-flash@red-team-reasoning",
    "local/qwen3.6-27b@first-principles",
    "custom/groq@deep-research",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "local/claude-code"


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

# Optional Local Ollama from .env
_ollama_base = os.getenv("OLLAMA_BASE_URL", "").strip().rstrip("/")
if _ollama_base:
    if ":11434" in _ollama_base and not _ollama_base.endswith("/v1"):
        _ollama_base += "/v1"
    _ollama_model = os.getenv("OLLAMA_MODEL_ID", "llama3.3:latest")
    LOCAL_MODELS[f"local/{_ollama_model}"] = {
        "base_url": f"{_ollama_base}/chat/completions",
        "model_id": _ollama_model,
        "api_key": "not-needed",
    }

# Root for all persisted state (conversations, config, analytics, cache, auth).
# Same env var auth.py reads, so one override relocates everything.
DATA_ROOT = os.getenv("DATA_DIR", "data")

# Data directory for conversation storage
DATA_DIR = os.path.join(DATA_ROOT, "conversations")
