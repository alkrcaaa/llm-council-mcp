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
        "icon": "",
        "description": "High-stakes architectural & strategic decisions: Antigravity Red Team, Gemini 3.6 Flash Red Team, Qwen First Principles, Groq Llama 3.3 Deep Research + Claude Referee.",
        "council_models": [
            "local/antigravity@red-team-reasoning",
            "custom/gemini-3-6-flash@red-team-reasoning",
            "local/qwen3.6-27b@first-principles",
            "custom/groq@deep-research",
        ],
        "chairman_model": "local/claude-code",
        "is_builtin": True,
    },
    {
        "id": "code-craft",
        "name": "Code Craft & Hard Refactor",
        "icon": "",
        "description": "Deep refactoring & surgical simplicity: Antigravity Diff Risk, Qwen Test & Verification, Gemini 3.6 Static Analysis, Groq Llama 3.3 Simplicity + Claude Principal Engineer.",
        "council_models": [
            "local/antigravity@differential-review",
            "local/qwen3.6-27b@testing-handbook",
            "custom/gemini-3-6-flash@static-analysis",
            "custom/groq@karpathy-guidelines",
        ],
        "chairman_model": "local/claude-code",
        "is_builtin": True,
    },
    {
        "id": "deep-tech",
        "name": "Deep Tech & RFC Evaluation",
        "icon": "",
        "description": "Technology, protocol & library evaluation: Antigravity Deep Research, Qwen Supply Chain Audit, Gemini 3.6 First Principles, Groq Llama 3.3 Simplicity + Claude CTO.",
        "council_models": [
            "local/antigravity@deep-research",
            "local/qwen3.6-27b@supply-chain-audit",
            "custom/gemini-3-6-flash@first-principles",
            "custom/groq@karpathy-guidelines",
        ],
        "chairman_model": "local/claude-code",
        "is_builtin": True,
    },
    {
        "id": "sec-ops",
        "name": "Production Hardening & SecOps",
        "icon": "",
        "description": "Production security & SRE resilience: Antigravity Red Team, Qwen OWASP Security, Groq Llama 3.3 DevOps, Gemini 3.6 Static Analysis + Claude CISO.",
        "council_models": [
            "local/antigravity@red-team-reasoning",
            "local/qwen3.6-27b@owasp-security",
            "custom/groq@devops",
            "custom/gemini-3-6-flash@static-analysis",
        ],
        "chairman_model": "local/claude-code",
        "is_builtin": True,
    },
    {
        "id": "frontend-craft",
        "name": "UI/UX & Design System Craft",
        "icon": "",
        "description": "Distinctive design systems & user flows: Antigravity Frontend Design, Qwen Design DNA, Groq Web Testing, Gemini 3.6 First Principles + Claude Design Lead.",
        "council_models": [
            "local/antigravity@frontend-design",
            "local/qwen3.6-27b@design-dna",
            "custom/groq@webapp-testing",
            "custom/gemini-3-6-flash@first-principles",
        ],
        "chairman_model": "local/claude-code",
        "is_builtin": True,
    },
    {
        "id": "tech-scout",
        "name": "Tech Scout & Candidate Radar",
        "icon": "",
        "description": "Automated technology scouting & candidate evaluation: Antigravity Deep Research, Qwen Supply Chain Audit, Gemini 3.6 First Principles, Groq Simplicity + Claude Evaluator.",
        "council_models": [
            "local/antigravity@deep-research",
            "local/qwen3.6-27b@supply-chain-audit",
            "custom/gemini-3-6-flash@first-principles",
            "custom/groq@karpathy-guidelines",
        ],
        "chairman_model": "local/claude-code",
        "is_builtin": True,
        "force_research": True,
    },
    {
        "id": "cloud-deliberation",
        "name": "Cloud Deliberation",
        "icon": "",
        "description": "Responsive zero-cost cloud & local models: Gemini 3.6 Flash, Groq Llama 3.3, Local Qwen.",
        "council_models": [
            "custom/gemini-3-6-flash@red-team-reasoning",
            "custom/groq@first-principles",
            "local/qwen3.6-27b@deep-research",
        ],
        "chairman_model": "custom/gemini-3-6-flash",
        "is_builtin": True,
    },
]


