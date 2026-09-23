"""
Round-Table / Group Chat logic for LLM Council.

Provides an organic, unconstrained multi-model conversation space (like a WhatsApp or Discord group chat)
where users can converse directly with multiple models (including free OpenRouter and local models)
without the bureaucratic 3-stage formal deliberation or ADR pipeline.
"""

import re
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Tuple, AsyncGenerator
from .openrouter import query_model_streaming
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

    system_content = (
        f"You are {current_short} participating in an open, direct, and unconstrained round-table "
        f"group chat with {user_name} and your AI colleagues ({peers_str}).\n\n"
        f"Conversation Guidelines:\n"
        f"- CRITICAL IDENTITY RULE: Speak ONLY as yourself ({current_short}). NEVER impersonate, script, roleplay, or generate dialogue turns for your colleagues ({peers_str}). Provide ONLY your own single turn response. If you want a colleague to answer or take the next turn, address them with an @mention (e.g. @colleague) and yield the turn — they are real models in this room and will answer in their own turn.\n"
        f"- Converse naturally, directly, and authentically, as in a team WhatsApp or Discord chat.\n"
        f"- Keep your response punchy, genuine, and concise (typically 1 to 3 short paragraphs). "
        f"Do NOT write lengthy formal essays, decision matrices, or structured ADRs unless explicitly asked.\n"
        f"- You are encouraged to react to, agree with, politely challenge, or riff on what your colleagues have said.\n"
        f"- If {user_name} tagged you directly with an @mention, answer them directly.\n"
        f"- If another colleague tagged you (e.g. @{current_short}), answer your colleague directly while keeping {user_name} in the loop.\n"
        f"- You may also tag a colleague with @mention (e.g. @qwen3.6-27b, @antigravity, @claude-code) if you specifically need their perspective or answer.\n"
        f"- When a question, handshake, or exchange is complete, summarize or sign off WITHOUT an @mention so the conversation naturally concludes.\n"
        f"- If {user_name} addressed the whole room, offer your own unique angle without repeating what others already said.\n"
        f"- Always respond in the language used in the room."
    )

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
    messages: List[Dict[str, str]],
    out_queue: asyncio.Queue,
    timeout: float = 120.0,
):
    """Worker task that queries a single model and pushes SSE events into out_queue."""
    try:
        async for chunk in query_model_streaming(model, messages, timeout=timeout):
            await out_queue.put(chunk)
    except Exception as e:
        await out_queue.put({
            "type": "error",
            "model": model,
            "error": str(e)
        })
    finally:
        await out_queue.put({
            "_internal_done": True,
            "model": model
        })


async def run_roundtable_stream(
    conversation_id: str,
    content: str,
    user_name: str = "User",
    max_hops: int = 8,
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

    # Append user message
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

    # Fetch custom context from conversation or active chat settings
    custom_context = conversation.get("system_prompt")
    if not custom_context:
        from . import councils
        chat_cfg = councils.get_chat_settings()
        custom_context = chat_cfg.get("system_prompt", "")

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

        for model in current_targets:
            if hop == 1:
                history_for_models = conversation["messages"][:-1]
                prompt_messages = format_roundtable_prompt(
                    current_model=model,
                    all_models=council_models,
                    history_messages=history_for_models,
                    user_content=content,
                    user_name=user_name,
                    custom_context=custom_context,
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
                )

            task = asyncio.create_task(
                stream_single_model_roundtable(model, prompt_messages, chunk_queue)
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

        # Check for peer mentions to chain into next hop
        next_targets: List[str] = []
        for m in current_targets:
            reply_text = model_buffers.get(m, "")
            peer_mentions = parse_peer_mentions(reply_text, council_models, author_model=m)
            for pm in peer_mentions:
                if pm not in next_targets:
                    next_targets.append(pm)

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
