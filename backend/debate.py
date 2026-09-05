"""Debate Mode for LLM Council.

This module implements multi-round structured debates where:
1. Round 1 (Position): All council models state their initial position/answer
2. Round 2 (Critique): Each model critiques another model's position (anonymized)
3. Round 3 (Rebuttal): Each model defends their position against received critiques
4. Judgment: Chairman evaluates the full debate and synthesizes the best answer

Debates force models to consider alternative viewpoints and defend their reasoning,
resulting in more thoroughly vetted answers.
"""

import random
from typing import List, Dict, Any, Tuple, AsyncGenerator, Optional
from .openrouter import query_models_parallel, query_model, query_model_streaming
from .config_api import get_council_models, get_chairman_model
from .pricing import calculate_cost


# Default configuration for debates
DEFAULT_NUM_ROUNDS = 3  # Position, Critique, Rebuttal
DEFAULT_INCLUDE_REBUTTAL = True  # Whether to include Round 3 rebuttal


# Prompt templates for each debate phase
POSITION_PROMPT_TEMPLATE = """You are participating in a structured debate on the following question:

**Question:** {question}

**Your Task (Round 1 - Position Statement):**
Present your best answer to this question. Be clear, thorough, and well-reasoned.
Support your position with evidence and logical arguments.

**Guidelines:**
- Be direct, structured, and concise (maximum 150-250 words or clear bullet points).
- Avoid conversational preamble or repetitive filler.

State your position:"""


CRITIQUE_PROMPT_TEMPLATE = """You are participating in a structured debate. Another participant has stated the following position:

**Original Question:** {question}

**Position Statement from {opponent_label}:**
{opponent_position}

**Your Task (Round 2 - Critique):**
Critically analyze this position. Identify:
1. **Weaknesses**: What are the flaws, gaps, or errors in this argument?
2. **Missing Considerations**: What important aspects did they overlook?
3. **Counter-arguments**: What evidence or logic contradicts their position?

**Guidelines:**
- Be constructive, sharp, and concise (maximum 150-200 words). Point out real issues, not minor nitpicks.
- Avoid repetitive filler.

Your critique:"""


REBUTTAL_PROMPT_TEMPLATE = """You are participating in a structured debate. You previously stated a position, and now you must defend it.

**Original Question:** {question}

**Your Original Position:**
{your_position}

**Critique Received from {critic_label}:**
{critique}

**Your Task (Round 3 - Rebuttal):**
Defend your position against this critique. You may:
1. **Refute**: Show why the criticisms are invalid or based on misunderstandings
2. **Acknowledge**: Accept valid points and explain how they fit into your position
3. **Strengthen**: Provide additional evidence or reasoning for your original position
4. **Revise**: If the critique has merit, refine your position accordingly

**Guidelines:**
- Keep your defense concise and focused (maximum 150-200 words).

Your rebuttal:"""


JUDGMENT_PROMPT_TEMPLATE = """You are the judge of a structured debate on the following question:

**Question:** {question}

The debate had {num_rounds} rounds. Below is the complete transcript:

{debate_transcript}

**Your Task (Final Judgment):**
Evaluate the debate and determine the best answer to the original question.

1. **Analysis**: Briefly analyze the key arguments and how they held up under criticism
2. **Assessment**: Which positions were strongest and why? Which critiques were most valid?
3. **Synthesis**: Combine the best insights from all participants
4. **Final Answer**: Provide the definitive, actionable answer to the question

Guidelines:
- Match the user's language: If the user writes in Turkish, respond fluently and naturally in Turkish.
- Keep the judgment authoritative, clear, and well-structured using bullet points or concise sections.
- Synthesize directly without re-quoting the entire transcript.

Your judgment:"""


def create_position_prompt(question: str) -> List[Dict[str, str]]:
    """
    Create the prompt for a model to state their initial position.

    Args:
        question: The debate question

    Returns:
        Message list for the position query
    """
    return [
        {
            "role": "system",
            "content": "You are a thoughtful debater. State your position clearly and support it with evidence and reasoning."
        },
        {
            "role": "user",
            "content": POSITION_PROMPT_TEMPLATE.format(question=question)
        }
    ]