BUILTIN_CHAT_ROSTERS: List[Dict[str, Any]] = [
    {
        "id": "roundtable-core",
        "name": "Round Table Core",
        "icon": "",
        "description": "Full multi-agent room with local engineering models (Antigravity, Claude, Qwen) and fast frontier cloud peers (Gemini 3.6, Groq Llama 3.3).",
        "models": [
            "local/antigravity",
            "local/claude-code",
            "local/qwen3.6-27b",
            "custom/gemini-3-6-flash",
            "custom/groq",
        ],
        "is_builtin": True,
    },
    {
        "id": "fast-trio",
        "name": "Fast Chat Trio",
        "icon": "",
        "description": "Lightning-fast conversational room with ultra-low latency Gemini 3.6 Flash, Groq 300 t/s Llama 3.3 and local Qwen.",
        "models": [
            "custom/gemini-3-6-flash@karpathy-guidelines",
            "custom/groq@first-principles",
            "local/qwen3.6-27b@deep-research",
        ],
        "is_builtin": True,
    },
    {
        "id": "code-collaborators",
        "name": "Code Collaborators",
        "icon": "",
        "description": "Pair programming, refactoring & review discussion team.",
        "models": [
            "local/antigravity@differential-review",
            "local/qwen3.6-27b@testing-handbook",
            "custom/groq@karpathy-guidelines",
            "custom/gemini-3-6-flash@static-analysis",
        ],
        "is_builtin": True,
    },
    {
        "id": "creative-brainstorm",
        "name": "Creative Brainstorm",
        "icon": "",
        "description": "Multi-perspective ideation and open challenge room.",
        "models": [
            "custom/gemini-3-6-flash@first-principles",
            "custom/groq@red-team-reasoning",
            "local/qwen3.6-27b@deep-research",
        ],
        "is_builtin": True,
    },
]


