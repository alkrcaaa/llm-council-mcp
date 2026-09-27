"""
Round-Table / Group Chat logic for LLM Council.

Provides an organic, unconstrained multi-model conversation space (like a WhatsApp or Discord group chat)
where users can converse directly with multiple models (including free OpenRouter and local models)
without the bureaucratic 3-stage formal deliberation or ADR pipeline.
"""

import re
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Tuple, AsyncGenerator, Optional
from .openrouter import query_model_streaming, query_model
from . import storage


def short_model_name(model_id: str) -> str:
    """Extract a friendly clean short name from a model identifier."""
    if not model_id:
        return "Assistant"
    base = model_id.split("@")[0] if "@" in model_id else model_id
    if "/" in base:
        base = base.split("/")[-1]
    # Strip :free suffix if present
    base = base.replace(":free", "")
    return base


def parse_mentions(content: str, available_models: List[str]) -> Tuple[List[str], bool]:
    """
    Parse @mentions from user content against available council models.

    Rules:
    - If '@all', '@everyone', or '@group' is present: all models are targeted.
    - If specific model mentions (e.g. '@qwen', '@claude', '@inkling') match available models:
      only those matched models are targeted.
    - If no recognizable @mention is present: broadcast to all available models.

    Returns:
        (target_models, is_broadcast)
    """
    if not available_models:
        return [], True

    content_lower = content.lower()

    # Check for broadcast tags
    if re.search(r"@(?:all|everyone|group|hepsi|herkes)\b", content_lower):
        return list(available_models), True

    # Find all @word tokens in content and strip trailing punctuation/brackets
    raw_tokens = re.findall(r"@([\w.-]+)", content_lower)
    mention_tokens = [t.strip(".,;:!?'\"()[]{}") for t in raw_tokens if t.strip(".,;:!?'\"()[]{}")]
    if not mention_tokens:
        # Default: no mention means talk to the entire round-table
        return list(available_models), True

    matched_models: List[str] = []
    for model in available_models:
        model_clean = model.lower().replace(":free", "")
        base_short = short_model_name(model).lower()
        
        # Check if any mention token matches this model
        for token in mention_tokens:
            is_alias = (token in ("agy", "antigravity", "gemini") and "antigravity" in model_clean) or \
                       (token in ("claude", "claudecode") and "claude" in model_clean) or \
                       (token in ("qwen", "qwen3") and "qwen" in model_clean)
            if is_alias or token in base_short or base_short.startswith(token) or token in model_clean:
                if model not in matched_models:
                    matched_models.append(model)
                break

    if matched_models:
        return matched_models, len(matched_models) == len(available_models)

    # If mentions were written but none matched a model, broadcast to all
    return list(available_models), True


def parse_peer_mentions(content: str, available_models: List[str], author_model: str) -> List[str]:
    """
    Parse explicit mentions from a model's output directed at other models in the room.

    Guards:
    - Never triggers @all, @everyone, etc. (to avoid cascading explosion).
    - Ignores mentions of the author model itself.
    - Matches explicit model names and aliases (@qwen, @antigravity, @claude, etc.).
    """
    if not available_models or not content:
        return []

    content_lower = content.lower()
    raw_tokens = re.findall(r"@([\w.-]+)", content_lower)
    if not raw_tokens:
        return []

    ignore_tokens = {"all", "everyone", "group", "hepsi", "herkes"}
    specific_tokens = [
        t.strip(".,;:!?'\"()[]{}")
        for t in raw_tokens
        if t.strip(".,;:!?'\"()[]{}") and t.strip(".,;:!?'\"()[]{}") not in ignore_tokens
    ]
    if not specific_tokens:
        return []

    author_clean = author_model.lower().replace(":free", "")
    author_short = short_model_name(author_model).lower()

    matched_models: List[str] = []
    for model in available_models:
        model_clean = model.lower().replace(":free", "")
        base_short = short_model_name(model).lower()

        # Cannot trigger self
        if model == author_model or model_clean == author_clean or base_short == author_short:
            continue

        for token in specific_tokens:
            is_alias = (token in ("agy", "antigravity", "gemini") and "antigravity" in model_clean) or \
                       (token in ("claude", "claudecode") and "claude" in model_clean) or \
                       (token in ("qwen", "qwen3") and "qwen" in model_clean)
            if is_alias or token in base_short or base_short.startswith(token) or token in model_clean:
                if model not in matched_models:
                    matched_models.append(model)
                break

    return matched_models


