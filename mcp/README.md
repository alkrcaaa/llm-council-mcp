# LLM Council MCP Server

Provides a deliberative oracle tool (`ask_council`) for Claude Code and Antigravity.
Connects directly to the `llm-council` engine running on `http://localhost:8001`.

## Tools

- `ask_council(question, type1_rationale, council_id="cognitive-strategy", target_workspace=None)`:
  Runs a multi-model 3-stage deliberation and returns a structured `<=150` words Markdown ADR.
- `list_councils()`:
  Lists available expert boards and their descriptions.

## Gating Rule (Mandatory)

Call `ask_council` ONLY if ALL of:
1. The decision is Type-1 (irreversible or high rollback cost).
2. You (or the user) have already tried direct reasoning and hit genuine disagreement or unresolved uncertainty.
3. Getting it wrong would cost more than the ~30s + API spend of asking.
4. The user hasn't already made the call. Council informs decisions, never overrules an explicit user decision.

Anti-patterns (do NOT call): routine library choices, trivial code formatting, delegating to avoid forming a recommendation, or calling twice for the same question.
