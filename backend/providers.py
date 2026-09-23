"""Custom LLM Providers Management.

Allows users to dynamically register, test, and persist custom OpenAI-compatible
LLM endpoints (both local e.g. Ollama/vLLM/LM Studio, and remote e.g. DeepSeek/Groq/OpenAI)
via the UI without modifying source code.
"""

import asyncio
import json
import os
import time
from typing import Dict, Any, List, Optional
from pathlib import Path
import httpx
from dotenv import load_dotenv

from .config import DATA_ROOT

load_dotenv(override=True)

PROVIDERS_FILE = os.path.join(DATA_ROOT, "custom_providers.json")

PROVIDER_PRESETS: Dict[str, Dict[str, Any]] = {
    "google": {
        "id": "google",
        "name": "Google AI Studio (Gemini)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "provider_type": "remote",
        "requires_key": True,
        "default_model": "gemini-3.6-flash",
        "key_hint": "Google AI Studio API Key",
    },
    "groq": {
        "id": "groq",
        "name": "Groq Cloud",
        "base_url": "https://api.groq.com/openai/v1",
        "provider_type": "remote",
        "requires_key": True,
        "default_model": "llama-3.3-70b-versatile",
        "key_hint": "Groq API Key (starts with gsk_...)",
    },
    "deepseek": {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "provider_type": "remote",
        "requires_key": True,
        "default_model": "deepseek-chat",
        "key_hint": "DeepSeek API Key (starts with sk-...)",
    },
    "openai": {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "provider_type": "remote",
        "requires_key": True,
        "default_model": "gpt-4o-mini",
        "key_hint": "OpenAI API Key (starts with sk-...)",
    },
    "openrouter": {
        "id": "openrouter",
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "provider_type": "remote",
        "requires_key": True,
        "default_model": "openrouter/auto",
        "key_hint": "OpenRouter API Key (starts with sk-or-...)",
    },
    "ollama": {
        "id": "ollama",
        "name": "Ollama (Local)",
        "base_url": "http://host.docker.internal:11434/v1",
        "provider_type": "local",
        "requires_key": False,
        "default_model": "llama3.3:latest",
        "key_hint": "Usually not needed for local Ollama",
    },
    "lmstudio": {
        "id": "lmstudio",
        "name": "LM Studio / vLLM (Local)",
        "base_url": "http://host.docker.internal:1234/v1",
        "provider_type": "local",
        "requires_key": False,
        "default_model": "default",
        "key_hint": "Usually not needed for local server",
    },
    "custom": {
        "id": "custom",
        "name": "Custom OpenAI Endpoint",
        "base_url": "",
        "provider_type": "remote",
        "requires_key": False,
        "default_model": "",
        "key_hint": "Enter custom base URL and API key",
    },
}


def _ensure_data_dir() -> None:
    Path(PROVIDERS_FILE).parent.mkdir(parents=True, exist_ok=True)


def _mask_key(key: Optional[str]) -> str:
    if not key or key == "not-needed":
        return ""
    if len(key) <= 8:
        return "••••"
    return f"{key[:4]}••••{key[-4:]}"