def _ensure_data_dir() -> None:
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def load_councils_data() -> Dict[str, Any]:
    """Load councils and chat rosters data from disk or initialize with built-in configurations."""
    _ensure_data_dir()
    builtin_ids = {c["id"] for c in BUILTIN_COUNCILS}
    builtin_roster_ids = {r["id"] for r in BUILTIN_CHAT_ROSTERS}

    if os.path.exists(COUNCILS_FILE):
        try:
            with open(COUNCILS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

                # Keep custom councils, prune stale built-ins, and ensure active built-ins are
                # updated -- except the ones the user edited, whose version wins so their
                # seat changes survive a reload.
                saved_by_id = {c.get("id"): c for c in data.get("councils", [])}
                custom_councils = [
                    c for c in data.get("councils", [])
                    if not c.get("is_builtin") and c.get("id") not in builtin_ids
                ]
                councils_list = []
                for builtin in BUILTIN_COUNCILS:
                    saved = saved_by_id.get(builtin["id"])
                    councils_list.append(
                        dict(saved) if saved and saved.get("is_customized") else dict(builtin)
                    )
                councils_list += custom_councils
                data["councils"] = councils_list

                valid_ids = {c["id"] for c in councils_list}
                if data.get("active_council_id") not in valid_ids:
                    data["active_council_id"] = BUILTIN_COUNCILS[0]["id"]

                # Handle chat rosters
                saved_rosters_by_id = {r.get("id"): r for r in data.get("chat_rosters", [])}
                custom_rosters = [
                    r for r in data.get("chat_rosters", [])
                    if not r.get("is_builtin") and r.get("id") not in builtin_roster_ids
                ]
                rosters_list = []
                for builtin_roster in BUILTIN_CHAT_ROSTERS:
                    saved = saved_rosters_by_id.get(builtin_roster["id"])
                    rosters_list.append(
                        dict(saved) if saved and saved.get("is_customized") else dict(builtin_roster)
                    )
                rosters_list += custom_rosters
                data["chat_rosters"] = rosters_list

                valid_roster_ids = {r["id"] for r in rosters_list}
                if data.get("active_chat_roster_id") not in valid_roster_ids:
                    data["active_chat_roster_id"] = BUILTIN_CHAT_ROSTERS[0]["id"]

                save_councils_data(data)
                return data
        except Exception:
            pass

    # Initialize new councils data
    initial_data = {
        "active_council_id": BUILTIN_COUNCILS[0]["id"],
        "councils": [dict(c) for c in BUILTIN_COUNCILS],
        "active_chat_roster_id": BUILTIN_CHAT_ROSTERS[0]["id"],
        "chat_rosters": [dict(r) for r in BUILTIN_CHAT_ROSTERS],
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
    icon: str = "",
    description: str = "",
) -> Dict[str, Any]:
    """Create a new custom council profile."""
    data = load_councils_data()
    new_id = f"council-{uuid.uuid4().hex[:8]}"

    new_council = {
        "id": new_id,
        "name": name.strip() or "Custom Council",
        "icon": icon.strip(),
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
            # Marks this built-in as user-owned so the loader stops overwriting it.
            c["is_customized"] = True
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


# -----------------------------------------------------------------------------
# Chat Rosters (Round Table Group Chat Mode)
# -----------------------------------------------------------------------------

def get_all_chat_rosters() -> List[Dict[str, Any]]:
    """Return all chat rosters list."""
    data = load_councils_data()
    return data.get("chat_rosters", [dict(r) for r in BUILTIN_CHAT_ROSTERS])


def get_active_chat_roster_id() -> str:
    """Get the currently active chat roster ID."""
    data = load_councils_data()
    return data.get("active_chat_roster_id", BUILTIN_CHAT_ROSTERS[0]["id"])


def get_active_chat_roster() -> Dict[str, Any]:
    """Get the active chat roster object."""
    data = load_councils_data()
    active_id = data.get("active_chat_roster_id", BUILTIN_CHAT_ROSTERS[0]["id"])
    for r in data.get("chat_rosters", []):
        if r["id"] == active_id:
            return r
    return BUILTIN_CHAT_ROSTERS[0]


def set_active_chat_roster(roster_id: str) -> Optional[Dict[str, Any]]:
    """Set the active chat roster by ID."""
    data = load_councils_data()
    target = None
    for r in data.get("chat_rosters", []):
        if r["id"] == roster_id:
            target = r
            break

    if not target:
        return None

    data["active_chat_roster_id"] = roster_id
    save_councils_data(data)
    return target


def get_chat_roster_by_id(roster_id: str) -> Optional[Dict[str, Any]]:
    """Find chat roster by its ID."""
    data = load_councils_data()
    for r in data.get("chat_rosters", []):
        if r["id"] == roster_id:
            return r
    return None


def create_custom_chat_roster(
    name: str,
    models: List[str],
    icon: str = "",
    description: str = "",
) -> Dict[str, Any]:
    """Create a new custom chat roster."""
    data = load_councils_data()
    new_id = f"roster-{uuid.uuid4().hex[:8]}"

    new_roster = {
        "id": new_id,
        "name": name.strip() or "Custom Chat Team",
        "icon": icon.strip(),
        "description": description.strip(),
        "models": models,
        "is_builtin": False,
    }

    if "chat_rosters" not in data:
        data["chat_rosters"] = [dict(r) for r in BUILTIN_CHAT_ROSTERS]
    data["chat_rosters"].append(new_roster)
    save_councils_data(data)
    return new_roster


def update_chat_roster(
    roster_id: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Update an existing chat roster."""
    data = load_councils_data()
    for i, r in enumerate(data.get("chat_rosters", [])):
        if r["id"] == roster_id:
            is_builtin = r.get("is_builtin", False)
            r.update(updates)
            r["id"] = roster_id
            r["is_builtin"] = is_builtin
            # Marks this built-in as user-owned so the loader stops overwriting it.
            r["is_customized"] = True
            data["chat_rosters"][i] = r
            save_councils_data(data)
            return r
    return None


def delete_chat_roster(roster_id: str) -> bool:
    """Delete a custom chat roster (built-in rosters cannot be deleted)."""
    data = load_councils_data()
    target = None
    for r in data.get("chat_rosters", []):
        if r["id"] == roster_id:
            target = r
            break

    if not target or target.get("is_builtin", False):
        return False

    data["chat_rosters"] = [r for r in data.get("chat_rosters", []) if r["id"] != roster_id]

    if data.get("active_chat_roster_id") == roster_id:
        data["active_chat_roster_id"] = BUILTIN_CHAT_ROSTERS[0]["id"]

    save_councils_data(data)
    return True


DEFAULT_CHAT_SYSTEM_PROMPT = """### User Profile & Communication Guidelines
Edit this in Settings to describe who you are and how you want the models to respond.
- Be direct, precise and respectful; skip filler phrases, flattery and emoji.
- Prefer concrete examples, real code and evidence over abstract theory.
- Push back when a proposal adds needless complexity, uses the wrong tool or hides a cost.
- Give complete, copy-pasteable commands and code rather than fragments."""


def get_chat_settings() -> Dict[str, Any]:
    """Get round table chat configuration (participating models and injected system prompt / user bio)."""
    data = load_councils_data()
    chat_cfg = data.get("chat_settings")
    if not chat_cfg or not isinstance(chat_cfg, dict):
        active_roster = get_active_chat_roster()
        models = (active_roster.get("models") if active_roster else None) or [
            "local/antigravity",
            "local/claude-code",
            "local/qwen3.6-27b",
            "liquid/lfm-2.5-2.6b:free",
            "nex-agi/nex-n2.5-mini:free",
        ]
        chat_cfg = {
            "models": models,
            "system_prompt": DEFAULT_CHAT_SYSTEM_PROMPT,
        }
        data["chat_settings"] = chat_cfg
        save_councils_data(data)
    elif "system_prompt" not in chat_cfg:
        chat_cfg["system_prompt"] = DEFAULT_CHAT_SYSTEM_PROMPT
        data["chat_settings"] = chat_cfg
        save_councils_data(data)
    return chat_cfg


def update_chat_settings(
    models: Optional[List[str]] = None,
    system_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Update round table chat configuration."""
    data = load_councils_data()
    current = get_chat_settings()
    if models is not None:
        current["models"] = [m for m in models if m.strip()]
        # Also sync with active roster
        active_id = get_active_chat_roster_id()
        for r in data.get("chat_rosters", []):
            if r["id"] == active_id:
                r["models"] = current["models"]
                break
    if system_prompt is not None:
        current["system_prompt"] = system_prompt

    data["chat_settings"] = current
    save_councils_data(data)
    return current


def reset_chat_system_prompt() -> str:
    """Reset the chat system prompt to the canonical English vault-grounded bio."""
    update_chat_settings(system_prompt=DEFAULT_CHAT_SYSTEM_PROMPT)
    return DEFAULT_CHAT_SYSTEM_PROMPT

