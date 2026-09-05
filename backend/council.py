"""3-stage LLM Council orchestration."""

import re
import time
from typing import List, Dict, Any, Tuple, Optional, AsyncGenerator
from .openrouter import query_models_parallel, query_model, query_models_parallel_streaming, query_model_streaming
from .config_api import get_council_models, get_chairman_model, get_routing_pools
from .pricing import aggregate_costs
from . import analytics
from . import weights
from . import router


# Confidence prompt suffix added to Stage 1 queries
CONFIDENCE_PROMPT_SUFFIX = """

Guidelines:
- Provide a direct, structured, and focused answer (maximum 200-300 words or clear bullet points). Avoid conversational preamble or repetitive filler.

After your response, please provide a confidence score from 1-10 indicating how confident you are in your answer. Format it exactly as:
CONFIDENCE: [score]
where [score] is a number from 1 (very uncertain) to 10 (very confident).
"""


# Chain-of-Thought prompt suffix for structured reasoning
COT_PROMPT_SUFFIX = """

Please structure your response using the following format to show your reasoning process:

**THINKING:**
[List the key aspects of the question and your initial thoughts. What are the important considerations?]

**ANALYSIS:**
[Evaluate different approaches or perspectives. Compare options, consider trade-offs, and explain your reasoning.]

**CONCLUSION:**
[Provide your final answer based on your analysis above.]

Make sure to include all three sections (THINKING, ANALYSIS, CONCLUSION) with clear headers.
"""


def parse_cot_response(text: str) -> Optional[Dict[str, str]]:
    """
    Parse Chain-of-Thought sections from model response text.

    Extracts THINKING, ANALYSIS, and CONCLUSION sections from a structured response.

    Args:
        text: The full response text from the model

    Returns:
        Dict with 'thinking', 'analysis', 'conclusion' keys, or None if not found
    """
    if not text:
        return None

    # Patterns to match section headers (case insensitive, with optional ** markdown)
    thinking_patterns = [
        r'\*\*THINKING:\*\*\s*(.*?)(?=\*\*ANALYSIS|\*\*Analysis|\Z)',
        r'\*\*Thinking:\*\*\s*(.*?)(?=\*\*ANALYSIS|\*\*Analysis|\Z)',
        r'THINKING:\s*(.*?)(?=ANALYSIS:|Analysis:|\Z)',
        r'Thinking:\s*(.*?)(?=ANALYSIS:|Analysis:|\Z)',
    ]

    analysis_patterns = [
        r'\*\*ANALYSIS:\*\*\s*(.*?)(?=\*\*CONCLUSION|\*\*Conclusion|\Z)',
        r'\*\*Analysis:\*\*\s*(.*?)(?=\*\*CONCLUSION|\*\*Conclusion|\Z)',
        r'ANALYSIS:\s*(.*?)(?=CONCLUSION:|Conclusion:|\Z)',
        r'Analysis:\s*(.*?)(?=CONCLUSION:|Conclusion:|\Z)',
    ]

    conclusion_patterns = [
        r'\*\*CONCLUSION:\*\*\s*(.*?)(?=CONFIDENCE:|Confidence:|\Z)',
        r'\*\*Conclusion:\*\*\s*(.*?)(?=CONFIDENCE:|Confidence:|\Z)',
        r'CONCLUSION:\s*(.*?)(?=CONFIDENCE:|Confidence:|\Z)',
        r'Conclusion:\s*(.*?)(?=CONFIDENCE:|Confidence:|\Z)',
    ]

    def find_section(patterns: List[str], text: str) -> Optional[str]:
        """Try each pattern and return the first match."""
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    thinking = find_section(thinking_patterns, text)
    analysis = find_section(analysis_patterns, text)
    conclusion = find_section(conclusion_patterns, text)

    # Only return structured CoT if we found at least thinking and conclusion
    if thinking and conclusion:
        return {
            "thinking": thinking,
            "analysis": analysis or "",
            "conclusion": conclusion,
        }

    return None


def extract_response_without_cot(text: str) -> str:
    """
    Extract the clean response content from CoT-structured text.

    When CoT is enabled, returns just the conclusion.
    When CoT sections aren't found, returns the original text.

    Args:
        text: The full response text

    Returns:
        Clean response text (conclusion if CoT found, or original text)
    """
    cot = parse_cot_response(text)
    if cot and cot.get("conclusion"):
        return cot["conclusion"]
    return text


