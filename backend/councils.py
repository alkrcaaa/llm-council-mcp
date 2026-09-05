"""Council profile management for LLM Council.

Allows saving, loading, creating, and switching between customized council sets
(e.g., specialized teams, local councils, architecture review boards).
"""

import json
import os
import uuid
from typing import Dict, Any, List, Optional
from pathlib import Path
from .config import DATA_DIR

COUNCILS_FILE = os.path.join(DATA_DIR, "councils.json")

BUILTIN_COUNCILS: List[Dict[str, Any]] = [
    {
        "id": "cognitive-strategy",
        "name": "Cognitive Strategy Board",
        "icon": "🧠",
        "description": "High-stakes architectural & strategic decisions: Antigravity Red Team, Qwen First Principles, Qwen Deep Research + Claude Referee.",
        "council_models": [
            "local/antigravity@red-team-reasoning",
            "local/qwen3.6-27b@first-principles",
            "local/qwen3.6-27b@deep-research",
        ],
        "chairman_model": "local/claude-code",
        "is_builtin": True,
    },
    {
        "id": "code-craft",
        "name": "Code Craft & Hard Refactor",
        "icon": "🛠️",
        "description": "Deep refactoring & surgical simplicity: Qwen Karpathy Simplicity, Antigravity Diff Risk, Qwen Test & Verification + Claude Principal Engineer.",
        "council_models": [
            "local/qwen3.6-27b@karpathy-guidelines",
            "local/antigravity@differential-review",
            "local/qwen3.6-27b@testing-handbook",
        ],
        "chairman_model": "local/claude-code",
        "is_builtin": True,
    },
    {
        "id": "deep-tech",
        "name": "Deep Tech & RFC Evaluation",
        "icon": "🔬",
        "description": "Technology, protocol & library evaluation: Antigravity Deep Research, Qwen First Principles, Qwen Supply Chain Audit + Claude CTO.",
        "council_models": [
            "local/antigravity@deep-research",
            "local/qwen3.6-27b@first-principles",
            "local/qwen3.6-27b@supply-chain-audit",
        ],
        "chairman_model": "local/claude-code",
        "is_builtin": True,
    },
    {
        "id": "sec-ops",
        "name": "Production Hardening & SecOps",
        "icon": "🛡️",
        "description": "Production security & SRE resilience: Qwen OWASP Security, Antigravity Red Team Failure Analysis, Qwen DevOps + Claude CISO.",
        "council_models": [
            "local/qwen3.6-27b@owasp-security",
            "local/antigravity@red-team-reasoning",
            "local/qwen3.6-27b@devops",
        ],
        "chairman_model": "local/claude-code",
        "is_builtin": True,
    },
    {
        "id": "frontend-craft",
        "name": "UI/UX & Design System Craft",
        "icon": "🎨",
        "description": "Distinctive design systems & user flows: Qwen Design DNA, Antigravity Frontend Design, Qwen E2E Web Testing + Claude Design Lead.",
        "council_models": [
            "local/qwen3.6-27b@design-dna",
            "local/antigravity@frontend-design",
            "local/qwen3.6-27b@webapp-testing",
        ],
        "chairman_model": "local/claude-code",
        "is_builtin": True,
    },
]


def _ensure_data_dir() -> None:
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def load_councils_data() -> Dict[str, Any]:
    """Load councils data from disk or initialize with built-in councils."""
    _ensure_data_dir()
    builtin_ids = {c["id"] for c in BUILTIN_COUNCILS}

    if os.path.exists(COUNCILS_FILE):
        try:
            with open(COUNCILS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                # Keep custom councils, prune stale built-ins, and ensure active built-ins are updated
                custom_councils = [
                    c for c in data.get("councils", [])
                    if not c.get("is_builtin") and c.get("id") not in builtin_ids
                ]
                
                # Combine active built-ins + custom councils
                councils_list = [dict(c) for c in BUILTIN_COUNCILS] + custom_councils
                data["councils"] = councils_list
                
                valid_ids = {c["id"] for c in councils_list}
                if data.get("active_council_id") not in valid_ids:
                    data["active_council_id"] = BUILTIN_COUNCILS[0]["id"]
                return data
        except Exception:
            pass

    # Initialize new councils data
    initial_data = {
        "active_council_id": BUILTIN_COUNCILS[0]["id"],
        "councils": [dict(c) for c in BUILTIN_COUNCILS],
    }
    save_councils_data(initial_data)
    return initial_data


def save_councils_data(data: Dict[str, Any]) -> None:
    """Save councils data to disk."""
    _ensure_data_dir()
    with open(COUNCILS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_all_councils() -> List[Dict[str, Any]]:
    """Return all councils list."""
    data = load_councils_data()
    return data.get("councils", [])


def get_active_council_id() -> str:
    """Get the currently active council ID."""
    data = load_councils_data()
    return data.get("active_council_id", BUILTIN_COUNCILS[0]["id"])


def get_active_council() -> Dict[str, Any]:
    """Get the active council object."""
    data = load_councils_data()
    active_id = data.get("active_council_id", BUILTIN_COUNCILS[0]["id"])
    for c in data.get("councils", []):
        if c["id"] == active_id:
            return c
    return BUILTIN_COUNCILS[0]


def set_active_council(council_id: str) -> Optional[Dict[str, Any]]:
    """Set the active council by ID."""
    data = load_councils_data()
    target = None
    for c in data.get("councils", []):
        if c["id"] == council_id:
            target = c
            break

    if not target:
        return None

    data["active_council_id"] = council_id
    save_councils_data(data)
    return target


def get_council_by_id(council_id: str) -> Optional[Dict[str, Any]]:
    """Find council by its ID."""
    data = load_councils_data()
    for c in data.get("councils", []):
        if c["id"] == council_id:
            return c
    return None


def create_custom_council(
    name: str,
    council_models: List[str],
    chairman_model: str,
    icon: str = "🏛️",
    description: str = "",
) -> Dict[str, Any]:
    """Create a new custom council profile."""
    data = load_councils_data()
    new_id = f"council-{uuid.uuid4().hex[:8]}"

    new_council = {
        "id": new_id,
        "name": name.strip() or "Custom Council",
        "icon": icon.strip() or "🏛️",
        "description": description.strip(),
        "council_models": council_models,
        "chairman_model": chairman_model,
        "is_builtin": False,
    }

    data["councils"].append(new_council)
    save_councils_data(data)
    return new_council


def update_council(
    council_id: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Update an existing council profile."""
    data = load_councils_data()
    for i, c in enumerate(data.get("councils", [])):
        if c["id"] == council_id:
            # Preserve id and builtin status
            is_builtin = c.get("is_builtin", False)
            c.update(updates)
            c["id"] = council_id
            c["is_builtin"] = is_builtin
            data["councils"][i] = c
            save_councils_data(data)
            return c
    return None


def delete_council(council_id: str) -> bool:
    """Delete a custom council profile (built-in councils cannot be deleted)."""
    data = load_councils_data()
    target = None
    for c in data.get("councils", []):
        if c["id"] == council_id:
            target = c
            break

    if not target or target.get("is_builtin", False):
        return False

    data["councils"] = [c for c in data.get("councils", []) if c["id"] != council_id]

    # If deleted council was active, reset active to first council
    if data.get("active_council_id") == council_id:
        data["active_council_id"] = BUILTIN_COUNCILS[0]["id"]

    save_councils_data(data)
    return True
