"""Skill-to-Tool mapping registry for LLM Council autonomous agents.

Maps model @skill specifications to curated, high-leverage toolkits.
"""

from typing import Any, Dict, List, Optional

from .mcp_bridge import get_tool_definitions

# Map each @skill identifier to its allocated toolset
SKILL_TOOL_MAP: Dict[str, List[str]] = {
    # Autonomous Researcher & Technology Scout
    "deep-research": [
        "web_search",
        "web_fetch",
        "github_scout",
        "package_scout",
    ],
    "tech-scout": [
        "web_search",
        "web_fetch",
        "github_scout",
        "package_scout",
    ],
    # Code Architecture, Diff Analysis & Refactoring
    "differential-review": [
        "workspace_git_diff",
        "workspace_read_file",
        "github_scout",
    ],
    "karpathy-guidelines": [
        "workspace_read_file",
        "workspace_git_diff",
        "web_search",
    ],
    "code-craft": [
        "workspace_read_file",
        "workspace_git_diff",
        "web_search",
    ],
    # Security, Vulnerability & Supply Chain Audit
    "owasp-security": [
        "workspace_read_file",
        "package_scout",
        "web_search",
    ],
    "static-analysis": [
        "workspace_read_file",
        "workspace_git_diff",
        "web_search",
    ],
    "supply-chain-audit": [
        "package_scout",
        "github_scout",
        "web_search",
    ],
    # Testing & Verification
    "testing-handbook": [
        "workspace_read_file",
        "web_search",
    ],
    "webapp-testing": [
        "web_search",
        "web_fetch",
        "workspace_read_file",
    ],
    # Infrastructure & Operations
    "devops": [
        "workspace_read_file",
        "workspace_git_diff",
        "web_search",
        "package_scout",
    ],
    # Logic & First Principles Audit
    "first-principles": [
        "web_search",
        "web_fetch",
        "github_scout",
    ],
    "red-team-reasoning": [
        "web_search",
        "web_fetch",
        "github_scout",
    ],
}

# All tools for Round Table / Free-form chat
ALL_AVAILABLE_TOOLS = [
    "web_search",
    "web_fetch",
    "github_scout",
    "package_scout",
    "workspace_read_file",
    "workspace_git_diff",
]


def get_tools_for_model(
    model_id: str,
    is_roundtable: bool = False,
    target_workspace: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Determine tools for a given model based on its @skill suffix or chat mode.

    Args:
        model_id: Model identifier (e.g. 'local/qwen3.8-27b@deep-research')
        is_roundtable: True if running in conversational Round Table mode

    Returns:
        List of OpenAI-compatible tool specifications
    """
    if not model_id:
        return []

    # If in open round table / chat mode, give all general tools
    if is_roundtable:
        return get_tool_definitions(ALL_AVAILABLE_TOOLS)

    # Extract skill from model string (e.g. 'local/qwen3.8-27b@deep-research')
    skill = None
    if "@" in model_id:
        skill = model_id.split("@", 1)[1].strip()

    if skill and skill in SKILL_TOOL_MAP:
        return get_tool_definitions(SKILL_TOOL_MAP[skill])

    # Default fallback: web_search and web_fetch
    return get_tool_definitions(["web_search", "web_fetch"])
