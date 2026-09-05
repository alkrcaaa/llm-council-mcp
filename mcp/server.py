#!/usr/bin/env python3
"""LLM Council MCP Server.

Provides a deliberative oracle interface for Claude Code and Antigravity,
querying the 3-stage LLM Council running on port 8001 and returning high-density
ADR verdicts strictly bounded to <=150 words.
"""

import os
import re
import sys
from typing import Optional, Dict, Any, List
import httpx

COUNCIL_API_BASE = os.getenv("COUNCIL_API_BASE", "http://localhost:8001")
RECURSION_ENV_KEY = "LLM_COUNCIL_INVOCATION"

try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("llm-council")
except (ImportError, ModuleNotFoundError):
    class _DummyFastMCP:
        def tool(self):
            def decorator(fn):
                return fn
            return decorator
    mcp = _DummyFastMCP()


def format_adr_payload(stage3_data: Dict[str, Any], metadata: Dict[str, Any]) -> str:
    """Format council response into the agreed <=150-word Markdown ADR schema."""
    response_text = stage3_data.get("response", "").strip()
    if not response_text:
        return (
            "## Verdict: Deliberation Complete\n"
            "**Confidence:** Unknown\n"
            "**Recommendation:** Deliberation completed without text payload.\n"
            "**Dissenting risk:** None reported."
        )

    # 1. Clean lines and extract title/verdict
    raw_lines = [l.strip() for l in response_text.splitlines() if l.strip()]
    verdict = raw_lines[0].lstrip("#").replace("Council Verdict:", "").replace("Verdict:", "").strip()[:120]

    # 2. Extract confidence & model rankings
    aggregate_rankings = metadata.get("aggregate_rankings", [])
    if aggregate_rankings:
        top_model = aggregate_rankings[0].get("model", "").split("/")[-1].split("@")[0]
        consensus_info = f"Consensus — {len(aggregate_rankings)} models evaluated (top ranked: {top_model})"
    else:
        consensus_info = "Consensus — agreement reached"

    # 3. Section based extraction for recommendation and dissenting risk
    sections = re.split(r"\n(?=#{1,4}\s|\*\*[^*]+\*\*)", response_text)
    sec0_lines = [l.strip() for l in sections[0].splitlines() if l.strip()]
    intro_summary = " ".join([l for l in sec0_lines[1:] if not l.startswith("#")]) if len(sec0_lines) > 1 else ""

    rec_candidates = []
    risk_candidates = []
    sources_candidates = []

    for sec in sections[1:]:
        sec_clean = sec.strip()
        if not sec_clean:
            continue
        first_line = sec_clean.splitlines()[0].lower()
        if any(h in first_line for h in ["source", "radar", "consulted"]):
            sources_candidates.append(sec_clean)
        elif any(h in first_line for h in ["risk", "tradeoff", "dissent", "objection", "caveat", "failure mode", "when to", "migrate"]):
            risk_candidates.append(sec_clean)
        elif any(h in first_line for h in ["recommendation", "decision", "action", "setup", "why", "fits", "solution", "proposal", "approach"]):
            rec_candidates.append(sec_clean)

    # Prioritize dedicated recommendation section over generic intro summary
    if rec_candidates:
        first = rec_candidates[0]
        rec_text = " ".join(first.splitlines()[1:]) if "\n" in first else first
    elif intro_summary:
        rec_text = intro_summary
    else:
        rec_text = "Follow synthesis verdict."

    if risk_candidates:
        first = risk_candidates[0]
        risk_text = " ".join(first.splitlines()[1:]) if "\n" in first else first
    else:
        risk_text = "None material (unanimous alignment across council seats)."

    # Format cleanly and enforce concise word boundaries
    rec_clean = re.sub(r"```[a-z]*\n?|```", "", rec_text)
    rec_clean = " ".join(rec_clean.split())
    rec_words = rec_clean.split()
    if len(rec_words) > 65:
        rec_clean = " ".join(rec_words[:65]) + "..."

    risk_clean = re.sub(r"```[a-z]*\n?|```", "", risk_text)
    risk_clean = " ".join(risk_clean.split())
    risk_words = risk_clean.split()
    if len(risk_words) > 40:
        risk_clean = " ".join(risk_words[:40]) + "..."

    lines = [
        f"## Verdict: {verdict}",
        f"**Confidence:** {consensus_info}",
        f"**Recommendation:** {rec_clean}",
        f"**Dissenting risk:** {risk_clean}",
    ]

    if sources_candidates:
        s_first = sources_candidates[0]
        s_text = " ".join(s_first.splitlines()[1:]) if "\n" in s_first else s_first
        s_clean = re.sub(r"```[a-z]*\n?|```", "", s_text)
        s_clean = " ".join(s_clean.split())
        s_words = s_clean.split()
        if len(s_words) > 45:
            s_clean = " ".join(s_words[:45]) + "..."
        lines.append(f"**Consulted Sources & Radar:** {s_clean}")

    return "\n".join(lines)