def get_system_providers() -> List[Dict[str, Any]]:
    """Retrieve endpoints declared via .env and backend/config.py."""
    system_list = []

    # 1. Local vLLM / Qwen Endpoint
    qwen_base = os.getenv("QWEN_BASE_URL", "http://host.docker.internal:8002/v1").rstrip("/")
    qwen_model = os.getenv("QWEN_MODEL_ID", "/models/qwen3.6-27b")
    qwen_key = os.getenv("QWEN_API_KEY", "not-needed")
    system_list.append({
        "id": "local/qwen3.6-27b",
        "name": "Qwen 3.6 (27B) Local vLLM",
        "provider_type": "local",
        "base_url": qwen_base,
        "model_id": qwen_model,
        "api_key": qwen_key if qwen_key != "not-needed" else "",
        "api_key_masked": _mask_key(qwen_key),
        "api_key_set": bool(qwen_key and qwen_key != "not-needed"),
        "is_system": True,
        "source": ".env (QWEN_BASE_URL)",
    })

    # 2. Claude Code Headless Shim
    claude_base = os.getenv("CLAUDE_SHIM_BASE_URL", "http://host.docker.internal:8600/v1").rstrip("/")
    claude_secret = os.getenv("CLAUDE_SHIM_SECRET", "not-needed")
    system_list.append({
        "id": "local/claude-code",
        "name": "Claude Code Headless Shim",
        "provider_type": "local",
        "base_url": claude_base,
        "model_id": "claude-code",
        "api_key": claude_secret if claude_secret != "not-needed" else "",
        "api_key_masked": _mask_key(claude_secret),
        "api_key_set": bool(claude_secret and claude_secret != "not-needed"),
        "is_system": True,
        "source": ".env (CLAUDE_SHIM_BASE_URL)",
    })

    # 3. Antigravity Headless Shim
    agy_base = os.getenv("ANTIGRAVITY_SHIM_BASE_URL", "http://host.docker.internal:8601/v1").rstrip("/")
    agy_secret = os.getenv("ANTIGRAVITY_SHIM_SECRET", "not-needed")
    system_list.append({
        "id": "local/antigravity",
        "name": "Antigravity Headless Shim",
        "provider_type": "local",
        "base_url": agy_base,
        "model_id": "antigravity",
        "api_key": agy_secret if agy_secret != "not-needed" else "",
        "api_key_masked": _mask_key(agy_secret),
        "api_key_set": bool(agy_secret and agy_secret != "not-needed"),
        "is_system": True,
        "source": ".env (ANTIGRAVITY_SHIM_BASE_URL)",
    })

    # 4. OpenRouter API Gateway
    or_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    system_list.append({
        "id": "system/openrouter",
        "name": "OpenRouter Cloud API Gateway",
        "provider_type": "remote",
        "base_url": "https://openrouter.ai/api/v1",
        "model_id": "openrouter/auto",
        "api_key": or_key,
        "api_key_masked": _mask_key(or_key),
        "api_key_set": bool(or_key),
        "is_system": True,
        "source": ".env (OPENROUTER_API_KEY)",
    })

    # 5. Local Ollama Endpoint (if declared in .env)
    ollama_base = os.getenv("OLLAMA_BASE_URL", "").strip().rstrip("/")
    if ollama_base:
        if ":11434" in ollama_base and not ollama_base.endswith("/v1"):
            ollama_base += "/v1"
        ollama_model = os.getenv("OLLAMA_MODEL_ID", "llama3.3:latest")
        system_list.append({
            "id": f"local/{ollama_model}",
            "name": f"Ollama Local ({ollama_model})",
            "provider_type": "local",
            "base_url": ollama_base,
            "model_id": ollama_model,
            "api_key": "not-needed",
            "api_key_masked": "",
            "api_key_set": False,
            "is_system": True,
            "source": ".env (OLLAMA_BASE_URL)",
        })

    return system_list


