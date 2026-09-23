"""Agent and model visual profile management (display names, avatar pictures, and theme colors).

Stores persistent customizations in data/agent_profiles.json.
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path
from .config import DATA_DIR

PROFILES_FILE = os.path.join(DATA_DIR, "agent_profiles.json")

# Sensible default profiles for all standard local and custom models
DEFAULT_PROFILES: Dict[str, Dict[str, Any]] = {
    "local/antigravity": {
        "display_name": "Antigravity",
        "color": "#6366f1",
        "avatar_url": "",
    },
    "local/claude-code": {
        "display_name": "Claude Code",
        "color": "#d97706",
        "avatar_url": "",
    },
    "local/qwen3.6-27b": {
        "display_name": "Qwen 27B",
        "color": "#10b981",
        "avatar_url": "",
    },
    "custom/gemini-3-6-flash": {
        "display_name": "Gemini 3.6 Flash",
        "color": "#3b82f6",
        "avatar_url": "",
    },
    "custom/groq": {
        "display_name": "Groq Llama 3.3",
        "color": "#f97316",
        "avatar_url": "",
    },
    "openai/gpt-4o": {
        "display_name": "GPT-4o",
        "color": "#10a37f",
        "avatar_url": "",
    },
    "deepseek/deepseek-chat": {
        "display_name": "DeepSeek",
        "color": "#0ea5e9",
        "avatar_url": "",
    },
}


def _ensure_data_dir() -> None:
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def load_agent_profiles() -> Dict[str, Dict[str, Any]]:
    """Load agent visual profiles from disk, merged with defaults."""
    _ensure_data_dir()
    profiles = {k: dict(v) for k, v in DEFAULT_PROFILES.items()}

    if os.path.exists(PROFILES_FILE):
        try:
            with open(PROFILES_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    for model_id, prof in saved.items():
                        if isinstance(prof, dict):
                            current = profiles.get(model_id, {})
                            current.update(prof)
                            profiles[model_id] = current
        except Exception:
            pass

    return profiles


def save_agent_profiles(profiles: Dict[str, Dict[str, Any]]) -> None:
    """Save agent visual profiles to disk."""
    _ensure_data_dir()
    with open(PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)


def update_agent_profile(
    model_id: str,
    display_name: Optional[str] = None,
    color: Optional[str] = None,
    avatar_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Create or update a visual profile for a specific model."""
    clean_model_id = model_id.split("@")[0].strip()
    profiles = load_agent_profiles()

    profile = profiles.get(clean_model_id, {
        "display_name": clean_model_id.split("/")[-1],
        "color": "#8b5cf6",
        "avatar_url": "",
    })

    if display_name is not None:
        profile["display_name"] = display_name.strip() or clean_model_id.split("/")[-1]
    if color is not None:
        profile["color"] = color.strip() or "#8b5cf6"
    if avatar_url is not None:
        profile["avatar_url"] = avatar_url.strip()

    profiles[clean_model_id] = profile
    save_agent_profiles(profiles)
    return profile
