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

load_dotenv(override=True)

PROVIDERS_FILE = "data/custom_providers.json"


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
    """Lookup provider by its unique identifier (e.g. 'custom/my-ollama')."""
    providers = load_providers()
    for p in providers:
        if p.get("id") == provider_id:
            return p
    return None


def add_or_update_provider(provider_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Register or update a custom provider.
    
    Fields expected:
    - id: optional, generated if not provided
    - name: friendly label
    - provider_type: 'local' | 'remote'
    - base_url: OpenAI-compatible base URL (e.g. http://host.docker.internal:11434/v1)
    - model_id: target model ID on server (e.g. llama3.3:70b)
    - api_key: optional bearer token
    - default_skill: optional default skill id
    """
    providers = load_providers()
    
    name = (provider_data.get("name") or "").strip()
    provider_type = (provider_data.get("provider_type") or "local").strip().lower()
    base_url = (provider_data.get("base_url") or "").strip().rstrip("/")
    model_id = (provider_data.get("model_id") or "").strip()
    api_key = (provider_data.get("api_key") or "").strip()
    default_skill = (provider_data.get("default_skill") or "").strip() or None

    if not name or not base_url or not model_id:
        raise ValueError("Name, Base URL, and Model ID are required.")

    # Format unique identifier: e.g. custom/<slug>
    raw_id = (provider_data.get("id") or "").strip()
    if not raw_id:
        slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in name.lower())
        raw_id = f"custom/{slug.strip('-')}"

    # Normalize completions URL: if not ending in /chat/completions, ensure proper base
    entry = {
        "id": raw_id,
        "name": name,
        "provider_type": provider_type,
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
    base_url: str,
    model_id: str,
    api_key: Optional[str] = None,
    timeout: float = 10.0
) -> Dict[str, Any]:
    """
    Test connectivity to an OpenAI-compatible endpoint with a minimal ping prompt.
    """
    base = base_url.rstrip("/")
    endpoint = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    
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
                return {
                    "success": False,
                    "status_code": resp.status_code,
                    "latency_ms": elapsed_ms,
                    "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
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

