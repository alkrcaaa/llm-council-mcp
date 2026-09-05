"""OpenRouter API client for making LLM requests."""

import httpx
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL, LOCAL_MODELS
from .pricing import calculate_cost


def _resolve_endpoint(model: str):
    """
    Resolve the API endpoint, headers, and outgoing model id for a council
    model identifier. Models registered in LOCAL_MODELS are routed to their
    own OpenAI-compatible endpoint (e.g. a self-hosted vLLM server); every
    other model goes to OpenRouter as before.
    Supports model@skill_id syntax by stripping the skill persona suffix.

    Returns:
        (url, headers, outgoing_model_id)
    """
    base_model = model.split("@")[0] if "@" in model else model

    local = LOCAL_MODELS.get(base_model)
    if local:
        headers = {"Content-Type": "application/json"}
        if local["api_key"]:
            headers["Authorization"] = f"Bearer {local['api_key']}"
        return local["base_url"], headers, local["model_id"]

    headers = {
        "Content-Type": "application/json",
    }
    if OPENROUTER_API_KEY and OPENROUTER_API_KEY.strip():
        headers["Authorization"] = f"Bearer {OPENROUTER_API_KEY.strip()}"
    return OPENROUTER_API_URL, headers, base_model


def _prepare_messages_for_model(model: str, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Inject domain skill instructions into system prompt if model identifier has @skill."""
    if "@" not in model:
        return messages

    try:
        from .skills import parse_model_identifier, get_skill_instructions
        _, skill_id = parse_model_identifier(model)
        if not skill_id:
            return messages

        skill_prompt = get_skill_instructions(skill_id)
        if not skill_prompt:
            return messages

        augmented = []
        has_system = False
        for msg in messages:
            if msg.get("role") == "system":
                has_system = True
                augmented.append({
                    "role": "system",
                    "content": f"{msg.get('content', '')}\n\n{skill_prompt}".strip()
                })
            else:
                augmented.append(msg)

        if not has_system:
            augmented.insert(0, {
                "role": "system",
                "content": skill_prompt
            })

        return augmented
    except Exception as e:
        print(f"Error preparing skill messages for {model}: {e}")
        return messages


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o" or "local/qwen3.6-27b@owasp-security")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with content, reasoning_details, usage, and cost.
    """
    url, headers, outgoing_model = _resolve_endpoint(model)
    model_messages = _prepare_messages_for_model(model, messages)

    payload = {
        "model": outgoing_model,
        "messages": model_messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            message = data['choices'][0]['message']

            # Extract usage data from response
            usage = data.get('usage', {})
            prompt_tokens = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)

            # Calculate cost based on usage
            cost = calculate_cost(model, prompt_tokens, completion_tokens)

            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details'),
                'usage': {
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'total_tokens': prompt_tokens + completion_tokens,
                },
                'cost': cost,
            }

    except Exception as e:
        print(f"Error querying model {model}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model identifier to response dict (or None if failed).
        Each response includes content, reasoning_details, usage, and cost.
    """
    import asyncio

    # Create tasks for all models
    tasks = [query_model(model, messages) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}


async def query_model_streaming(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Query a single model via OpenRouter API with streaming.

    Yields token events as they arrive from the model.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Yields:
        Dict events with types:
        - {'type': 'token', 'content': str, 'model': str} - Incremental token
        - {'type': 'reasoning_token', 'content': str, 'model': str} - Reasoning token (for reasoning models)
        - {'type': 'complete', 'model': str, 'content': str, 'reasoning_details': str|None, 'usage': dict, 'cost': dict}
        - {'type': 'error', 'model': str, 'error': str}
    """
    url, headers, outgoing_model = _resolve_endpoint(model)
    model_messages = _prepare_messages_for_model(model, messages)

    payload = {
        "model": outgoing_model,
        "messages": model_messages,
        "stream": True,
    }

    full_content = ""
    full_reasoning = ""
    usage_data = {}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=payload
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    # SSE format: "data: {...}"
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix

                        # Check for stream end
                        if data_str.strip() == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)

                            # Extract delta content
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content")
                                reasoning = delta.get("reasoning_content") or delta.get("reasoning")

                                if content:
                                    full_content += content
                                    yield {
                                        "type": "token",
                                        "content": content,
                                        "model": model,
                                    }

                                if reasoning:
                                    full_reasoning += reasoning
                                    yield {
                                        "type": "reasoning_token",
                                        "content": reasoning,
                                        "model": model,
                                    }

                            # Extract usage data (usually in the final chunk)
                            if "usage" in data:
                                usage_data = data["usage"]

                        except json.JSONDecodeError:
                            # Skip malformed JSON
                            continue

        # Calculate cost from usage
        prompt_tokens = usage_data.get("prompt_tokens", 0)
        completion_tokens = usage_data.get("completion_tokens", 0)
        cost = calculate_cost(model, prompt_tokens, completion_tokens)

        # Yield completion event
        yield {
            "type": "complete",
            "model": model,
            "content": full_content,
            "reasoning_details": full_reasoning if full_reasoning else None,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "cost": cost,
        }

    except Exception as e:
        print(f"Error streaming from model {model}: {e}")
        yield {
            "type": "error",
            "model": model,
            "error": str(e),
        }


async def query_models_parallel_streaming(
    models: List[str],
    messages: List[Dict[str, str]]
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Query multiple models in parallel with streaming.

    Streams tokens from all models concurrently, yielding events as they arrive.
    Each event includes the model identifier so the caller can track which model
    produced which tokens.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model

    Yields:
        Dict events (same as query_model_streaming) with model identifier included.
        Events from different models may interleave.
    """
    import asyncio

    async def stream_model(model: str, queue: asyncio.Queue):
        """Stream from a single model and put events in the queue."""
        async for event in query_model_streaming(model, messages):
            await queue.put(event)
        # Signal this model is done
        await queue.put({"type": "model_done", "model": model})

    # Create a queue for collecting events from all models
    queue = asyncio.Queue()

    # Start streaming from all models concurrently
    tasks = [asyncio.create_task(stream_model(model, queue)) for model in models]

    # Track how many models are still streaming
    models_remaining = len(models)
    completed_responses = {}

    try:
        while models_remaining > 0:
            event = await queue.get()

            if event["type"] == "model_done":
                models_remaining -= 1
            elif event["type"] == "complete":
                # Store completed response for final aggregation
                completed_responses[event["model"]] = event
                yield event
            else:
                yield event

    finally:
        # Ensure all tasks are completed
        for task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