def parse_confidence(text: str) -> Optional[int]:
    """
    Parse confidence score from model response text.

    Args:
        text: The full response text from the model

    Returns:
        Confidence score (1-10) or None if not found/invalid
    """
    if not text:
        return None

    # Look for "CONFIDENCE: X" pattern (case insensitive)
    patterns = [
        r'CONFIDENCE:\s*(\d+)',           # CONFIDENCE: 8
        r'CONFIDENCE:\s*\[(\d+)\]',       # CONFIDENCE: [8]
        r'Confidence:\s*(\d+)',           # Confidence: 8
        r'confidence:\s*(\d+)',           # confidence: 8
        r'CONFIDENCE\s*=\s*(\d+)',        # CONFIDENCE = 8
        r'Confidence\s+score:\s*(\d+)',   # Confidence score: 8
        r'\*\*CONFIDENCE:\*\*\s*(\d+)',   # **CONFIDENCE:** 8
        r'\*\*Confidence:\*\*\s*(\d+)',   # **Confidence:** 8
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                score = int(match.group(1))
                # Clamp to valid range
                return max(1, min(10, score))
            except ValueError:
                continue

    return None


def extract_response_without_confidence(text: str) -> str:
    """
    Remove the confidence line from the response text for cleaner display.

    Args:
        text: The full response text

    Returns:
        Response text with confidence line removed
    """
    if not text:
        return text

    # Remove lines containing just the confidence score
    lines = text.split('\n')
    filtered_lines = []
    for line in lines:
        # Skip lines that are just confidence declarations
        stripped = line.strip()
        if re.match(r'^(\*\*)?[Cc]onfidence(\s+score)?(\*\*)?:?\s*\[?\d+\]?\s*$', stripped):
            continue
        filtered_lines.append(line)

    # Remove trailing whitespace/newlines
    result = '\n'.join(filtered_lines).rstrip()
    return result


def calculate_aggregate_confidence(stage1_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate aggregate confidence statistics from Stage 1 results.

    Args:
        stage1_results: Results from Stage 1 with confidence scores

    Returns:
        Dict with confidence statistics:
        - average: Average confidence across all models
        - min: Minimum confidence
        - max: Maximum confidence
        - count: Number of models that provided confidence
        - total_models: Total number of models
        - distribution: Dict mapping score to count
    """
    scores = []
    distribution = {i: 0 for i in range(1, 11)}

    for result in stage1_results:
        confidence = result.get('confidence')
        if confidence is not None:
            scores.append(confidence)
            distribution[confidence] = distribution.get(confidence, 0) + 1

    if not scores:
        return {
            "average": None,
            "min": None,
            "max": None,
            "count": 0,
            "total_models": len(stage1_results),
            "distribution": distribution,
        }

    return {
        "average": round(sum(scores) / len(scores), 2),
        "min": min(scores),
        "max": max(scores),
        "count": len(scores),
        "total_models": len(stage1_results),
        "distribution": distribution,
    }


async def stage1_collect_responses(
    user_query: str,
    system_prompt: str = None,
    use_cot: bool = False,
    models: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.

    Each model is asked to provide a confidence score (1-10) with their response.
    Optionally, models can be asked to provide Chain-of-Thought structured responses.

    Args:
        user_query: The user's question
        system_prompt: Optional system prompt to prepend to all queries
        use_cot: If True, request Chain-of-Thought structured responses
        models: Optional list of specific models to use (for dynamic routing)

    Returns:
        List of dicts with 'model', 'response', 'confidence', and optional
        'reasoning_details', 'cot' (chain-of-thought), plus 'usage' and 'cost' data.
    """
    messages = []

    # Add system prompt if provided
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # Build query with optional CoT and confidence prompts
    query = user_query
    if use_cot:
        query += COT_PROMPT_SUFFIX
    query += CONFIDENCE_PROMPT_SUFFIX
    messages.append({"role": "user", "content": query})

    # Use provided models or get current council models dynamically
    council_models = models if models else get_council_models()
    responses = await query_models_parallel(council_models, messages)

    # Format results, including reasoning_details, confidence, CoT, and cost data
    stage1_results = []
    for model, response in responses.items():
        if response is not None:  # Only include successful responses
            raw_content = response.get('content', '')

            # Parse confidence from response
            confidence = parse_confidence(raw_content)

            # Clean response by removing confidence line
            clean_response = extract_response_without_confidence(raw_content)

            result = {
                "model": model,
                "response": clean_response,
                "confidence": confidence,
                "usage": response.get('usage', {}),
                "cost": response.get('cost', {}),
            }

            # Parse Chain-of-Thought structure if CoT mode was enabled
            if use_cot:
                cot = parse_cot_response(raw_content)
                if cot:
                    result["cot"] = cot
                    # Use conclusion as the clean response for ranking
                    result["response"] = cot["conclusion"]

            # Include reasoning_details if present (for reasoning models like o1, o3)
            reasoning = response.get('reasoning_details')
            if reasoning:
                result["reasoning_details"] = reasoning
            stage1_results.append(result)

    return stage1_results


async def stage1_collect_responses_streaming(
    user_query: str,
    system_prompt: str = None,
    use_cot: bool = False,
    models: List[str] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stage 1: Collect individual responses from all council models with streaming.

    Yields token events as they arrive from each model, then yields complete
    results when all models have finished.

    Args:
        user_query: The user's question
        system_prompt: Optional system prompt to prepend to all queries
        use_cot: If True, request Chain-of-Thought structured responses
        models: Optional list of specific models to use (for dynamic routing)

    Yields:
        Events with types:
        - {'type': 'stage1_token', 'model': str, 'content': str} - Token from a model
        - {'type': 'stage1_reasoning_token', 'model': str, 'content': str} - Reasoning token
        - {'type': 'stage1_model_complete', 'model': str, 'response': str, 'confidence': int|None,
           'reasoning_details': str|None, 'cot': dict|None, 'usage': dict, 'cost': dict} - Single model complete
        - {'type': 'stage1_complete', 'results': list, 'aggregate_confidence': dict} - All models complete
        - {'type': 'stage1_error', 'model': str, 'error': str} - Model error
    """
    messages = []

    # Add system prompt if provided
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # Build query with optional CoT and confidence prompts
    query = user_query
    if use_cot:
        query += COT_PROMPT_SUFFIX
    query += CONFIDENCE_PROMPT_SUFFIX
    messages.append({"role": "user", "content": query})

    # Use provided models or get current council models dynamically
    council_models = models if models else get_council_models()

    # Track partial and complete responses
    partial_responses = {model: "" for model in council_models}
    partial_reasoning = {model: "" for model in council_models}
    completed_results = []
    models_completed = set()

    # Stream from all models in parallel
    async for event in query_models_parallel_streaming(council_models, messages):
        if event["type"] == "token":
            # Accumulate content and yield token event
            model = event["model"]
            partial_responses[model] += event["content"]
            yield {
                "type": "stage1_token",
                "model": model,
                "content": event["content"],
            }

        elif event["type"] == "reasoning_token":
            # Accumulate reasoning and yield reasoning token event
            model = event["model"]
            partial_reasoning[model] += event["content"]
            yield {
                "type": "stage1_reasoning_token",
                "model": model,
                "content": event["content"],
            }

        elif event["type"] == "complete":
            # Model finished - process the complete response
            model = event["model"]
            models_completed.add(model)

            raw_content = event.get("content", "")

            # Parse confidence from response
            confidence = parse_confidence(raw_content)

            # Clean response by removing confidence line
            clean_response = extract_response_without_confidence(raw_content)

            result = {
                "model": model,
                "response": clean_response,
                "confidence": confidence,
                "usage": event.get("usage", {}),
                "cost": event.get("cost", {}),
            }

            # Parse Chain-of-Thought structure if CoT mode was enabled
            if use_cot:
                cot = parse_cot_response(raw_content)
                if cot:
                    result["cot"] = cot
                    # Use conclusion as the clean response for ranking
                    result["response"] = cot["conclusion"]

            # Include reasoning_details if present
            reasoning = event.get("reasoning_details")
            if reasoning:
                result["reasoning_details"] = reasoning

            completed_results.append(result)

            # Yield model complete event
            yield {
                "type": "stage1_model_complete",
                **result,
            }

        elif event["type"] == "error":
            # Model error - yield error event
            yield {
                "type": "stage1_error",
                "model": event["model"],
                "error": event.get("error", "Unknown error"),
            }

    # All models finished - calculate aggregate confidence and yield final event
    aggregate_confidence = calculate_aggregate_confidence(completed_results)

    yield {
        "type": "stage1_complete",
        "results": completed_results,
        "aggregate_confidence": aggregate_confidence,
    }


async def stage3_synthesize_final_streaming(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    model: Optional[str] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stage 3: Chairman synthesizes final response with token streaming.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2
        model: Optional chairman model identifier

    Yields:
        Events with types:
        - {'type': 'stage3_token', 'content': str, 'model': str} - Token from chairman
        - {'type': 'stage3_complete', 'model': str, 'response': str, 'usage': dict, 'cost': dict}
        - {'type': 'stage3_error', 'error': str}
    """
    # Build comprehensive context for chairman
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, accurate, well-crafted answer to the user's original question.

Guidelines:
- Match the user's language: If the user writes in Turkish, respond fluently and naturally in Turkish.
- Match the scale and intent: If the user query is a simple greeting (e.g. "selam", "merhaba", "hello"), brief conversation opener, or simple check, reply warmly, directly, and concisely without unnecessary essays, jargon, or excessive formality.
- For technical, complex, or analytical inquiries, synthesize the council's perspectives into a comprehensive, well-structured final answer using concise bullet points and direct takeaways. Avoid unnecessary fluff.

Provide the final answer:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Get chairman model (provided or current active config)
    chairman_model = model if model else get_chairman_model()

    # Stream from chairman
    async for event in query_model_streaming(chairman_model, messages):
        if event["type"] == "token":
            yield {
                "type": "stage3_token",
                "content": event["content"],
                "model": chairman_model,
            }

        elif event["type"] == "complete":
            yield {
                "type": "stage3_complete",
                "model": chairman_model,
                "response": event.get("content", ""),
                "usage": event.get("usage", {}),
                "cost": event.get("cost", {}),
            }

        elif event["type"] == "error":
            yield {
                "type": "stage3_error",
                "model": chairman_model,
                "error": event.get("error", "Unknown error"),
            }


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    use_cot: bool = False,
    models: Optional[List[str]] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    When CoT mode is enabled, responses include full reasoning structure
    and evaluators are asked to assess reasoning quality in addition to answer quality.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1
        use_cot: If True, include and evaluate Chain-of-Thought reasoning
        models: Optional list of council models to participate in ranking

    Returns:
        Tuple of (rankings list with cost data, label_to_model mapping)
    """
    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    # Create mapping from label to model name
    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    # Build the response text - include CoT structure if enabled
    if use_cot:
        # Include full reasoning structure when available
        responses_text = ""
        for label, result in zip(labels, stage1_results):
            cot = result.get("cot")
            if cot:
                responses_text += f"""Response {label}:

THINKING:
{cot.get('thinking', 'N/A')}

ANALYSIS:
{cot.get('analysis', 'N/A')}

CONCLUSION:
{cot.get('conclusion', result['response'])}

"""
            else:
                responses_text += f"Response {label}:\n{result['response']}\n\n"

        # CoT-aware ranking prompt
        ranking_prompt = f"""You are evaluating different responses to the following question. Each response includes a reasoning process with THINKING, ANALYSIS, and CONCLUSION sections.

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. Evaluate each response individually and concisely (1-2 sentences per response focusing on reasoning and answer quality):
   - **Reasoning Quality**: Is the THINKING section thorough? Does it identify key aspects?
   - **Analysis Depth**: Does the ANALYSIS section consider multiple perspectives and trade-offs?
   - **Conclusion Accuracy**: Is the CONCLUSION well-supported by the reasoning?
   - **Overall Coherence**: Does the reasoning flow logically from thinking to conclusion?
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Now provide your evaluation and ranking:"""
    else:
        # Standard ranking prompt (original behavior)
        responses_text = "\n\n".join([
            f"Response {label}:\n{result['response']}"
            for label, result in zip(labels, stage1_results)
        ])

        ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response concisely (1-2 sentences per response explaining what it does well and what it does poorly).
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from all council models in parallel (use provided models or fallback to dynamic config)
    council_models = models if models else get_council_models()
    responses = await query_models_parallel(council_models, messages)

    # Format results with cost data
    stage2_results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed,
                "usage": response.get('usage', {}),
                "cost": response.get('cost', {}),
            })

    return stage2_results, label_to_model


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2
        model: Optional chairman model identifier

    Returns:
        Dict with 'model', 'response', 'usage', and 'cost' keys
    """
    # Build comprehensive context for chairman
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, accurate, well-crafted answer to the user's original question.

Guidelines:
- Match the user's language: If the user writes in Turkish, respond fluently and naturally in Turkish.
- Match the scale and intent: If the user query is a simple greeting (e.g. "selam", "merhaba", "hello"), brief conversation opener, or simple check, reply warmly, directly, and concisely without unnecessary essays, jargon, or excessive formality.
- For technical, complex, or analytical inquiries, synthesize the council's perspectives into a comprehensive, well-structured final answer using concise bullet points and direct takeaways. Avoid unnecessary fluff.
- For architectural decisions, library comparisons, or strategy evaluations, structure your response clearly:
  ## Verdict: <One clear, decisive conclusion>
  **Recommendation:** <Concrete action items and direct rationale>
  **Dissenting risk:** <The most critical counterargument, tradeoff, or failure mode raised by any seat, or "None material">

Provide the final answer:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model (use provided model or fallback to dynamic config)
    chairman_model = model if model else get_chairman_model()
    response = await query_model(chairman_model, messages)

    if response is None:
        # Fallback if chairman fails
        return {
            "model": chairman_model,
            "response": "Error: Unable to generate final synthesis.",
            "usage": {},
            "cost": {},
        }

    return {
        "model": chairman_model,
        "response": response.get('content', ''),
        "usage": response.get('usage', {}),
        "cost": response.get('cost', {}),
    }


# Consensus detection constants
CONSENSUS_MIN_CONFIDENCE = 7  # Minimum average confidence for consensus
CONSENSUS_MAX_AVG_RANK = 1.5  # Maximum average rank for top model to be consensus
CONSENSUS_MIN_AGREEMENT = 0.8  # Minimum fraction of models ranking top model as #1


def detect_consensus(
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str],
    aggregate_rankings: List[Dict[str, Any]],
    aggregate_confidence: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Detect if there is a clear consensus among council models.

    Consensus is detected when:
    1. The top-ranked model has a very low average rank (close to 1.0)
    2. A high percentage of models ranked the top model as #1
    3. The average confidence is high enough

    Args:
        stage1_results: Results from Stage 1 (individual responses)
        stage2_results: Results from Stage 2 (rankings)
        label_to_model: Mapping from anonymous labels to model names
        aggregate_rankings: Calculated aggregate rankings
        aggregate_confidence: Aggregate confidence stats from Stage 1

    Returns:
        Dict with:
        - is_consensus: bool - Whether consensus was detected
        - consensus_model: str - The model that achieved consensus (if any)
        - consensus_response: str - The response from that model (if any)
        - reason: str - Human-readable explanation
        - metrics: dict - Detailed metrics for the consensus decision
    """
    if not aggregate_rankings or len(aggregate_rankings) == 0:
        return {
            "is_consensus": False,
            "consensus_model": None,
            "consensus_response": None,
            "reason": "No rankings available",
            "metrics": {},
        }

    # Get the top-ranked model
    top_model = aggregate_rankings[0]
    top_model_name = top_model.get("model")
    avg_rank = top_model.get("weighted_average_rank") or top_model.get("average_rank", 99)

    # Count how many models ranked the top model as #1
    model_to_label = {v: k for k, v in label_to_model.items()}
    top_label = model_to_label.get(top_model_name)

    first_place_votes = 0
    total_voters = len(stage2_results)

    for ranking in stage2_results:
        parsed = ranking.get("parsed_ranking", [])
        if parsed and len(parsed) > 0 and parsed[0] == top_label:
            first_place_votes += 1

    agreement_ratio = first_place_votes / total_voters if total_voters > 0 else 0

    # Get average confidence
    avg_confidence = aggregate_confidence.get("average", 0) if aggregate_confidence else 0

    # Check consensus conditions
    is_low_rank = avg_rank <= CONSENSUS_MAX_AVG_RANK
    is_high_agreement = agreement_ratio >= CONSENSUS_MIN_AGREEMENT
    is_high_confidence = avg_confidence >= CONSENSUS_MIN_CONFIDENCE

    is_consensus = is_low_rank and is_high_agreement and is_high_confidence

    # Get the consensus response if consensus detected
    consensus_response = None
    if is_consensus and top_model_name:
        for result in stage1_results:
            if result.get("model") == top_model_name:
                consensus_response = result.get("response", "")
                break

    # Build reason
    reasons = []
    if is_low_rank:
        reasons.append(f"avg rank {avg_rank:.2f} <= {CONSENSUS_MAX_AVG_RANK}")
    else:
        reasons.append(f"avg rank {avg_rank:.2f} > {CONSENSUS_MAX_AVG_RANK}")

    if is_high_agreement:
        reasons.append(f"{first_place_votes}/{total_voters} voted #1 ({agreement_ratio:.0%} >= {CONSENSUS_MIN_AGREEMENT:.0%})")
    else:
        reasons.append(f"only {first_place_votes}/{total_voters} voted #1 ({agreement_ratio:.0%} < {CONSENSUS_MIN_AGREEMENT:.0%})")

    if is_high_confidence:
        reasons.append(f"avg confidence {avg_confidence:.1f} >= {CONSENSUS_MIN_CONFIDENCE}")
    else:
        reasons.append(f"avg confidence {avg_confidence:.1f} < {CONSENSUS_MIN_CONFIDENCE}")

    if is_consensus:
        reason = f"Consensus reached: {', '.join(reasons)}"
    else:
        reason = f"No consensus: {', '.join(reasons)}"

    return {
        "is_consensus": is_consensus,
        "consensus_model": top_model_name if is_consensus else None,
        "consensus_response": consensus_response,
        "reason": reason,
        "metrics": {
            "top_model": top_model_name,
            "average_rank": avg_rank,
            "first_place_votes": first_place_votes,
            "total_voters": total_voters,
            "agreement_ratio": agreement_ratio,
            "average_confidence": avg_confidence,
            "thresholds": {
                "max_avg_rank": CONSENSUS_MAX_AVG_RANK,
                "min_agreement": CONSENSUS_MIN_AGREEMENT,
                "min_confidence": CONSENSUS_MIN_CONFIDENCE,
            },
        },
    }


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order
    """
    import re

    # Look for "FINAL RANKING:" section
    if "FINAL RANKING:" in ranking_text:
        # Extract everything after "FINAL RANKING:"
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Try to extract numbered list format (e.g., "1. Response A")
            # This pattern looks for: number, period, optional space, "Response X"
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                # Extract just the "Response X" part
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

            # Fallback: Extract all "Response X" patterns in order
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    # Fallback: try to find any "Response X" patterns in order
    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names

    Returns:
        List of dicts with model name and average rank, sorted best to worst
    """
    from collections import defaultdict

    # Track positions for each model
    model_positions = defaultdict(list)

    for ranking in stage2_results:
        ranking_text = ranking['ranking']

        # Parse the ranking from the structured format
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    # Calculate average position for each model
    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    # Sort by average rank (lower is better)
    aggregate.sort(key=lambda x: x['average_rank'])

    return aggregate


def calculate_total_costs(
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    stage3_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate total costs across all stages.

    Args:
        stage1_results: Results from Stage 1
        stage2_results: Results from Stage 2
        stage3_result: Result from Stage 3

    Returns:
        Dict with cost summary for each stage and total
    """
    # Collect cost data from each stage
    stage1_costs = [r.get('cost', {}) for r in stage1_results if r.get('cost')]
    stage2_costs = [r.get('cost', {}) for r in stage2_results if r.get('cost')]
    stage3_costs = [stage3_result.get('cost', {})] if stage3_result.get('cost') else []

    # Aggregate costs per stage
    stage1_summary = aggregate_costs(stage1_costs)
    stage2_summary = aggregate_costs(stage2_costs)
    stage3_summary = aggregate_costs(stage3_costs)

    # Calculate grand total
    all_costs = stage1_costs + stage2_costs + stage3_costs
    total_summary = aggregate_costs(all_costs)

    return {
        "stage1": stage1_summary,
        "stage2": stage2_summary,
        "stage3": stage3_summary,
        "total": total_summary,
    }


async def generate_conversation_title(user_query: str) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Args:
        user_query: The first user message

    Returns:
        A short title (3-5 words)
    """
    clean_q = user_query.strip()
    words = clean_q.split()
    if len(words) <= 3 and len(clean_q) <= 30:
        return clean_q.capitalize()

    from .config import OPENROUTER_API_KEY
    title_model = "google/gemini-2.5-flash" if (OPENROUTER_API_KEY and OPENROUTER_API_KEY.strip()) else get_chairman_model()

    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]
    response = await query_model(title_model, messages, timeout=20.0)

    if response is None:
        return " ".join(words[:4])[:40].capitalize() or "New Conversation"

    title = response.get('content', 'New Conversation').strip()

    # Clean up the title - remove quotes, limit length
    title = title.strip('"\'')

    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_full_council(
    user_query: str,
    system_prompt: str = None,
    use_cot: bool = False,
    use_weighted_consensus: bool = True,
    use_early_consensus: bool = False,
    use_dynamic_routing: bool = False,
    council_models: Optional[List[str]] = None,
    chairman_model: Optional[str] = None
) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process.

    Args:
        user_query: The user's question
        system_prompt: Optional system prompt to prepend to all queries
        use_cot: If True, request Chain-of-Thought structured responses
        use_weighted_consensus: If True, weight model votes by historical performance
        use_early_consensus: If True, skip Stage 3 if clear consensus is detected
        use_dynamic_routing: If True, classify question and route to specialized model pool
        council_models: Optional list of council models to participate
        chairman_model: Optional chairman model for Stage 3 synthesis

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
        metadata includes label_to_model, aggregate_rankings, aggregate_confidence, costs, weights_info, consensus_info, and routing_info
    """
    start_time = time.time()

    # Dynamic routing: classify question and select appropriate model pool
    routing_info = None
    routed_models = None

    if use_dynamic_routing:
        all_models = council_models if council_models else get_council_models()
        custom_pools = get_routing_pools()
        routing_info = await router.route_query(user_query, all_models, custom_pools)
        routed_models = routing_info.get("models")

    # Stage 1: Collect individual responses (using routed models if routing is enabled)
    models_for_stage1 = routed_models if use_dynamic_routing else council_models
    stage1_results = await stage1_collect_responses(user_query, system_prompt, use_cot, models_for_stage1)

    # If no models responded successfully, return error
    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "All models failed to respond. Please try again.",
            "usage": {},
            "cost": {},
        }, {}

    # Stage 2: Collect rankings
    stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results, use_cot, models=council_models)

    # Calculate aggregate rankings (weighted or unweighted)
    aggregate_rankings = weights.calculate_weighted_aggregate_rankings(
        stage2_results, label_to_model, use_weights=use_weighted_consensus
    )

    # Calculate aggregate confidence from Stage 1
    aggregate_confidence = calculate_aggregate_confidence(stage1_results)

    # Check for early consensus exit
    consensus_info = None
    early_exit = False

    if use_early_consensus:
        consensus_info = detect_consensus(
            stage1_results,
            stage2_results,
            label_to_model,
            aggregate_rankings,
            aggregate_confidence
        )

        if consensus_info.get("is_consensus"):
            early_exit = True
            # Create a stage3 result from the consensus response
            stage3_result = {
                "model": consensus_info.get("consensus_model"),
                "response": consensus_info.get("consensus_response"),
                "is_consensus": True,
                "consensus_reason": consensus_info.get("reason"),
                "usage": {},  # No chairman usage since we skipped Stage 3
                "cost": {},
            }
        else:
            # No consensus, proceed with Stage 3
            stage3_result = await stage3_synthesize_final(
                user_query,
                stage1_results,
                stage2_results,
                model=chairman_model
            )
    else:
        # Early consensus disabled, always run Stage 3
        stage3_result = await stage3_synthesize_final(
            user_query,
            stage1_results,
            stage2_results,
            model=chairman_model
        )

    # Calculate total costs across all stages
    costs = calculate_total_costs(stage1_results, stage2_results, stage3_result)

    # Calculate query duration
    query_duration_ms = (time.time() - start_time) * 1000

    # Record analytics for performance dashboard
    try:
        analytics.record_query_result(
            stage1_results=stage1_results,
            stage2_results=stage2_results,
            stage3_result=stage3_result,
            aggregate_rankings=aggregate_rankings,
            query_duration_ms=query_duration_ms
        )
    except Exception as e:
        # Don't fail the query if analytics recording fails
        print(f"Warning: Failed to record analytics: {e}")

    # Get weights info for metadata
    weights_info = weights.get_weights_summary() if use_weighted_consensus else None

    # Prepare metadata
    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
        "aggregate_confidence": aggregate_confidence,
        "costs": costs,
        "use_weighted_consensus": use_weighted_consensus,
        "weights_info": weights_info,
        "use_early_consensus": use_early_consensus,
        "consensus_info": consensus_info,
        "early_exit": early_exit,
        "use_dynamic_routing": use_dynamic_routing,
        "routing_info": routing_info,
    }

    return stage1_results, stage2_results, stage3_result, metadata