def get_caller_model_id() -> Optional[str]:
    """Identify the host agent CLI calling the MCP server.

    Returns:
        'local/claude-code' if invoked by Claude Code,
        'local/antigravity' if invoked by Antigravity,
        None if unrecognized or generic caller.
    """
    if os.getenv("CLAUDE_PROJECT_DIR") or os.getenv("CLAUDE_CODE") or "claude" in sys.argv[0].lower():
        return "local/claude-code"
    if (
        os.getenv("ANTIGRAVITY_AGENT")
        or os.getenv("AI_AGENT") == "antigravity"
        or os.getenv("ANTIGRAVITY_CONVERSATION_ID")
        or "antigravity" in sys.argv[0].lower()
    ):
        return "local/antigravity"
    return None


def filter_panelists_for_caller(
    council_models: List[str],
    caller_model_id: Optional[str]
) -> List[str]:
    """Filter out any panelist whose model id matches the calling agent.

    Strips the model identifier before '@skill' and compares with caller_model_id.
    """
    if not caller_model_id or not council_models:
        return list(council_models)

    return [
        m for m in council_models
        if m.split("@")[0] != caller_model_id
    ]


@mcp.tool()
async def ask_council(
    question: str,
    type1_rationale: str,
    council_id: str = "cognitive-strategy",
    target_workspace: Optional[str] = None
) -> str:
    """Consult the multi-model LLM Council on high-stakes architectural or strategic decisions.

    Call this ONLY for Type-1 (irreversible/high rollback cost) decisions when you or the
    user hit genuine uncertainty or disagreement. Do NOT call for routine choices.

    Args:
        question: The architectural dilemma, library choice, or proposal to evaluate.
        type1_rationale: Explicit justification of why this decision is Type-1 (irreversible or high rollback cost). Required by council gating rules.
        council_id: One of 'cognitive-strategy', 'code-craft', 'deep-tech', 'sec-ops', 'frontend-craft'.
        target_workspace: Optional project folder name (e.g. 'dev-agent-kit') for context extraction.

    Returns:
        Structured <=150-word Markdown ADR with Verdict, Confidence, Recommendation, and Dissenting Risk.
    """
    # 0. Gating check: ensure explicit Type-1 rationale is provided
    if not type1_rationale or len(type1_rationale.strip()) < 10:
        return (
            "## Verdict: Gating Rejection (Type-1 Justification Required)\n"
            "**Confidence:** Rejected\n"
            "**Recommendation:** The LLM Council is reserved exclusively for Type-1 decisions (irreversible or high rollback cost). Provide a concrete justification in 'type1_rationale' or proceed with solo direct reasoning.\n"
            "**Dissenting risk:** Routine decision offloading prevented."
        )

    # 1. Recursion Guard: Prevent infinite loops if invoked inside a council seat
    if os.environ.get(RECURSION_ENV_KEY):
        return (
            "## Verdict: Recursive Council Call Blocked\n"
            "**Confidence:** Rejected\n"
            "**Recommendation:** The council cannot be invoked from inside another council process.\n"
            "**Dissenting risk:** Infinite deadlock prevention."
        )

    # 2. Identify caller and assign opposing peer as chairman
    caller_model_id = get_caller_model_id()
    chairman_override = "local/antigravity" if caller_model_id == "local/claude-code" else "local/claude-code"

    os.environ[RECURSION_ENV_KEY] = "1"
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            # Create a dedicated conversation for this deliberation
            conv_resp = await client.post(
                f"{COUNCIL_API_BASE}/api/conversations",
                json={"council_id": council_id}
            )
            if conv_resp.status_code != 200:
                return (
                    f"## Verdict: Failed to Initialize Council Session\n"
                    f"**Confidence:** Error ({conv_resp.status_code})\n"
                    f"**Recommendation:** Ensure llm-council backend is running on {COUNCIL_API_BASE}.\n"
                    f"**Dissenting risk:** Backend unreachable."
                )

            conv_data = conv_resp.json()
            conv_id = conv_data["id"]

            raw_council_models = conv_data.get("council_models", [])
            filtered_council_models = filter_panelists_for_caller(raw_council_models, caller_model_id)

            if len(filtered_council_models) < 2:
                return (
                    "## Verdict: Council Misconfigured for This Caller\n"
                    "**Confidence:** Rejected\n"
                    f"**Recommendation:** Deliberation requires at least 2 independent panelists after filtering out the calling agent ({caller_model_id or 'unknown'}). "
                    f"Board '{council_id}' has insufficient independent panelists for this caller.\n"
                    "**Dissenting risk:** Degenerate single-model deliberation prevented."
                )

            # Send deliberation request (synchronous 3-stage process with early consensus enabled)
            msg_payload = {
                "content": f"{question}\n\nType-1 Context: {type1_rationale.strip()}",
                "council_id": council_id,
                "chairman_model": chairman_override,
                "target_workspace": target_workspace,
                "use_early_consensus": True,
            }
            if filtered_council_models != raw_council_models:
                msg_payload["council_models"] = filtered_council_models

            msg_resp = await client.post(
                f"{COUNCIL_API_BASE}/api/conversations/{conv_id}/message",
                json=msg_payload
            )

            if msg_resp.status_code != 200:
                return (
                    f"## Verdict: Council Deliberation Error\n"
                    f"**Confidence:** Error ({msg_resp.status_code})\n"
                    f"**Recommendation:** Fall back to direct reasoning or check council server logs.\n"
                    f"**Dissenting risk:** Backend failed during deliberation: {msg_resp.text[:120]}"
                )

            result = msg_resp.json()
            stage3 = result.get("stage3", {})
            metadata = result.get("metadata", {})

            return format_adr_payload(stage3, metadata)

    except httpx.TimeoutException:
        return (
            "## Verdict: Council Deliberation Timed Out (>300s)\n"
            "**Confidence:** Aborted\n"
            "**Recommendation:** Models took too long to reach consensus; fall back to local direct analysis.\n"
            "**Dissenting risk:** Latency ceiling exceeded."
        )
    except Exception as e:
        return (
            f"## Verdict: Council Bridge Error\n"
            f"**Confidence:** Error\n"
            f"**Recommendation:** Fall back to solo reasoning.\n"
            f"**Dissenting risk:** {str(e)[:150]}"
        )
    finally:
        os.environ.pop(RECURSION_ENV_KEY, None)