def create_critique_prompt(
    question: str,
    opponent_position: str,
    opponent_label: str = "Opponent"
) -> List[Dict[str, str]]:
    """
    Create the prompt for a model to critique another's position.

    Args:
        question: The debate question
        opponent_position: The position being critiqued
        opponent_label: Anonymous label for the opponent (e.g., "Position A")

    Returns:
        Message list for the critique query
    """
    return [
        {
            "role": "system",
            "content": "You are a critical analyst in a debate. Identify genuine weaknesses and missing considerations."
        },
        {
            "role": "user",
            "content": CRITIQUE_PROMPT_TEMPLATE.format(
                question=question,
                opponent_position=opponent_position,
                opponent_label=opponent_label
            )
        }
    ]


def create_rebuttal_prompt(
    question: str,
    your_position: str,
    critique: str,
    critic_label: str = "Critic"
) -> List[Dict[str, str]]:
    """
    Create the prompt for a model to defend their position.

    Args:
        question: The debate question
        your_position: The model's original position
        critique: The critique received
        critic_label: Anonymous label for the critic

    Returns:
        Message list for the rebuttal query
    """
    return [
        {
            "role": "system",
            "content": "You are defending your position in a debate. Be persuasive but intellectually honest."
        },
        {
            "role": "user",
            "content": REBUTTAL_PROMPT_TEMPLATE.format(
                question=question,
                your_position=your_position,
                critique=critique,
                critic_label=critic_label
            )
        }
    ]


def create_judgment_prompt(
    question: str,
    debate_transcript: str,
    num_rounds: int
) -> List[Dict[str, str]]:
    """
    Create the prompt for the chairman to judge the debate.

    Args:
        question: The debate question
        debate_transcript: Full formatted debate transcript
        num_rounds: Number of rounds in the debate

    Returns:
        Message list for the judgment query
    """
    return [
        {
            "role": "system",
            "content": "You are an impartial debate judge. Evaluate arguments fairly and synthesize the best answer."
        },
        {
            "role": "user",
            "content": JUDGMENT_PROMPT_TEMPLATE.format(
                question=question,
                debate_transcript=debate_transcript,
                num_rounds=num_rounds
            )
        }
    ]


def assign_critique_pairs(models: List[str]) -> Dict[str, str]:
    """
    Assign which model critiques which other model's position.

    Uses a rotation so each model critiques exactly one other model,
    and each model is critiqued by exactly one other model.

    Args:
        models: List of model identifiers

    Returns:
        Dict mapping critic model -> target model
    """
    n = len(models)
    if n < 2:
        return {}

    # Simple rotation: each model critiques the next one
    # Model[0] critiques Model[1], Model[1] critiques Model[2], etc.
    pairs = {}
    for i, model in enumerate(models):
        target_idx = (i + 1) % n
        pairs[model] = models[target_idx]

    return pairs


def format_debate_transcript(
    positions: List[Dict[str, Any]],
    critiques: List[Dict[str, Any]],
    rebuttals: List[Dict[str, Any]],
    model_to_label: Dict[str, str]
) -> str:
    """
    Format the full debate into a readable transcript for the judge.

    Args:
        positions: List of position dicts from Round 1
        critiques: List of critique dicts from Round 2
        rebuttals: List of rebuttal dicts from Round 3 (may be empty)
        model_to_label: Mapping of model identifiers to anonymous labels

    Returns:
        Formatted debate transcript string
    """
    lines = []

    # Round 1: Positions
    lines.append("=" * 60)
    lines.append("ROUND 1: POSITION STATEMENTS")
    lines.append("=" * 60)
    for pos in positions:
        label = model_to_label.get(pos["model"], pos["model"])
        lines.append(f"\n**{label}:**")
        lines.append(pos["position"])

    # Round 2: Critiques
    lines.append("\n" + "=" * 60)
    lines.append("ROUND 2: CRITIQUES")
    lines.append("=" * 60)
    for crit in critiques:
        critic_label = model_to_label.get(crit["critic"], crit["critic"])
        target_label = model_to_label.get(crit["target"], crit["target"])
        lines.append(f"\n**{critic_label} critiques {target_label}:**")
        lines.append(crit["critique"])

    # Round 3: Rebuttals (if present)
    if rebuttals:
        lines.append("\n" + "=" * 60)
        lines.append("ROUND 3: REBUTTALS")
        lines.append("=" * 60)
        for reb in rebuttals:
            label = model_to_label.get(reb["model"], reb["model"])
            lines.append(f"\n**{label} responds to criticism:**")
            lines.append(reb["rebuttal"])

    return "\n".join(lines)