def load_providers() -> List[Dict[str, Any]]:
    """Load list of custom registered providers."""
    if not os.path.exists(PROVIDERS_FILE):
        return []
    try:
        with open(PROVIDERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[Providers] Error loading {PROVIDERS_FILE}: {e}")
        return []


def save_providers(providers: List[Dict[str, Any]]) -> bool:
    """Persist list of custom providers."""
    _ensure_data_dir()
    try:
        with open(PROVIDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(providers, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[Providers] Error saving {PROVIDERS_FILE}: {e}")
        return False


def get_provider_by_id(provider_id: str) -> Optional[Dict[str, Any]]:
    """Lookup provider by its unique identifier (e.g. 'local/llama3.3:latest' or 'custom/gemini-3-6-flash')."""
    providers = load_providers()
    # 1. Exact ID match
    for p in providers:
        if p.get("id") == provider_id:
            return p
    # 2. Secondary match: match by model_id or with/without local/ or custom/ prefix
    clean_target = provider_id.removeprefix("local/").removeprefix("custom/")
    for p in providers:
        p_id_clean = p.get("id", "").removeprefix("local/").removeprefix("custom/")
        p_mid_clean = p.get("model_id", "").removeprefix("local/")
        if clean_target in (p_id_clean, p_mid_clean):
            return p
    return None


def add_or_update_provider(provider_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Register or update a custom provider.
    
    Fields expected:
    - id: optional, generated if not provided (local/<model> for local, custom/<slug> for remote)
    - name: friendly label (optional if preset is provided)
    - preset: optional preset key (e.g. 'google', 'groq', 'ollama')
    - provider_type: 'local' | 'remote'
    - base_url: OpenAI-compatible base URL (optional if preset is provided)
    - model_id: target model ID on server (e.g. llama3.3:latest or gemini-3.6-flash)
    - api_key: optional bearer token
    - default_skill: optional default skill id
    """
    providers = load_providers()
    
    preset = (provider_data.get("preset") or "").strip().lower()
    preset_info = PROVIDER_PRESETS.get(preset, {})

    name = (provider_data.get("name") or "").strip()
    if not name and preset_info:
        name = preset_info.get("name", "")

    provider_type = (provider_data.get("provider_type") or "").strip().lower()
    if not provider_type:
        provider_type = preset_info.get("provider_type", "remote" if preset else "local")

    base_url = (provider_data.get("base_url") or "").strip().rstrip("/")
    if not base_url and preset_info:
        base_url = preset_info.get("base_url", "")

    model_id = (provider_data.get("model_id") or "").strip()
    if not model_id and preset_info:
        model_id = preset_info.get("default_model", "")

    api_key = (provider_data.get("api_key") or "").strip()
    default_skill = (provider_data.get("default_skill") or "").strip() or None

    # Local host and Ollama normalization
    is_local = provider_type == "local" or preset in ("ollama", "lmstudio")
    if is_local:
        # Convert localhost / 127.0.0.1 to host.docker.internal inside Docker
        base_url = (
            base_url.replace("://localhost:", "://host.docker.internal:")
            .replace("://127.0.0.1:", "://host.docker.internal:")
        )
        if ":11434" in base_url and not base_url.endswith("/v1") and not base_url.endswith("/chat/completions"):
            base_url = f"{base_url}/v1"
        if not api_key:
            api_key = "not-needed"

    if not name:
        raise ValueError("Provider Name is required.")
    if not base_url:
        raise ValueError("Base URL is required (or select a Provider Preset).")
    if not model_id:
        raise ValueError("Model ID is required.")

    # Format unique identifier:
    # Local models use the council-native 'local/<model_id>' namespace (0 cost, local badge)
    # Remote custom models use 'custom/<slug>'
    raw_id = (provider_data.get("id") or "").strip()
    if not raw_id:
        if is_local:
            clean_model = model_id.removeprefix("local/")
            raw_id = f"local/{clean_model}"
        else:
            slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in name.lower())
            raw_id = f"custom/{slug.strip('-')}"

    # Normalize completions URL: if not ending in /chat/completions, ensure proper base
    entry = {
        "id": raw_id,
        "name": name,
        "preset": preset or None,
        "provider_type": "local" if is_local else "remote",
        "base_url": base_url,
        "model_id": model_id,
        "api_key": api_key,
        "default_skill": default_skill,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Upsert
    existing_idx = next((i for i, p in enumerate(providers) if p.get("id") == raw_id), None)
    if existing_idx is not None:
        providers[existing_idx] = entry
    else:
        entry["created_at"] = entry["updated_at"]
        providers.append(entry)

    save_providers(providers)
    return entry


def delete_provider(provider_id: str) -> bool:
    """Remove a custom provider by ID."""
    providers = load_providers()
    new_list = [p for p in providers if p.get("id") != provider_id]
    if len(new_list) == len(providers):
        return False
    return save_providers(new_list)


async def test_provider_connection(
    base_url: Optional[str] = None,
    model_id: str = "",
    api_key: Optional[str] = None,
    preset: Optional[str] = None,
    timeout: float = 12.0
) -> Dict[str, Any]:
    """
    Test connectivity to an OpenAI-compatible endpoint with a minimal ping prompt.
    """
    resolved_base = (base_url or "").strip().rstrip("/")
    if not resolved_base and preset and preset in PROVIDER_PRESETS:
        resolved_base = PROVIDER_PRESETS[preset]["base_url"]

    if not resolved_base or not model_id:
        return {
            "success": False,
            "error": "Base URL (or Preset) and Model ID are required to test connection.",
        }

    endpoint = resolved_base if resolved_base.endswith("/chat/completions") else f"{resolved_base}/chat/completions"
    
    headers = {"Content-Type": "application/json"}
    if api_key and api_key.strip() and api_key.strip() != "not-needed":
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    payload = {
        "model": model_id,
        "messages": [
            {"role": "user", "content": "Respond with the word 'OK' only."}
        ],
        "max_tokens": 8,
        "temperature": 0.1,
    }

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            elapsed_ms = int((time.time() - start) * 1000)

            if resp.status_code == 200:
                data = resp.json()
                reply = ""
                if "choices" in data and len(data["choices"]) > 0:
                    reply = data["choices"][0].get("message", {}).get("content", "").strip()
                return {
                    "success": True,
                    "status_code": resp.status_code,
                    "latency_ms": elapsed_ms,
                    "reply": reply or "OK",
                    "message": f"Successfully connected to {model_id} ({elapsed_ms}ms)",
                }
            else:
                err_body = resp.text[:300]
                try:
                    j = resp.json()
                    if "error" in j:
                        err_body = j["error"].get("message", err_body) if isinstance(j["error"], dict) else str(j["error"])
                except Exception:
                    pass
                return {
                    "success": False,
                    "status_code": resp.status_code,
                    "latency_ms": elapsed_ms,
                    "error": f"HTTP {resp.status_code}: {err_body}",
                }
    except httpx.ConnectError:
        return {
            "success": False,
            "error": f"Connection refused to {endpoint}. If running inside Docker, use 'http://host.docker.internal:<port>' to reach host services.",
        }
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": f"Connection timed out after {timeout}s at {endpoint}.",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error testing connection: {str(e)}",
        }


async def fetch_models_from_endpoint(
    base_url: Optional[str] = None,
    preset: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """
    Fetch available models list from an OpenAI-compatible /models endpoint.
    Supports OpenAI, Google AI Studio OpenAI shim, Groq, DeepSeek, Ollama, etc.
    """
    resolved_base = (base_url or "").strip().rstrip("/")
    if not resolved_base and preset and preset in PROVIDER_PRESETS:
        resolved_base = PROVIDER_PRESETS[preset]["base_url"]

    if not resolved_base:
        return {
            "success": False,
            "error": "Base URL or a valid Provider Preset is required to fetch models.",
            "models": [],
        }

    # Normalize endpoint: ensure we target /models
    if resolved_base.endswith("/chat/completions"):
        models_url = resolved_base[:-len("/chat/completions")] + "/models"
    elif resolved_base.endswith("/models"):
        models_url = resolved_base
    else:
        models_url = f"{resolved_base}/models"

    headers = {"Accept": "application/json"}
    if api_key and api_key.strip() and api_key.strip() != "not-needed":
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(models_url, headers=headers)
            elapsed_ms = int((time.time() - start) * 1000)

            if resp.status_code != 200:
                # Try secondary fallback for Ollama: /api/tags if /v1/models returned 404
                if "11434" in resolved_base or preset == "ollama":
                    try:
                        base_root = resolved_base.split("/v1")[0]
                        alt_url = f"{base_root}/api/tags"
                        alt_resp = await client.get(alt_url, headers=headers)
                        if alt_resp.status_code == 200:
                            alt_data = alt_resp.json()
                            raw_models = [m.get("name") for m in alt_data.get("models", []) if m.get("name")]
                            return {
                                "success": True,
                                "models": sorted(list(set(raw_models))),
                                "count": len(raw_models),
                                "latency_ms": elapsed_ms,
                            }
                    except Exception:
                        pass

                err_text = resp.text[:250]
                try:
                    err_json = resp.json()
                    if "error" in err_json:
                        err_text = err_json["error"].get("message", err_text) if isinstance(err_json["error"], dict) else str(err_json["error"])
                except Exception:
                    pass
                return {
                    "success": False,
                    "status_code": resp.status_code,
                    "error": f"HTTP {resp.status_code}: {err_text}",
                    "models": [],
                }

            data = resp.json()
            raw_models: List[str] = []

            # 1. Standard OpenAI format: {"data": [{"id": "model_name"}, ...]}
            if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                for item in data["data"]:
                    if isinstance(item, dict) and "id" in item:
                        raw_models.append(item["id"])
                    elif isinstance(item, str):
                        raw_models.append(item)
            # 2. Ollama / custom format: {"models": [{"name": "..."}, ...]}
            elif isinstance(data, dict) and "models" in data and isinstance(data["models"], list):
                for item in data["models"]:
                    if isinstance(item, dict):
                        name = item.get("name") or item.get("id") or item.get("model")
                        if name:
                            raw_models.append(name)
                    elif isinstance(item, str):
                        raw_models.append(item)
            # 3. Direct array format: ["model-1", "model-2"]
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, str):
                        raw_models.append(item)
                    elif isinstance(item, dict) and "id" in item:
                        raw_models.append(item["id"])

            cleaned: List[str] = []
            seen = set()
            for m in raw_models:
                m_str = str(m).strip()
                if not m_str:
                    continue
                # For Google AI Studio: normalize "models/gemini-3.6-flash" to "gemini-3.6-flash"
                display_id = m_str[7:] if m_str.startswith("models/") else m_str
                if display_id not in seen:
                    seen.add(display_id)
                    cleaned.append(display_id)

            # Sort intelligently: put prominent chat models first, filter preview noise down
            def _rank(name: str) -> int:
                n = name.lower()
                if any(x in n for x in ("embed", "tts", "audio", "veo", "clip", "transcribe", "robotics", "image")):
                    return 100
                if "gemini-3.6" in n:
                    return 1
                if "gemini-3.7" in n or "gemini-3.5" in n:
                    return 2
                if "gemini-2.5-pro" in n or "gemini-2.5-flash" in n:
                    return 3
                if "gemini" in n or "gpt-4" in n or "claude" in n or "deepseek" in n or "llama" in n:
                    return 10
                return 50

            cleaned.sort(key=lambda x: (_rank(x), x))

            return {
                "success": True,
                "models": cleaned,
                "count": len(cleaned),
                "latency_ms": elapsed_ms,
            }
    except httpx.ConnectError:
        return {
            "success": False,
            "error": f"Connection refused to {models_url}. If running inside Docker, use 'http://host.docker.internal:<port>' to reach host services.",
            "models": [],
        }
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": f"Connection timed out after {timeout}s fetching models.",
            "models": [],
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error fetching models: {str(e)}",
            "models": [],
        }


async def ping_provider(provider_id: str, timeout: float = 3.5) -> Dict[str, Any]:
    """
    Ping a provider endpoint by ID (either system or custom) to check live connectivity.
    Returns status: 'online' | 'offline', latency_ms, message or error.
    """
    target: Optional[Dict[str, Any]] = None
    for sp in get_system_providers():
        if sp["id"] == provider_id:
            target = sp
            break

    if target is None:
        target = get_provider_by_id(provider_id)

    if target is None:
        return {
            "id": provider_id,
            "status": "offline",
            "online": False,
            "error": f"Provider '{provider_id}' not found",
            "latency_ms": 0,
        }

    # Special handling for OpenRouter gateway
    if target.get("id") == "system/openrouter":
        api_key = target.get("api_key") or os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            return {
                "id": provider_id,
                "status": "offline",
                "online": False,
                "error": "OPENROUTER_API_KEY is not configured in .env",
                "latency_ms": 0,
            }
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(
                    "https://openrouter.ai/api/v1/auth/key",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                latency = int((time.time() - start) * 1000)
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    label = data.get("label", "valid")
                    return {
                        "id": provider_id,
                        "status": "online",
                        "online": True,
                        "latency_ms": latency,
                        "message": f"Connected ({label}, {latency}ms)",
                    }
                else:
                    return {
                        "id": provider_id,
                        "status": "offline",
                        "online": False,
                        "latency_ms": latency,
                        "error": f"HTTP {resp.status_code}: {resp.text[:100]}",
                    }
        except Exception as e:
            return {
                "id": provider_id,
                "status": "offline",
                "online": False,
                "latency_ms": int((time.time() - start) * 1000),
                "error": str(e),
            }

    # General OpenAI-compatible endpoint
    base_url = target.get("base_url", "").rstrip("/")
    if base_url.endswith("/chat/completions"):
        models_url = base_url[:-len("/chat/completions")] + "/models"
    else:
        models_url = f"{base_url}/models"

    api_key = target.get("api_key", "").strip()
    headers = {}
    if api_key and api_key != "not-needed":
        headers["Authorization"] = f"Bearer {api_key}"

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # 1. Fast probe: GET /models
            try:
                resp = await client.get(models_url, headers=headers)
                latency = int((time.time() - start) * 1000)
                if resp.status_code == 200:
                    return {
                        "id": provider_id,
                        "status": "online",
                        "online": True,
                        "latency_ms": latency,
                        "message": f"Online ({latency}ms)",
                    }
            except Exception:
                pass

            # 2. Secondary probe: minimal chat completion ping if /models is unsupported
            completions_url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
            model_id = target.get("model_id") or "default"
            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            }
            resp = await client.post(completions_url, json=payload, headers=headers)
            latency = int((time.time() - start) * 1000)
            if resp.status_code in (200, 400):
                return {
                    "id": provider_id,
                    "status": "online",
                    "online": True,
                    "latency_ms": latency,
                    "message": f"Online ({latency}ms)",
                }
            else:
                return {
                    "id": provider_id,
                    "status": "offline",
                    "online": False,
                    "latency_ms": latency,
                    "error": f"HTTP {resp.status_code}",
                }
    except httpx.ConnectError:
        return {
            "id": provider_id,
            "status": "offline",
            "online": False,
            "latency_ms": int((time.time() - start) * 1000),
            "error": "Connection refused (offline)",
        }
    except httpx.TimeoutException:
        return {
            "id": provider_id,
            "status": "offline",
            "online": False,
            "latency_ms": int((time.time() - start) * 1000),
            "error": "Connection timed out",
        }
    except Exception as e:
        return {
            "id": provider_id,
            "status": "offline",
            "online": False,
            "latency_ms": int((time.time() - start) * 1000),
            "error": str(e),
        }


async def ping_all_providers(timeout: float = 3.5) -> Dict[str, Any]:
    """Ping all system and custom providers concurrently."""
    system_providers = get_system_providers()
    custom_providers = load_providers()
    all_ids = [p["id"] for p in system_providers] + [p["id"] for p in custom_providers]

    tasks = [ping_provider(pid, timeout=timeout) for pid in all_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    status_map = {}
    for pid, res in zip(all_ids, results):
        if isinstance(res, Exception):
            status_map[pid] = {
                "id": pid,
                "status": "offline",
                "online": False,
                "error": str(res),
                "latency_ms": 0,
            }
        else:
            status_map[pid] = res

    return status_map

