"""ReAct Tool Execution Loop for LLM Council Autonomous Agents.

Handles:
- Calling model with OpenAI-compatible tool specifications
- Detecting and executing tool calls
- Appending tool messages and multi-turn completion
- Bounded turn iteration (safeguard against infinite tool loops)
"""

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from .mcp_bridge import execute_tool

logger = logging.getLogger("llm_council.executor")


async def run_agentic_tool_loop(
    query_fn: Callable[..., Any],
    model: str,
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    target_workspace: Optional[str] = None,
    max_turns: int = 3,
) -> Dict[str, Any]:
    """Execute a bounded ReAct tool-calling loop with the given model.

    Args:
        query_fn: Async function taking (model, messages, tools=...) and returning model response dict
        model: Target model identifier
        messages: Initial conversation history
        tools: OpenAI-compatible tools list
        target_workspace: Target project/workspace context
        max_turns: Maximum allowed tool call rounds (default 3)

    Returns:
        Dict containing:
        - content: Final assistant text
        - tools_executed: List of tool call records with results
        - usage: Aggregated token usage
        - cost: Aggregated cost
    """
    current_messages = list(messages)
    tools_executed: List[Dict[str, Any]] = []
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    total_cost = {"input_cost": 0.0, "output_cost": 0.0, "total_cost": 0.0}

    for turn in range(max_turns):
        # Only pass tools if we still have turns remaining
        active_tools = tools if turn < max_turns - 1 else None

        response = await query_fn(model, current_messages, tools=active_tools)
        if not response:
            break

        # Accumulate usage & cost
        resp_usage = response.get("usage", {})
        total_usage["prompt_tokens"] += resp_usage.get("prompt_tokens", 0)
        total_usage["completion_tokens"] += resp_usage.get("completion_tokens", 0)
        total_usage["total_tokens"] += resp_usage.get("total_tokens", 0)

        resp_cost = response.get("cost", {})
        total_cost["input_cost"] += resp_cost.get("input_cost", 0.0)
        total_cost["output_cost"] += resp_cost.get("output_cost", 0.0)
        total_cost["total_cost"] += resp_cost.get("total_cost", 0.0)

        tool_calls = response.get("tool_calls")
        if not tool_calls:
            # Model finished reasoning and returned final text
            return {
                "content": response.get("content", ""),
                "tools_executed": tools_executed,
                "usage": total_usage,
                "cost": total_cost,
                "reasoning_details": response.get("reasoning_details"),
            }

        # Model requested one or more tool executions
        assistant_msg: Dict[str, Any] = {
            "role": "assistant",
            "content": response.get("content") or "",
            "tool_calls": tool_calls,
        }
        current_messages.append(assistant_msg)

        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            call_id = tc.get("id", f"call_{len(tools_executed)}")
            raw_args = func.get("arguments", "{}")

            args = {}
            if isinstance(raw_args, dict):
                args = raw_args
            elif isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args)
                except Exception:
                    args = {"query": raw_args}

            logger.info(f"Agent [{model}] executing tool: {name}({args})")
            tool_output = await execute_tool(name, args, target_workspace=target_workspace)

            tools_executed.append({
                "tool": name,
                "arguments": args,
                "result_preview": tool_output[:300] if tool_output else "",
            })

            # Append tool result back to message history
            current_messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "name": name,
                "content": tool_output,
            })

    # Return whatever content was last generated
    return {
        "content": response.get("content", "") if response else "",
        "tools_executed": tools_executed,
        "usage": total_usage,
        "cost": total_cost,
    }