async def collect_positions(
    question: str,
    models: Optional[List[str]] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Round 1: Collect initial positions from all models.

    Args:
        question: The debate question
        models: Optional list of models to use

    Returns:
        Tuple of (positions list, total costs)
    """
    if models is None:
        models = get_council_models()

    prompt = create_position_prompt(question)
    results = await query_models_parallel(models, prompt)

    positions = []
    total_cost = {"prompt_tokens": 0, "completion_tokens": 0, "total": 0}

    for model, result in results.items():
        if result and result.get("content"):
            positions.append({
                "model": model,
                "position": result["content"],
                "usage": result.get("usage", {}),
                "cost": result.get("cost", {}),
            })

            # Aggregate costs
            if result.get("cost"):
                total_cost["prompt_tokens"] += result["cost"].get("prompt_tokens", 0)
                total_cost["completion_tokens"] += result["cost"].get("completion_tokens", 0)
                total_cost["total"] += result["cost"].get("total", 0)

    return positions, total_cost


async def collect_critiques(
    question: str,
    positions: List[Dict[str, Any]],
    critique_pairs: Dict[str, str],
    model_to_label: Dict[str, str]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Round 2: Collect critiques from each model about their assigned target.

    Args:
        question: The debate question
        positions: List of position dicts from Round 1
        critique_pairs: Dict mapping critic model -> target model
        model_to_label: Dict mapping models to anonymous labels

    Returns:
        Tuple of (critiques list, total costs)
    """
    # Build position lookup
    position_by_model = {p["model"]: p["position"] for p in positions}

    # Prepare queries for each critic
    queries = []
    for critic, target in critique_pairs.items():
        target_position = position_by_model.get(target, "")
        target_label = model_to_label.get(target, "Opponent")
        prompt = create_critique_prompt(question, target_position, target_label)
        queries.append((critic, target, prompt))

    # Execute queries in parallel
    query_models = [q[0] for q in queries]
    query_prompts = {q[0]: q[2] for q in queries}

    # We need to query each model with its specific prompt
    # Using sequential queries since each has a different prompt
    critiques = []
    total_cost = {"prompt_tokens": 0, "completion_tokens": 0, "total": 0}

    import asyncio

    async def query_critic(critic, target, prompt):
        from .openrouter import query_model
        result = await query_model(critic, prompt)
        return critic, target, result

    tasks = [query_critic(c, t, p) for c, t, p in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            continue
        critic, target, response = result
        if response and response.get("content"):
            critiques.append({
                "critic": critic,
                "target": target,
                "critique": response["content"],
                "usage": response.get("usage", {}),
                "cost": response.get("cost", {}),
            })

            if response.get("cost"):
                total_cost["prompt_tokens"] += response["cost"].get("prompt_tokens", 0)
                total_cost["completion_tokens"] += response["cost"].get("completion_tokens", 0)
                total_cost["total"] += response["cost"].get("total", 0)

    return critiques, total_cost


async def collect_rebuttals(
    question: str,
    positions: List[Dict[str, Any]],
    critiques: List[Dict[str, Any]],
    model_to_label: Dict[str, str]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Round 3: Collect rebuttals from each model defending their position.

    Args:
        question: The debate question
        positions: List of position dicts from Round 1
        critiques: List of critique dicts from Round 2
        model_to_label: Dict mapping models to anonymous labels

    Returns:
        Tuple of (rebuttals list, total costs)
    """
    # Build lookups
    position_by_model = {p["model"]: p["position"] for p in positions}
    critique_by_target = {c["target"]: c for c in critiques}

    import asyncio

    async def query_rebuttal(model, position, critique_data):
        from .openrouter import query_model
        critic_label = model_to_label.get(critique_data["critic"], "Critic")
        prompt = create_rebuttal_prompt(
            question,
            position,
            critique_data["critique"],
            critic_label
        )
        result = await query_model(model, prompt)
        return model, result

    # Prepare rebuttal queries
    tasks = []
    for pos in positions:
        model = pos["model"]
        position = pos["position"]
        critique_data = critique_by_target.get(model)
        if critique_data:
            tasks.append(query_rebuttal(model, position, critique_data))

    rebuttals = []
    total_cost = {"prompt_tokens": 0, "completion_tokens": 0, "total": 0}

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            continue
        model, response = result
        if response and response.get("content"):
            rebuttals.append({
                "model": model,
                "rebuttal": response["content"],
                "usage": response.get("usage", {}),
                "cost": response.get("cost", {}),
            })

            if response.get("cost"):
                total_cost["prompt_tokens"] += response["cost"].get("prompt_tokens", 0)
                total_cost["completion_tokens"] += response["cost"].get("completion_tokens", 0)
                total_cost["total"] += response["cost"].get("total", 0)

    return rebuttals, total_cost


async def synthesize_judgment(
    question: str,
    positions: List[Dict[str, Any]],
    critiques: List[Dict[str, Any]],
    rebuttals: List[Dict[str, Any]],
    model_to_label: Dict[str, str],
    chairman_model: Optional[str] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Final judgment: Chairman evaluates the debate and synthesizes the answer.

    Args:
        question: The debate question
        positions: List of position dicts
        critiques: List of critique dicts
        rebuttals: List of rebuttal dicts
        model_to_label: Dict mapping models to anonymous labels
        chairman_model: Optional chairman model override

    Returns:
        Tuple of (judgment text, cost dict)
    """
    if chairman_model is None:
        chairman_model = get_chairman_model()

    # Format the debate transcript
    transcript = format_debate_transcript(
        positions, critiques, rebuttals, model_to_label
    )

    num_rounds = 3 if rebuttals else 2
    prompt = create_judgment_prompt(question, transcript, num_rounds)

    result = await query_model(chairman_model, prompt)

    if result and result.get("content"):
        return result["content"], result.get("cost", {})

    return "Unable to synthesize judgment.", {}


async def run_debate_streaming(
    question: str,
    include_rebuttal: bool = DEFAULT_INCLUDE_REBUTTAL,
    council_models: Optional[List[str]] = None,
    chairman_model: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Run a full debate with streaming for real-time display.

    Yields events:
    - debate_start: Debate beginning
    - round1_start: Position round starting
    - position_complete: A model's position received
    - round1_complete: All positions collected
    - round2_start: Critique round starting
    - critique_complete: A model's critique received
    - round2_complete: All critiques collected
    - round3_start: Rebuttal round starting (if enabled)
    - rebuttal_complete: A model's rebuttal received
    - round3_complete: All rebuttals collected
    - judgment_start: Chairman judgment starting
    - judgment_token: Token from chairman during judgment
    - judgment_complete: Judgment finished
    - debate_complete: Full debate finished

    Args:
        question: The debate question
        include_rebuttal: Whether to include Round 3 rebuttal
        council_models: Optional council models override
        chairman_model: Optional chairman model override
    """
    if council_models is None:
        council_models = get_council_models()
    if chairman_model is None:
        chairman_model = get_chairman_model()

    # Create anonymous labels for models
    labels = [chr(65 + i) for i in range(len(council_models))]  # A, B, C, ...
    model_to_label = {model: f"Position {label}" for model, label in zip(council_models, labels)}
    label_to_model = {f"Position {label}": model for model, label in zip(council_models, labels)}

    total_cost = {"prompt_tokens": 0, "completion_tokens": 0, "total": 0}
    num_rounds = 3 if include_rebuttal else 2

    yield {
        "type": "debate_start",
        "question": question,
        "models": council_models,
        "chairman": chairman_model,
        "num_rounds": num_rounds,
        "model_to_label": model_to_label,
        "label_to_model": label_to_model,
    }

    # =========================================================================
    # Round 1: Positions
    # =========================================================================
    yield {
        "type": "round1_start",
        "round": 1,
        "name": "Position Statements",
        "model_count": len(council_models),
    }

    positions, round1_cost = await collect_positions(question, council_models)
    total_cost["prompt_tokens"] += round1_cost["prompt_tokens"]
    total_cost["completion_tokens"] += round1_cost["completion_tokens"]
    total_cost["total"] += round1_cost["total"]

    # Emit individual position completions
    for pos in positions:
        yield {
            "type": "position_complete",
            "model": pos["model"],
            "label": model_to_label.get(pos["model"], pos["model"]),
            "position": pos["position"],
            "cost": pos.get("cost", {}),
        }

    yield {
        "type": "round1_complete",
        "positions": positions,
        "total_cost": round1_cost,
    }

    # =========================================================================
    # Round 2: Critiques
    # =========================================================================
    critique_pairs = assign_critique_pairs(council_models)

    yield {
        "type": "round2_start",
        "round": 2,
        "name": "Critiques",
        "critique_pairs": {model_to_label[c]: model_to_label[t] for c, t in critique_pairs.items()},
    }

    critiques, round2_cost = await collect_critiques(
        question, positions, critique_pairs, model_to_label
    )
    total_cost["prompt_tokens"] += round2_cost["prompt_tokens"]
    total_cost["completion_tokens"] += round2_cost["completion_tokens"]
    total_cost["total"] += round2_cost["total"]

    # Emit individual critique completions
    for crit in critiques:
        yield {
            "type": "critique_complete",
            "critic": crit["critic"],
            "critic_label": model_to_label.get(crit["critic"], crit["critic"]),
            "target": crit["target"],
            "target_label": model_to_label.get(crit["target"], crit["target"]),
            "critique": crit["critique"],
            "cost": crit.get("cost", {}),
        }

    yield {
        "type": "round2_complete",
        "critiques": critiques,
        "total_cost": round2_cost,
    }

    # =========================================================================
    # Round 3: Rebuttals (optional)
    # =========================================================================
    rebuttals = []
    if include_rebuttal:
        yield {
            "type": "round3_start",
            "round": 3,
            "name": "Rebuttals",
            "model_count": len(council_models),
        }

        rebuttals, round3_cost = await collect_rebuttals(
            question, positions, critiques, model_to_label
        )
        total_cost["prompt_tokens"] += round3_cost["prompt_tokens"]
        total_cost["completion_tokens"] += round3_cost["completion_tokens"]
        total_cost["total"] += round3_cost["total"]

        # Emit individual rebuttal completions
        for reb in rebuttals:
            yield {
                "type": "rebuttal_complete",
                "model": reb["model"],
                "label": model_to_label.get(reb["model"], reb["model"]),
                "rebuttal": reb["rebuttal"],
                "cost": reb.get("cost", {}),
            }

        yield {
            "type": "round3_complete",
            "rebuttals": rebuttals,
            "total_cost": round3_cost,
        }

    # =========================================================================
    # Judgment: Chairman evaluates
    # =========================================================================
    yield {
        "type": "judgment_start",
        "model": chairman_model,
    }

    # Format transcript for judgment
    transcript = format_debate_transcript(
        positions, critiques, rebuttals, model_to_label
    )

    prompt = create_judgment_prompt(question, transcript, num_rounds)

    judgment_text = ""
    judgment_cost = {}

    try:
        async for event in query_model_streaming(chairman_model, prompt):
            if event["type"] == "token":
                judgment_text += event["content"]
                yield {
                    "type": "judgment_token",
                    "content": event["content"],
                    "model": chairman_model,
                }
            elif event["type"] == "complete":
                judgment_text = event.get("content", judgment_text)
                judgment_cost = event.get("cost", {})

                total_cost["prompt_tokens"] += judgment_cost.get("prompt_tokens", 0)
                total_cost["completion_tokens"] += judgment_cost.get("completion_tokens", 0)
                total_cost["total"] += judgment_cost.get("total", 0)

                yield {
                    "type": "judgment_complete",
                    "judgment": judgment_text,
                    "model": chairman_model,
                    "cost": judgment_cost,
                }
            elif event["type"] == "error":
                yield {
                    "type": "judgment_error",
                    "error": event.get("error", "Unknown error"),
                    "model": chairman_model,
                }
    except Exception as e:
        yield {
            "type": "judgment_error",
            "error": str(e),
            "model": chairman_model,
        }

    # =========================================================================
    # Debate Complete
    # =========================================================================
    yield {
        "type": "debate_complete",
        "positions": positions,
        "critiques": critiques,
        "rebuttals": rebuttals,
        "judgment": judgment_text,
        "model_to_label": model_to_label,
        "label_to_model": label_to_model,
        "num_rounds": num_rounds,
        "total_cost": total_cost,
    }


def get_debate_config() -> Dict[str, Any]:
    """
    Get current debate configuration.

    Returns:
        Dict with default_num_rounds, include_rebuttal, etc.
    """
    return {
        "default_num_rounds": DEFAULT_NUM_ROUNDS,
        "include_rebuttal": DEFAULT_INCLUDE_REBUTTAL,
        "round_names": ["Position Statements", "Critiques", "Rebuttals"],
        "description": "Multi-round structured debate: Position → Critique → Rebuttal → Judgment",
    }
