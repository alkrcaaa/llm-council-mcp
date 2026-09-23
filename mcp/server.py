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


def _load_jwt_secret_from_env_file(repo_root: str) -> None:
    """Share the backend's JWT_SECRET without a second copy in the host MCP config.

    docker-compose feeds <repo>/.env to the backend; read the same file here.
    backend.auth reads JWT_SECRET at import time, so this must run before that import.
    """
    if os.environ.get("JWT_SECRET"):
        return
    try:
        with open(os.path.join(repo_root, ".env")) as f:
            for line in f:
                key, sep, value = line.strip().partition("=")
                if sep and key.strip() == "JWT_SECRET":
                    os.environ["JWT_SECRET"] = value.strip().strip("'\"")
                    return
    except OSError:
        pass


def _get_mcp_auth_headers() -> Dict[str, str]:
    """Generate authenticated bearer token for local agent MCP calls."""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        for p in (parent_dir, current_dir):
            if p not in sys.path:
                sys.path.insert(0, p)
        _load_jwt_secret_from_env_file(parent_dir)
        from backend.auth import create_token
        return {"Authorization": f"Bearer {create_token('mcp-agent')}"}
    except Exception:
        return {}


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
    raw_lines = [ln.strip() for ln in response_text.splitlines() if ln.strip()]
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
    sec0_lines = [ln.strip() for ln in sections[0].splitlines() if ln.strip()]
    intro_summary = " ".join([ln for ln in sec0_lines[1:] if not ln.startswith("#")]) if len(sec0_lines) > 1 else ""

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
    # AI_AGENT is set by the immediate host (Claude Code: "claude-code_<ver>_agent"),
    # so it wins over host-specific vars a parent host may have leaked into the env.
    ai_agent = os.getenv("AI_AGENT", "").lower()
    if ai_agent.startswith("claude-code"):
        return "local/claude-code"
    if ai_agent.startswith("antigravity"):
        return "local/antigravity"
    if (
        os.getenv("ANTIGRAVITY_AGENT")
        or os.getenv("ANTIGRAVITY_CONVERSATION_ID")
        or "antigravity" in sys.argv[0].lower()
    ):
        return "local/antigravity"
    if (
        os.getenv("CLAUDECODE")
        or os.getenv("CLAUDE_CODE_ENTRYPOINT")
        or os.getenv("CLAUDE_PROJECT_DIR")
        or os.getenv("CLAUDE_CODE")
        or "claude" in sys.argv[0].lower()
    ):
        return "local/claude-code"
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


LOCAL_PEERS = ("local/claude-code", "local/antigravity")


def pick_chairman(
    board_chairman: Optional[str],
    panel: List[str],
    caller_model_id: Optional[str]
) -> str:
    """Choose a chairman that never also sits on the panel.

    A panelist chairing would synthesize over its own Stage 1 answer. The caller's model
    is only avoided when possible: a shim chairman is a fresh stateless CLI process that
    never saw the caller's transcript, so it carries no bias from the caller's session.
    """
    panel_bases = {m.split("@")[0] for m in panel}
    candidates = [c for c in (board_chairman, *LOCAL_PEERS) if c and c not in panel_bases]
    for cand in candidates:
        if cand != caller_model_id:
            return cand
    return candidates[0] if candidates else (board_chairman or LOCAL_PEERS[0])


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
        council_id: Board id, e.g. 'cognitive-strategy' (default), 'code-craft', 'deep-tech', 'sec-ops', 'frontend-craft', 'tech-scout', 'cloud-deliberation'. Call list_councils for the live list.
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

    # 1. Recursion Guard: council shims export this into the seat CLI's env, which
    # passes it on to any MCP server that CLI spawns. Only read it here — setting it
    # in this long-lived process would block every concurrent ask_council call.
    if os.environ.get(RECURSION_ENV_KEY):
        return (
            "## Verdict: Recursive Council Call Blocked\n"
            "**Confidence:** Rejected\n"
            "**Recommendation:** The council cannot be invoked from inside another council process.\n"
            "**Dissenting risk:** Infinite deadlock prevention."
        )

    # 2. Identify caller; its own seat is stripped from the panel below
    caller_model_id = get_caller_model_id()

    try:
        async with httpx.AsyncClient(timeout=420.0) as client:
            # Create a dedicated conversation for this deliberation
            conv_resp = await client.post(
                f"{COUNCIL_API_BASE}/api/conversations",
                json={"council_id": council_id},
                headers=_get_mcp_auth_headers(),
            )
            if conv_resp.status_code == 401:
                return (
                    "## Verdict: Council Auth Rejected\n"
                    "**Confidence:** Error (401)\n"
                    "**Recommendation:** Backend is up but rejected the MCP token — JWT_SECRET in this MCP server's env must match the backend's. Fall back to direct reasoning.\n"
                    "**Dissenting risk:** Auth misconfiguration, not a backend outage."
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

            chairman_model = pick_chairman(
                conv_data.get("chairman_model"), filtered_council_models, caller_model_id
            )

            # Send deliberation request (synchronous 3-stage process with early consensus enabled)
            msg_payload = {
                "content": f"{question}\n\nType-1 Context: {type1_rationale.strip()}",
                "council_id": council_id,
                "chairman_model": chairman_model,
                "target_workspace": target_workspace,
                "use_early_consensus": True,
            }
            if filtered_council_models != raw_council_models:
                msg_payload["council_models"] = filtered_council_models

            msg_resp = await client.post(
                f"{COUNCIL_API_BASE}/api/conversations/{conv_id}/message",
                json=msg_payload,
                headers=_get_mcp_auth_headers(),
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
            "## Verdict: Council Deliberation Timed Out (>420s)\n"
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


@mcp.tool()
async def list_councils() -> str:
    """List available LLM Council boards, their focus domains, and models."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{COUNCIL_API_BASE}/api/councils", headers=_get_mcp_auth_headers())
            if resp.status_code == 200:
                data = resp.json()
                councils = data.get("councils", [])
                lines = ["### Available LLM Council Boards:"]
                for c in councils:
                    lines.append(f"- **{c.get('id')}** ({c.get('icon', '')} {c.get('name')}): {c.get('description')}")
                return "\n".join(lines)
            return f"Council backend error ({resp.status_code}) at {COUNCIL_API_BASE}/api/councils — board list unavailable."
    except Exception as e:
        return f"Council backend unreachable at {COUNCIL_API_BASE} ({type(e).__name__}) — board list unavailable; ask_council will fail too."



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
                json={"query": query, "max_candidates": max_candidates},
                headers=_get_mcp_auth_headers(),
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