@mcp.tool()
async def list_councils() -> str:
    """List available LLM Council boards, their focus domains, and models."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{COUNCIL_API_BASE}/api/councils")
            if resp.status_code == 200:
                data = resp.json()
                councils = data.get("councils", [])
                lines = ["### Available LLM Council Boards:"]
                for c in councils:
                    lines.append(f"- **{c.get('id')}** ({c.get('icon', '')} {c.get('name')}): {c.get('description')}")
                return "\n".join(lines)
    except Exception:
        pass
    return (
        "Available Councils:\n"
        "- cognitive-strategy: High-stakes architectural & strategic decisions\n"
        "- code-craft: Deep refactoring & surgical simplicity\n"
        "- deep-tech: Technology, protocol & library evaluation\n"
        "- sec-ops: Production security & SRE resilience\n"
        "- frontend-craft: Design systems & UI flows\n"
        "- tech-scout: Automated technology scouting, candidate evaluation & telemetry"
    )


@mcp.tool()
async def scout_candidates(
    query: str,
    max_candidates: int = 6
) -> str:
    """Scout and discover candidate technologies, MCP servers, libraries, or skills across GitHub, web, and local registries.

    Args:
        query: Technology keywords or problem description (e.g. 'vector database', 'obsidian mcp')
        max_candidates: Maximum number of candidates to evaluate (default 6)

    Returns:
        Structured candidate dossier with stars, forks, licenses, topics, and overview.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{COUNCIL_API_BASE}/api/research/scout",
                json={"query": query, "max_candidates": max_candidates}
            )
            if resp.status_code == 200:
                data = resp.json()
                dossier = data.get("dossier", "")
                if dossier:
                    return dossier
                candidates = data.get("candidates", [])
                if candidates:
                    return f"Found {len(candidates)} candidates: " + ", ".join(c.get("title", "") for c in candidates)
                return f"No candidate technologies found for query: '{query}'"
            return f"Scout error ({resp.status_code}): {resp.text[:120]}"
    except Exception as e:
        return f"Failed to scout candidates: {str(e)}"


if __name__ == "__main__":
    mcp.run()