def format_roundtable_prompt(
    current_model: str,
    all_models: List[str],
    history_messages: List[Dict[str, Any]],
    user_content: str = "",
    user_name: str = "User",
    custom_context: str = "",
    max_history_turns: int = 6,
    lead_model: Optional[str] = None,
    custom_model_prompt: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    Build the message context for a specific model participating in the round table.

    Applies an anchored sliding window: retains the opening root message (index 0)
    for topic grounding and the last `max_history_turns` recent turns to strictly bound
    input token usage and eliminate O(N^2) runaway context explosion.
    """
    current_short = short_model_name(current_model)
    peer_names = [short_model_name(m) for m in all_models if m != current_model]
    peers_str = ", ".join(peer_names) if peer_names else "none"

    is_lead = False
    lead_name = ""
    if lead_model:
        lead_name = short_model_name(lead_model)
        is_lead = (current_model == lead_model or 
                   current_model.split("@")[0] == lead_model.split("@")[0] or
                   current_short.lower() == lead_name.lower())

    if is_lead:
        role_header = (
            f"You are {current_short}, the designated TEAM LEAD & LEAD ARCHITECT of this engineering round table.\n"
            f"Colleagues at the table: {peers_str}.\n"
            f"Your responsibility: Steer the technical discussion, synthesize the team's perspectives, "
            f"evaluate trade-offs objectively, and deliver cohesive, authoritative conclusions to {user_name}.\n"
            f"Listen to your specialists; never be authoritarian. If a colleague raises valid risks or better alternatives, "
            f"acknowledge them and incorporate them into the final engineering decision."
        )
    else:
        lead_reference = f"The designated Team Lead is {lead_name}." if lead_name else "A Team Lead coordinates the room."
        role_header = (
            f"You are {current_short}, a Senior Engineering Specialist participating in this round table.\n"
            f"Team members: {peers_str}. {lead_reference}\n"
            f"Your responsibility: Provide deep, uncompromised domain expertise from your perspective."
        )

    anti_sycophancy_rules = (
        "- STRICT ANTI-SYCOPHANCY RULE (YALAKALIK YASAĞI): Do NOT be a yes-man or sycophant. "
        "Never post empty agreement, superficial flattery, or polite deferrals (e.g. 'I agree with the lead', "
        "'Well said', or 'I am waiting for my turn'). Such replies waste context and are strictly forbidden.\n"
        "- EVIDENCE-BASED BACKBONE (DİK DURUŞ): Defend your technical position with first principles, "
        "RFC standards, concrete benchmark numbers, real code trade-offs, or production failure modes. "
        "If the Team Lead or a colleague proposes something flawed, suboptimal, or high-risk, "
        "CHALLENGE THEM RESPECTFULLY BUT DIRECTLY with concrete evidence and provide the superior alternative.\n"
        "- MENTION & TURN DISCIPLINE: When referring to a colleague in third person or outlining future plans "
        "(e.g. 'as Claude noted', 'I will check with Qwen later'), write their name in PLAIN TEXT without the '@' prefix. "
        "ONLY use an '@mention' tag (e.g. @model) if you are directly addressing them to take the microphone and answer right now.\n"
        "- CRITICAL IDENTITY RULE: Speak ONLY as yourself ({current_short}). NEVER impersonate, script, roleplay, or generate dialogue turns for your colleagues ({peers_str}). Provide ONLY your own single turn response.\n"
        "- Converse naturally, directly, and punchily (typically 1 to 3 focused paragraphs). Skip formal essays unless asked.\n"
        "- If {user_name} tagged you directly with an @mention, answer them directly.\n"
        "- Always respond in the language used in the room (Turkish/English)."
    )

    custom_role_section = ""
    if custom_model_prompt and custom_model_prompt.strip():
        custom_role_section = f"\n\n--- Assigned Domain Role & Directives for {current_short} (from UI) ---\n{custom_model_prompt.strip()}\n-------------------------------------------------------------"

    system_content = f"{role_header}\n\nCore Guidelines:\n{anti_sycophancy_rules}{custom_role_section}"

    if custom_context and custom_context.strip():
        system_content += f"\n\n--- Injected User Profile & Guidelines ---\n{custom_context.strip()}\n------------------------------------------"

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_content}
    ]

    # Select effective window of past messages (anchored root message + last max_history_turns)
    if len(history_messages) > max_history_turns + 1:
        root_msg = history_messages[0]
        recent_msgs = history_messages[-max_history_turns:]
        effective_history = [root_msg] + recent_msgs
    else:
        effective_history = history_messages

    # Convert past messages into dialogue turns
    for idx, msg in enumerate(effective_history):
        role = msg.get("role")
        content = msg.get("content", "")
        if not content:
            continue

        if role == "user":
            sender = msg.get("sender_name") or user_name
            if idx == 0 and len(history_messages) > max_history_turns + 1:
                messages.append({"role": "user", "content": f"[{sender} (Opening Topic)]: {content}"})
            else:
                messages.append({"role": "user", "content": f"[{sender}]: {content}"})
        elif role == "assistant":
            msg_model = msg.get("model", "")
            if msg_model == current_model:
                messages.append({"role": "assistant", "content": content})
            else:
                sender_label = short_model_name(msg_model) if msg_model else "AI"
                messages.append({"role": "user", "content": f"[{sender_label}]: {content}"})

    # Append current user prompt if provided
    if user_content and user_content.strip():
        messages.append({"role": "user", "content": f"[{user_name}]: {user_content.strip()}"})

    # Normalize messages to merge consecutive turns of the same role (required by strict APIs)
    merged_messages: List[Dict[str, str]] = []
    for m in messages:
        if merged_messages and merged_messages[-1]["role"] == m["role"] and m["role"] != "system":
            merged_messages[-1]["content"] += f"\n\n{m['content']}"
        else:
            merged_messages.append(m)

    return merged_messages


async def stream_single_model_roundtable(
    model: str,
    messages: List[Dict[str, Any]],
    out_queue: asyncio.Queue,
    timeout: float = 120.0,
    target_workspace: Optional[str] = None,
):
    """Worker task that queries a single model with tool support and pushes SSE events into out_queue."""
    try:
        import json
        from .tools import get_tools_for_model, execute_tool

        current_messages = list(messages)
        tools = get_tools_for_model(model, is_roundtable=True, target_workspace=target_workspace)

        if tools:
            first_pass = await query_model(model, current_messages, timeout=30.0, tools=tools)
            if first_pass and first_pass.get("tool_calls"):
                current_messages.append({
                    "role": "assistant",
                    "content": first_pass.get("content") or "",
                    "tool_calls": first_pass["tool_calls"],
                })

                for tc in first_pass["tool_calls"]:
                    func = tc.get("function", {})
                    name = func.get("name", "")
                    call_id = tc.get("id", f"call_{name}")
                    raw_args = func.get("arguments", "{}")
                    args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})

                    if target_workspace and "target_workspace" not in args:
                        args["target_workspace"] = target_workspace

                    await out_queue.put({
                        "type": "tool_call",
                        "model": model,
                        "tool": name,
                        "arguments": args,
                    })

                    tool_res = await execute_tool(name, args)
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": name,
                        "content": tool_res,
                    })

        async for chunk in query_model_streaming(model, current_messages, timeout=timeout):
            await out_queue.put(chunk)
    except Exception as e:
        await out_queue.put({
            "type": "error",
            "model": model,
            "error": str(e),
        })
    finally:
        await out_queue.put({
            "_internal_done": True,
            "model": model,
        })


async def run_roundtable_stream(
    conversation_id: str,
    content: str,
    user_name: str = "User",
    max_hops: int = 2,
    target_workspace: Optional[str] = None,
    workspace_dossier: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Execute a round-table message turn and yield SSE-ready events.

    1. Parses mentions from initial user content.
    2. Saves the user message to conversation storage.
    3. Runs initial target models concurrently.
    4. If any completed model mentions a peer (e.g. @qwen, @claude, @antigravity)
       and the turn wasn't an @all broadcast, chains into the next hop (up to max_hops).
    5. Yields real-time tokens and completions per model turn.
    """
    conversation = storage.get_conversation(conversation_id)
    if not conversation:
        yield {"type": "error", "error": f"Conversation {conversation_id} not found"}
        return

    council_models = conversation.get("council_models") or []
    if not council_models:
        yield {"type": "error", "error": "No models configured for this round table"}
        return

    # Parse which models should respond initially
    target_models, is_broadcast = parse_mentions(content, council_models)
    if not target_models:
        target_models = list(council_models)

    # Append user message (clean, without raw dossier pollution)
    user_msg = {
        "role": "user",
        "sender_name": user_name,
        "content": content,
        "created_at": datetime.utcnow().isoformat(),
        "target_models": target_models,
        "is_broadcast": is_broadcast,
    }
    conversation["messages"].append(user_msg)
    storage.save_conversation(conversation)

    # Fetch active roster to identify Lead Model and custom model prompts
    from . import councils
    active_roster = councils.get_active_chat_roster() or {}
    lead_model = active_roster.get("lead_model") or (council_models[0] if council_models else None)
    model_prompts = active_roster.get("model_prompts") or {}

    custom_context = conversation.get("system_prompt")
    if not custom_context:
        chat_cfg = councils.get_chat_settings()
        custom_context = chat_cfg.get("system_prompt", "")

    if workspace_dossier:
        custom_context = f"{custom_context}\n\n{workspace_dossier}" if custom_context else workspace_dossier

    current_targets = list(target_models)
    hop = 1
    all_completed_models: List[str] = []

    while current_targets and hop <= max_hops:
        # Check if conversation was aborted by user
        curr_conv = storage.get_conversation(conversation_id)
        if curr_conv and curr_conv.get("status") == "aborted":
            break

        yield {
            "type": "roundtable_start",
            "conversation_id": conversation_id,
            "target_models": current_targets,
            "is_broadcast": is_broadcast if hop == 1 else False,
            "hop": hop,
        }

        # Queue to collect streaming chunks from all concurrent models in this hop
        chunk_queue: asyncio.Queue = asyncio.Queue()
        tasks = []

        model_buffers: Dict[str, str] = {m: "" for m in current_targets}
        model_usages: Dict[str, Dict[str, Any]] = {}
        model_costs: Dict[str, Dict[str, Any]] = {}
        model_tools: Dict[str, List[Dict[str, Any]]] = {m: [] for m in current_targets}

        for model in current_targets:
            custom_model_prompt = model_prompts.get(model) or model_prompts.get(model.split("@")[0])
            if hop == 1:
                history_for_models = conversation["messages"][:-1]
                prompt_messages = format_roundtable_prompt(
                    current_model=model,
                    all_models=council_models,
                    history_messages=history_for_models,
                    user_content=content,
                    user_name=user_name,
                    custom_context=custom_context,
                    lead_model=lead_model,
                    custom_model_prompt=custom_model_prompt,
                )
            else:
                # In subsequent hops, all previous dialogue turns are already saved in storage
                curr_conv = storage.get_conversation(conversation_id)
                history_for_models = curr_conv.get("messages", []) if curr_conv else []
                prompt_messages = format_roundtable_prompt(
                    current_model=model,
                    all_models=council_models,
                    history_messages=history_for_models,
                    user_content="",
                    user_name=user_name,
                    custom_context=custom_context,
                    lead_model=lead_model,
                    custom_model_prompt=custom_model_prompt,
                )

            effective_ws = target_workspace or conversation.get("target_workspace")
            task = asyncio.create_task(
                stream_single_model_roundtable(model, prompt_messages, chunk_queue, target_workspace=effective_ws)
            )
            tasks.append(task)

        active_tasks = len(current_targets)

        while active_tasks > 0:
            chunk = await chunk_queue.get()
            if chunk.get("_internal_done"):
                active_tasks -= 1
                chunk_queue.task_done()
                continue

            chunk_type = chunk.get("type")
            model = chunk.get("model", "")

            if chunk_type == "token":
                tok = chunk.get("content", "")
                if model in model_buffers:
                    model_buffers[model] += tok
                yield {
                    "type": "roundtable_token",
                    "model": model,
                    "content": tok,
                }
            elif chunk_type == "tool_call":
                tool_data = {
                    "tool": chunk.get("tool"),
                    "arguments": chunk.get("arguments"),
                }
                if model not in model_tools:
                    model_tools[model] = []
                model_tools[model].append(tool_data)
                yield {
                    "type": "roundtable_tool_call",
                    "model": model,
                    "tool": chunk.get("tool"),
                    "arguments": chunk.get("arguments"),
                    "hop": hop,
                }
            elif chunk_type == "complete":
                model_buffers[model] = chunk.get("content", model_buffers[model])
                if "usage" in chunk:
                    model_usages[model] = chunk["usage"]
                if "cost" in chunk:
                    model_costs[model] = chunk["cost"]

                # Save completed response into conversation history immediately
                assistant_msg = {
                    "role": "assistant",
                    "model": model,
                    "content": model_buffers[model],
                    "created_at": datetime.utcnow().isoformat(),
                    "usage": model_usages.get(model),
                    "cost": model_costs.get(model),
                    "tools_executed": model_tools.get(model, []),
                }
                curr_conv = storage.get_conversation(conversation_id)
                if curr_conv:
                    curr_conv["messages"].append(assistant_msg)
                    curr_conv["status"] = "streaming"
                    storage.save_conversation(curr_conv)

                if model not in all_completed_models:
                    all_completed_models.append(model)

                yield {
                    "type": "roundtable_model_complete",
                    "model": model,
                    "content": model_buffers[model],
                    "usage": model_usages.get(model),
                    "cost": model_costs.get(model),
                    "tools_executed": model_tools.get(model, []),
                    "hop": hop,
                }
            elif chunk_type == "error":
                yield {
                    "type": "roundtable_model_error",
                    "model": model,
                    "error": chunk.get("error", "Unknown model query error"),
                    "hop": hop,
                }

            chunk_queue.task_done()

        # Wait for all background worker tasks to conclude for this hop
        await asyncio.gather(*tasks, return_exceptions=True)

        # Check for peer mentions to chain into next hop (only if not already broadcast and within hop limit)
        next_targets: List[str] = []
        if hop < max_hops and not is_broadcast:
            for m in current_targets:
                reply_text = model_buffers.get(m, "")
                peer_mentions = parse_peer_mentions(reply_text, council_models, author_model=m)
                # Take at most 1 peer mention per speaker to avoid concurrent chain explosions
                for pm in peer_mentions[:1]:
                    # Guard: Never re-trigger a model that already completed a response in this turn
                    if pm not in all_completed_models and pm not in next_targets:
                        next_targets.append(pm)
                        break

            # Limit next_targets to 1 model per hop during autonomous chaining
            if len(next_targets) > 1:
                next_targets = next_targets[:1]

        current_targets = next_targets
        hop += 1

    # Set final conversation status to idle
    final_conv = storage.get_conversation(conversation_id)
    if final_conv:
        final_conv["status"] = "idle"
        storage.save_conversation(final_conv)

    yield {
        "type": "roundtable_complete",
        "conversation_id": conversation_id,
        "completed_models": all_completed_models,
    }
