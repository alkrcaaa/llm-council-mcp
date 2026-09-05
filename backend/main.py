"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio
import time

from . import storage
from . import config_api
from . import councils
from . import analytics
from . import process_logger as pl
from . import weights
from .council import (
    run_full_council,
    generate_conversation_title,
    stage1_collect_responses,
    stage1_collect_responses_streaming,
    stage2_collect_rankings,
    stage3_synthesize_final,
    stage3_synthesize_final_streaming,
    calculate_aggregate_rankings,
    calculate_aggregate_confidence,
    calculate_total_costs,
    detect_consensus,
)
from .multi_chairman import (
    stage3_multi_chairman_streaming,
    calculate_multi_chairman_costs,
    get_multi_chairman_models,
)
from . import router
from . import escalation
from . import refinement
from . import adversary
from . import debate
from . import decompose
from . import cache
from . import embeddings
from . import ingestion
from . import research

app = FastAPI(title="LLM Council API")

# Enable CORS for local development, including access from other devices
# on the LAN (e.g. http://192.168.x.x:5173) since the frontend is often
# viewed from a machine other than the one running the containers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|(\d{1,3}\.){3}\d{1,3}):(5173|3000)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Active background deliberations registry {conversation_id: asyncio.Task}
ACTIVE_DELIBERATIONS: Dict[str, asyncio.Task] = {}


class DeliberationContext:
    """Manages independent background deliberation worker and SSE subscriber queues."""
    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.task: Optional[asyncio.Task] = None
        self.subscribers: List[asyncio.Queue] = []
        self.history: List[str] = []
        self.done: bool = False

    def add_subscriber(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        for item in self.history:
            q.put_nowait(item)
        if self.done:
            q.put_nowait(None)
        self.subscribers.append(q)
        return q

    def remove_subscriber(self, q: asyncio.Queue):
        if q in self.subscribers:
            self.subscribers.remove(q)

    def broadcast(self, data: Optional[str]):
        if data is not None:
            self.history.append(data)
        for q in list(self.subscribers):
            q.put_nowait(data)


ACTIVE_DELIBERATION_CONTEXTS: Dict[str, DeliberationContext] = {}


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    council_id: Optional[str] = None


class CreateCouncilRequest(BaseModel):
    """Request to create a new custom council profile."""
    name: str
    icon: str = "🏛️"
    description: str = ""
    council_models: List[str]
    chairman_model: str


class UpdateCouncilRequest(BaseModel):
    """Request to update a council profile."""
    name: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    council_models: Optional[List[str]] = None
    chairman_model: Optional[str] = None


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str
    target_workspace: Optional[str] = None  # Optional target workspace project name
    system_prompt: str = None
    council_id: Optional[str] = None  # Optional council override for this deliberation
    council_models: Optional[List[str]] = None  # Optional panelist-list override for this deliberation
    chairman_model: Optional[str] = None  # Optional chairman model override
    verbosity: int = 0  # Process monitor verbosity level (0-3)
    use_cot: bool = False  # Chain-of-Thought mode (request structured reasoning)
    use_multi_chairman: bool = False  # Multi-Chairman mode (ensemble synthesis)
    use_weighted_consensus: bool = True  # Weight model votes by historical performance
    use_early_consensus: bool = False  # Skip Stage 3 if clear consensus is detected
    use_dynamic_routing: bool = False  # Classify question and route to specialized model pool
    use_escalation: bool = False  # Start with cheap models, escalate to expensive ones if confidence is low
    use_refinement: bool = False  # Enable iterative refinement after Stage 3
    refinement_max_iterations: int = 2  # Max refinement iterations (1-5)
    use_adversary: bool = False  # Enable adversarial validation (devil's advocate review)
    use_debate: bool = False  # Enable debate mode (position → critique → rebuttal → judgment)
    include_rebuttal: bool = True  # Include Round 3 rebuttal in debate (default true)
    use_decomposition: bool = False  # Enable sub-question decomposition (map-reduce for complex questions)
    use_cache: bool = False  # Enable semantic response caching (returns similar cached responses)
    cache_similarity_threshold: float = 0.92  # Minimum similarity for cache hit (0.0-1.0)
    use_research: Optional[bool] = None  # Automated technology scouting (None = auto, True = force, False = disable)


class ScoutRequest(BaseModel):
    """Request to scout candidate technologies, libraries, and skills."""
    query: str
    max_candidates: int = 6
    include_github: bool = True
    include_web: bool = True
    include_packages: bool = True
    include_local_skills: bool = True


class UpdateTagsRequest(BaseModel):
    """Request to update tags for a conversation."""
    tags: List[str]


class UpdateConfigRequest(BaseModel):
    """Request to update model configuration."""
    council_models: List[str]
    chairman_model: str


class ConfigResponse(BaseModel):
    """Response containing model configuration."""
    council_models: List[str]
    chairman_model: str


class AvailableModelsResponse(BaseModel):
    """Response containing list of available models."""
    models: List[str]


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    tags: List[str] = []
    message_count: int
    council_id: Optional[str] = None
    council_name: Optional[str] = None
    status: Optional[str] = "idle"
    last_error: Optional[str] = None


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    tags: List[str] = []
    council_id: Optional[str] = None
    council_name: Optional[str] = None
    council_models: Optional[List[str]] = None
    chairman_model: Optional[str] = None
    status: Optional[str] = "idle"
    last_error: Optional[str] = None
    messages: List[Dict[str, Any]]


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations(tag: Optional[str] = Query(None, description="Filter by tag")):
    """List all conversations (metadata only), optionally filtered by tag."""
    if tag:
        return storage.filter_conversations_by_tag(tag)
    return storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation bound to an active or requested council profile."""
    conversation_id = str(uuid.uuid4())
    council_id = request.council_id or councils.get_active_council_id()
    council_obj = councils.get_council_by_id(council_id) or councils.get_active_council()
    conversation = storage.create_conversation(
        conversation_id,
        council_id=council_obj["id"],
        council_name=council_obj["name"],
        council_models=council_obj["council_models"],
        chairman_model=council_obj["chairman_model"],
    )
    return conversation


@app.get("/api/conversations/active")
async def get_active_deliberations():
    """
    Get list of currently running deliberation conversation IDs.
    """
    active_ids = [
        cid for cid, ctx in ACTIVE_DELIBERATION_CONTEXTS.items()
        if ctx.task and not ctx.task.done()
    ]
    for cid, t in ACTIVE_DELIBERATIONS.items():
        if cid not in active_ids and not t.done():
            active_ids.append(cid)
    return {"active_conversations": active_ids}


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation and its messages."""
    success = storage.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "ok", "message": "Conversation deleted"}


@app.put("/api/conversations/{conversation_id}/council")
async def update_conversation_council(conversation_id: str, council_id: str = Body(..., embed=True)):
    """Switch the council profile for an existing conversation."""
    conversation = storage.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    c_obj = councils.get_council_by_id(council_id)
    if not c_obj:
        raise HTTPException(status_code=400, detail="Council profile not found")
    conversation["council_id"] = c_obj["id"]
    conversation["council_name"] = c_obj["name"]
    conversation["council_models"] = c_obj["council_models"]
    conversation["chairman_model"] = c_obj["chairman_model"]
    storage.save_conversation(conversation)
    return conversation


@app.post("/api/conversations/{conversation_id}/abort")
async def abort_deliberation(conversation_id: str):
    """
    Abort an actively running deliberation for a conversation.
    """
    ctx = ACTIVE_DELIBERATION_CONTEXTS.get(conversation_id)
    task = ACTIVE_DELIBERATIONS.get(conversation_id)
    storage.set_conversation_status(conversation_id, "aborted")
    aborted_any = False
    if ctx and ctx.task and not ctx.task.done():
        ctx.task.cancel()
        ACTIVE_DELIBERATION_CONTEXTS.pop(conversation_id, None)
        aborted_any = True
    if task and not task.done():
        task.cancel()
        ACTIVE_DELIBERATIONS.pop(conversation_id, None)
        aborted_any = True
    if aborted_any:
        return {"success": True, "message": "Deliberation successfully aborted"}
    return {"success": True, "message": "No active deliberation task was running or already finished"}


# ============================================================================
# Council Profile Endpoints
# ============================================================================

@app.get("/api/councils")
async def get_councils():
    """List all council profiles (built-in and custom) and the active council."""
    return {
        "councils": councils.get_all_councils(),
        "active_council_id": councils.get_active_council_id(),
    }


@app.get("/api/councils/active")
async def get_current_active_council():
    """Get the currently active council profile."""
    return councils.get_active_council()


@app.post("/api/councils/{council_id}/activate")
async def activate_council_profile(council_id: str):
    """Activate a council profile as current default."""
    target = councils.set_active_council(council_id)
    if not target:
        raise HTTPException(status_code=404, detail="Council profile not found")
    # Also sync global config so non-scoped calls use active council
    try:
        config_api.save_config({
            "council_models": target["council_models"],
            "chairman_model": target["chairman_model"],
        })
    except Exception:
        pass
    return target


@app.post("/api/councils")
async def create_new_council(request: CreateCouncilRequest):
    """Create a new custom council profile."""
    if len(request.council_models) < 2:
        raise HTTPException(status_code=400, detail="At least 2 council models are required")
    if not request.chairman_model:
        raise HTTPException(status_code=400, detail="Chairman model is required")
    created = councils.create_custom_council(
        name=request.name,
        council_models=request.council_models,
        chairman_model=request.chairman_model,
        icon=request.icon,
        description=request.description,
    )
    return created


@app.put("/api/councils/{council_id}")
async def update_council_profile(council_id: str, request: UpdateCouncilRequest):
    """Update an existing council profile."""
    updates = {k: v for k, v in request.dict().items() if v is not None}
    updated = councils.update_council(council_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Council profile not found")
    return updated


@app.delete("/api/councils/{council_id}")
async def delete_council_profile(council_id: str):
    """Delete a custom council profile."""
    success = councils.delete_council(council_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot delete built-in or non-existent council profile")
    return {"status": "ok", "deleted_id": council_id}


@app.put("/api/conversations/{conversation_id}/tags")
async def update_tags(conversation_id: str, request: UpdateTagsRequest):
    """Update tags for a conversation."""
    conversation = storage.update_conversation_tags(conversation_id, request.tags)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "ok", "tags": request.tags}


@app.get("/api/tags")
async def get_all_tags():
    """Get all unique tags across all conversations."""
    return {"tags": storage.get_all_tags()}


@app.get("/api/config", response_model=ConfigResponse)
async def get_config():
    """Get current model configuration."""
    return config_api.load_config()


@app.put("/api/config", response_model=ConfigResponse)
async def update_config(request: UpdateConfigRequest):
    """
    Update model configuration.

    Requires at least 2 council models.
    Configuration is persisted to disk.
    """
    try:
        config = config_api.save_config({
            "council_models": request.council_models,
            "chairman_model": request.chairman_model,
        })
        return config
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/config/reset", response_model=ConfigResponse)
async def reset_config():
    """Reset configuration to defaults."""
    return config_api.reset_to_defaults()


@app.get("/api/config/models", response_model=AvailableModelsResponse)
async def get_available_models():
    """Get list of suggested models for the dropdown."""
    return {"models": config_api.AVAILABLE_MODELS}


@app.get("/api/skills")
async def get_skills():
    """Get list of available domain skills from dev-agent-kit."""
    from backend.skills import get_available_skills
    return {"skills": get_available_skills()}


@app.get("/api/workspaces")
async def get_workspaces():
    """Get list of discoverable local workspace projects for context evaluation."""
    return {"workspaces": ingestion.discover_workspaces()}


# ============================================================================
# Analytics Endpoints
# ============================================================================


@app.get("/api/analytics")
async def get_analytics():
    """
    Get comprehensive model performance statistics.

    Returns statistics for all models including:
    - Win rates (how often each model is ranked #1)
    - Average ranking positions
    - Confidence scores
    - Cost data
    - Token usage

    Returns:
        Dict with 'models' (per-model stats) and 'summary' (aggregate stats)
    """
    return analytics.get_model_statistics()


@app.get("/api/analytics/recent")
async def get_recent_queries(limit: int = Query(default=50, le=200)):
    """
    Get recent query records for detailed analysis.

    Args:
        limit: Maximum number of queries to return (default 50, max 200)

    Returns:
        List of recent query records, newest first
    """
    return {"queries": analytics.get_recent_queries(limit=limit)}


@app.get("/api/analytics/chairman")
async def get_chairman_analytics():
    """
    Get statistics about chairman model usage.

    Returns:
        Dict with 'models' (per-chairman stats) and 'total_syntheses' count
    """
    return analytics.get_chairman_statistics()


@app.delete("/api/analytics")
async def clear_analytics_data():
    """
    Clear all analytics data.

    WARNING: This permanently deletes all recorded statistics.
    Use with caution.
    """
    analytics.clear_analytics()
    return {"status": "ok", "message": "Analytics data cleared"}


# ============================================================================
# Weights Endpoints
# ============================================================================


@app.get("/api/weights")
async def get_model_weights():
    """
    Get current model weights based on historical performance.

    Models with better historical performance (higher win rates, lower average ranks)
    receive higher weights in the weighted consensus voting system.

    Returns:
        Dict with:
        - weights: Per-model weight information
        - has_historical_data: Whether any models have sufficient history
        - models_with_history: Count of models with enough queries
        - weight_range: Min and max weight values
        - explanation: Human-readable summary
    """
    return weights.get_weights_summary()


@app.get("/api/weights/{model}")
async def get_model_weight(model: str):
    """
    Get weight information for a specific model.

    Args:
        model: The model identifier (e.g., "openai/gpt-4o")

    Returns:
        Dict with the model's weight information, or 404 if model not found
    """
    model_weights = weights.get_model_weights([model])
    if model not in model_weights:
        raise HTTPException(status_code=404, detail="Model not found in analytics data")
    return model_weights[model]


# ============================================================================
# Routing Endpoints
# ============================================================================


@app.get("/api/routing/pools")
async def get_routing_pools():
    """
    Get current routing pool configuration.

    Returns model pools optimized for each question category.

    Returns:
        Dict with routing pools per category and category info
    """
    pools = config_api.get_routing_pools()
    return {
        "pools": pools,
        "categories": router.CATEGORY_INFO,
    }


@app.post("/api/routing/classify")
async def classify_question(query: str):
    """
    Classify a question and return routing information.

    This endpoint allows testing the classifier without running a full query.

    Args:
        query: The question to classify

    Returns:
        Routing information including category, confidence, and selected models
    """
    all_models = config_api.get_council_models()
    custom_pools = config_api.get_routing_pools()
    routing_info = await router.route_query(query, all_models, custom_pools)
    return routing_info


# ============================================================================
# Escalation Endpoints
# ============================================================================


@app.get("/api/escalation/tiers")
async def get_escalation_tiers():
    """
    Get current tier configuration for confidence-gated escalation.

    Returns Tier 1 (cheap/fast) and Tier 2 (premium) model pools,
    along with escalation thresholds.

    Returns:
        Dict with tier1_models, tier2_models, thresholds, and descriptions
    """
    return escalation.get_tier_info()


@app.get("/api/escalation/thresholds")
async def get_escalation_thresholds():
    """
    Get current escalation thresholds.

    Returns:
        Dict with confidence_threshold, min_confidence_threshold, agreement_threshold
    """
    return config_api.get_escalation_thresholds()


# ============================================================================
# Refinement Endpoints
# ============================================================================


@app.get("/api/refinement/config")
async def get_refinement_config():
    """
    Get current refinement configuration.

    Returns configuration for iterative refinement including
    default max iterations and convergence thresholds.

    Returns:
        Dict with default_max_iterations, min_critiques_for_revision, etc.
    """
    return refinement.get_refinement_config()


# ============================================================================
# Adversary Endpoints
# ============================================================================


@app.get("/api/adversary/config")
async def get_adversary_config():
    """
    Get current adversarial validation configuration.

    Returns configuration for adversarial review including
    adversary model and severity thresholds.

    Returns:
        Dict with adversary_model, severity_levels, revision_threshold, etc.
    """
    return adversary.get_adversary_config()


# ============================================================================
# Debate Endpoints
# ============================================================================


@app.get("/api/debate/config")
async def get_debate_config():
    """
    Get current debate mode configuration.

    Returns configuration for structured debates including
    round structure and default settings.

    Returns:
        Dict with default_num_rounds, include_rebuttal, round_names, description
    """
    return debate.get_debate_config()


# ============================================================================
# Decomposition Endpoints
# ============================================================================


@app.get("/api/decomposition/config")
async def get_decomposition_config():
    """
    Get current sub-question decomposition configuration.

    Returns configuration for breaking complex questions into
    sub-questions that are answered separately.

    Returns:
        Dict with default_max_sub_questions, complexity_threshold,
        decomposer_model, complexity_indicators, description
    """
    return decompose.get_decomposition_config()


# ============================================================================
# Conversation Endpoints
# ============================================================================


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    storage.set_conversation_status(conversation_id, "deliberating")
    ACTIVE_DELIBERATIONS[conversation_id] = asyncio.current_task()

    try:
        # Ingest and enrich evaluation context if GitHub URLs or workspace references exist
        effective_query, ingest_meta = await ingestion.resolve_evaluation_context(
            request.content,
            target_workspace=request.target_workspace
        )

        # Resolve council models and chairman model for the conversation
        c_target = None
        if request.council_id:
            c_target = councils.get_council_by_id(request.council_id)
        elif conversation and conversation.get("council_id"):
            c_target = councils.get_council_by_id(conversation["council_id"])

        if not c_target:
            c_target = councils.get_active_council()

        if request.council_models:
            active_council_models = list(request.council_models)
            active_chairman_model = request.chairman_model or (c_target.get("chairman_model") if c_target else None) or (conversation.get("chairman_model") if conversation else None)
        elif c_target and c_target.get("council_models"):
            active_council_models = list(c_target["council_models"])
            active_chairman_model = request.chairman_model or c_target.get("chairman_model")
        elif conversation and conversation.get("council_models"):
            active_council_models = list(conversation["council_models"])
            active_chairman_model = request.chairman_model or conversation.get("chairman_model")
        else:
            active_council_models = None
            active_chairman_model = request.chairman_model

        if request.council_models and conversation:
            conversation["council_models"] = active_council_models
            storage.save_conversation(conversation)

        # Automated technology scouting & candidate discovery
        research_meta = {"researched": False}
        if request.use_research is not False:
            is_scout_council = bool((c_target and c_target.get("force_research")) or request.council_id == "tech-scout")
            force_research = request.use_research is True or is_scout_council
            effective_query, research_meta = await research.resolve_research_context(
                effective_query,
                force=force_research
            )

        # Set specialized system prompt for candidate scout council if not provided
        effective_system_prompt = request.system_prompt
        if not effective_system_prompt and ((c_target and c_target.get("id") == "tech-scout") or request.council_id == "tech-scout"):
            effective_system_prompt = (
                "You are the Tech Scout & Radar Council. Your primary objective is to evaluate discovered technology "
                "candidates (GitHub repos, packages, web articles, skills) on production readiness, telemetry, maintenance, "
                "license, and trade-offs. Directly compare the candidates and deliver a clear top recommendation."
            )

        # Run the 3-stage council process
        stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
            effective_query,
            system_prompt=effective_system_prompt,
            use_cot=request.use_cot,
            use_weighted_consensus=request.use_weighted_consensus,
            use_early_consensus=request.use_early_consensus,
            council_models=active_council_models,
            chairman_model=active_chairman_model,
        )
        if ingest_meta.get("enriched"):
            metadata["ingestion"] = ingest_meta
        if research_meta.get("researched"):
            metadata["research"] = research_meta

        # Add assistant message with all stages
        storage.add_assistant_message(
            conversation_id,
            stage1_results,
            stage2_results,
            stage3_result
        )

        # Return the complete response with metadata
        return {
            "stage1": stage1_results,
            "stage2": stage2_results,
            "stage3": stage3_result,
            "metadata": metadata
        }
    except asyncio.CancelledError:
        storage.set_conversation_status(conversation_id, "aborted")
        raise
    except Exception as e:
        storage.set_conversation_status(conversation_id, "error", error=str(e))
        raise
    finally:
        ACTIVE_DELIBERATIONS.pop(conversation_id, None)
        conv = storage.get_conversation(conversation_id)
        if conv and conv.get("status") == "deliberating":
            storage.set_conversation_status(conversation_id, "idle")


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events with token-level streaming for real-time display.

    Event types emitted:
    - routing_start: Dynamic routing classification begins (only if use_dynamic_routing=True)
    - routing_complete: Routing classification finished with category and selected models
    - tier1_start: Tier 1 escalation begins (only if use_escalation=True)
    - tier1_complete: Tier 1 assessment complete with escalation decision
    - escalation_triggered: Escalating to Tier 2 models (includes escalation_info with reasons)
    - tier2_start: Tier 2 escalation begins (only if escalation triggered)
    - stage1_start: Stage 1 begins (includes routing_info if routing enabled, escalation_info if escalation enabled)
    - stage1_token: Token from a council model (includes model identifier and optional tier)
    - stage1_reasoning_token: Reasoning token from a council model
    - stage1_model_complete: A single model has finished responding (includes tier if escalation enabled)
    - stage1_complete: All Stage 1 models have finished
    - stage2_start: Stage 2 begins
    - stage2_complete: Stage 2 finished (rankings don't stream - they're batch)
    - consensus_detected: Early consensus detected, Stage 3 will be skipped
    - stage3_start: Stage 3 begins
    - stage3_token: Token from chairman model
    - stage3_complete: Stage 3 finished
    - refinement_start: Iterative refinement loop beginning (only if use_refinement=True)
    - iteration_start: New refinement iteration beginning
    - critiques_start: Council critique collection starting
    - critique_complete: A single model's critique received
    - critiques_complete: All critiques collected for iteration
    - revision_start: Chairman revision starting
    - revision_token: Token from chairman during revision
    - revision_complete: Revision finished for iteration
    - iteration_complete: Full refinement iteration finished
    - refinement_converged: Refinement stopped early (quality converged)
    - refinement_complete: Refinement loop finished
    - adversary_start: Adversarial validation beginning (only if use_adversary=True)
    - adversary_token: Token from adversary model during review
    - adversary_complete: Adversary review complete (includes has_issues, severity)
    - adversary_revision_start: Chairman revision starting (only if issues found)
    - adversary_revision_token: Token from chairman during revision
    - adversary_revision_complete: Adversary revision complete
    - adversary_validation_complete: Full adversarial validation finished
    - debate_start: Debate mode beginning (only if use_debate=True)
    - round1_start: Position round starting (models stating positions)
    - position_complete: A model's position statement received
    - round1_complete: All positions collected
    - round2_start: Critique round starting (models critiquing other positions)
    - critique_complete: A model's critique received (different from refinement critique)
    - round2_complete: All critiques collected
    - round3_start: Rebuttal round starting (models defending positions)
    - rebuttal_complete: A model's rebuttal received
    - round3_complete: All rebuttals collected
    - judgment_start: Chairman judgment starting
    - judgment_token: Token from chairman during judgment
    - judgment_complete: Chairman judgment finished
    - debate_complete: Full debate finished with all rounds and judgment
    - cache_check_start: Checking semantic cache (only if use_cache=True)
    - cache_hit: Cache hit found (includes similarity, cached_query, cost_saved)
    - cache_miss: No cache hit, proceeding with full council query
    - cache_stored: Response stored in cache (includes cache_id, cache_size)
    - costs_complete: Cost breakdown calculated
    - title_complete: Conversation title generated
    - complete: Full process complete
    - error: An error occurred
    - process: Process monitor event (when verbosity > 0)
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Get verbosity level (clamp to 0-3)
    verbosity = max(0, min(3, request.verbosity))

    def emit_process(event: dict) -> str:
        """Helper to emit a process event if verbosity allows."""
        if pl.should_emit(event.get("level", 0), verbosity):
            return f"data: {json.dumps(event)}\n\n"
        return ""

    async def _execute_deliberation_stream():
        try:
            # Track timing for process events
            stage_start_time = time.time()

            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Ingest and enrich evaluation context if GitHub URLs or workspace references exist
            effective_query, ingest_meta = await ingestion.resolve_evaluation_context(
                request.content,
                target_workspace=request.target_workspace
            )

            if ingest_meta.get("enriched"):
                target_ws = ingest_meta.get("target_workspace")
                ext_repos = ingest_meta.get("external_repos", [])
                repo_names = [r.replace("https://github.com/", "") for r in ext_repos]
                details = []
                if target_ws:
                    details.append(f"Workspace: {target_ws}")
                if repo_names:
                    details.append(f"Repos: {', '.join(repo_names)}")

                proc_event = emit_process(pl.create_process_event(
                    f"Context Ingested: {' | '.join(details)}",
                    pl.EventCategory.INFO,
                    pl.Verbosity.BASIC
                ))
                if proc_event:
                    yield proc_event

                yield f"data: {json.dumps({'type': 'context_ingested', 'metadata': ingest_meta})}\n\n"

            # Get council models for process events
            from .config_api import get_council_models, get_chairman_model, get_routing_pools

            # Resolve council from request override, conversation binding, or active council
            conv_data = storage.get_conversation(conversation_id)
            c_target = None
            if request.council_id:
                c_target = councils.get_council_by_id(request.council_id)
            elif conv_data and conv_data.get("council_id"):
                c_target = councils.get_council_by_id(conv_data["council_id"])

            if not c_target:
                c_target = councils.get_active_council()

            if request.council_models:
                council_models = list(request.council_models)
                chairman_model = request.chairman_model or (c_target.get("chairman_model") if c_target else None) or (conv_data.get("chairman_model") if conv_data else None) or get_chairman_model()
            elif c_target and c_target.get("council_models"):
                council_models = list(c_target["council_models"])
                chairman_model = request.chairman_model or c_target.get("chairman_model") or get_chairman_model()
            elif conv_data and conv_data.get("council_models"):
                council_models = list(conv_data["council_models"])
                chairman_model = request.chairman_model or conv_data.get("chairman_model") or get_chairman_model()
            else:
                council_models = get_council_models()
                chairman_model = request.chairman_model or get_chairman_model()

            # Ensure conversation records council profile info if missing or overridden
            if request.council_models and conv_data:
                conv_data["council_models"] = council_models
                conv_data["chairman_model"] = chairman_model
                storage.save_conversation(conv_data)
            elif conv_data and c_target and not conv_data.get("council_id"):
                conv_data["council_id"] = c_target["id"]
                conv_data["council_name"] = c_target["name"]
                conv_data["council_models"] = council_models
                conv_data["chairman_model"] = chairman_model
                storage.save_conversation(conv_data)

            # Automated technology scouting & candidate discovery
            research_meta = {"researched": False}
            if request.use_research is not False:
                is_scout_council = bool((c_target and c_target.get("force_research")) or request.council_id == "tech-scout")
                force_research = request.use_research is True or is_scout_council
                effective_query, research_meta = await research.resolve_research_context(
                    effective_query,
                    force=force_research
                )

            # Set specialized system prompt for candidate scout council if not provided
            active_system_prompt = request.system_prompt
            if not active_system_prompt and ((c_target and c_target.get("id") == "tech-scout") or request.council_id == "tech-scout"):
                active_system_prompt = (
                    "You are the Tech Scout & Radar Council. Your primary objective is to evaluate discovered technology "
                    "candidates (GitHub repos, packages, web articles, skills) on production readiness, telemetry, maintenance, "
                    "license, and trade-offs. Directly compare the candidates and deliver a clear top recommendation."
                )

            if research_meta.get("researched"):
                c_count = research_meta.get("candidate_count", 0)
                sterms = research_meta.get("search_terms", "")
                proc_event = emit_process(pl.create_process_event(
                    f"Research Discovery: Found {c_count} candidates for '{sterms}'",
                    pl.EventCategory.INFO,
                    pl.Verbosity.BASIC
                ))
                if proc_event:
                    yield proc_event

                yield f"data: {json.dumps({'type': 'research_complete', 'metadata': research_meta})}\n\n"

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # ================================================================
            # CACHE CHECK - Return cached response if similar query found
            # ================================================================
            if request.use_cache:
                # Process event: Cache check starting
                proc_event = emit_process(pl.create_process_event(
                    "Checking semantic cache for similar queries...",
                    pl.EventCategory.INFO,
                    pl.Verbosity.BASIC
                ))
                if proc_event:
                    yield proc_event

                yield f"data: {json.dumps({'type': 'cache_check_start'})}\n\n"

                # Search cache for similar query
                cache_result = await cache.search_cache(
                    query=request.content,
                    system_prompt=request.system_prompt,
                    similarity_threshold=request.cache_similarity_threshold
                )

                if cache_result:
                    # Cache hit! Return cached response
                    cached_response = cache_result.get("response", {})
                    similarity = cache_result.get("similarity", 0)
                    cached_query = cache_result.get("cached_query", "")

                    # Calculate estimated cost saved (from cached metadata)
                    cached_costs = cached_response.get("metadata", {}).get("costs", {})
                    cost_saved = cached_costs.get("total", {}).get("total_cost", 0.0) if cached_costs else 0.0
                    time_saved_ms = int((time.time() - stage_start_time) * 1000) + 3000  # Estimate 3+ seconds saved

                    # Record cache hit
                    cache.record_cache_hit(cost_saved=cost_saved, time_saved_ms=time_saved_ms)

                    # Process event: Cache hit
                    proc_event = emit_process(pl.create_process_event(
                        f"Cache hit! Similarity: {similarity:.1%} - Returning cached response",
                        pl.EventCategory.SUCCESS,
                        pl.Verbosity.BASIC
                    ))
                    if proc_event:
                        yield proc_event

                    # Emit cache hit event with details
                    yield f"data: {json.dumps({'type': 'cache_hit', 'similarity': similarity, 'cached_query': cached_query, 'cache_id': cache_result.get('cache_id'), 'cost_saved': cost_saved, 'time_saved_ms': time_saved_ms})}\n\n"

                    # Emit cached response stages
                    cached_stage1 = cached_response.get("stage1", [])
                    cached_stage2 = cached_response.get("stage2", [])
                    cached_stage3 = cached_response.get("stage3", {})
                    cached_metadata = cached_response.get("metadata", {})

                    # Emit stage events for cached response
                    yield f"data: {json.dumps({'type': 'stage1_complete', 'results': cached_stage1, 'aggregate_confidence': cached_metadata.get('aggregate_confidence'), 'from_cache': True})}\n\n"
                    yield f"data: {json.dumps({'type': 'stage2_complete', 'results': cached_stage2, 'label_to_model': cached_metadata.get('label_to_model'), 'aggregate_rankings': cached_metadata.get('aggregate_rankings'), 'from_cache': True})}\n\n"
                    yield f"data: {json.dumps({'type': 'stage3_complete', 'result': cached_stage3, 'from_cache': True})}\n\n"

                    # Emit costs
                    if cached_costs:
                        yield f"data: {json.dumps({'type': 'costs_complete', 'costs': cached_costs, 'from_cache': True})}\n\n"

                    # Handle title generation
                    if title_task:
                        title = await title_task
                        storage.update_conversation_title(conversation_id, title)
                        yield f"data: {json.dumps({'type': 'title_complete', 'title': title})}\n\n"

                    # Save cached message to conversation
                    storage.add_assistant_message(
                        conversation_id,
                        cached_stage1,
                        cached_stage2,
                        cached_stage3
                    )

                    # Complete
                    yield f"data: {json.dumps({'type': 'complete', 'from_cache': True})}\n\n"
                    return  # Exit early - cache hit handled

                else:
                    # Cache miss - continue with normal flow
                    cache.record_cache_miss()

                    proc_event = emit_process(pl.create_process_event(
                        "Cache miss - Running full council query",
                        pl.EventCategory.INFO,
                        pl.Verbosity.STANDARD
                    ))
                    if proc_event:
                        yield proc_event

                    yield f"data: {json.dumps({'type': 'cache_miss'})}\n\n"

            # ================================================================
            # DEBATE MODE - Alternative flow (bypasses normal council process)
            # ================================================================
            if request.use_debate:
                # Process event: Debate mode starting
                proc_event = emit_process(pl.create_process_event(
                    f"Starting debate mode with {len(council_models)} models",
                    pl.EventCategory.STAGE,
                    pl.Verbosity.BASIC
                ))
                if proc_event:
                    yield proc_event

                # Run the full debate with streaming
                debate_result = None
                async for event in debate.run_debate_streaming(
                    effective_query,
                    include_rebuttal=request.include_rebuttal,
                    council_models=council_models,
                    chairman_model=chairman_model,
                ):
                    event_type = event["type"]

                    if event_type == "debate_start":
                        yield f"data: {json.dumps({'type': 'debate_start', 'models': event['models'], 'chairman': event['chairman'], 'num_rounds': event['num_rounds'], 'model_to_label': event['model_to_label'], 'label_to_model': event['label_to_model']})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Debate starting: {event['num_rounds']} rounds with {len(event['models'])} participants",
                            pl.EventCategory.INFO,
                            pl.Verbosity.STANDARD
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "round1_start":
                        yield f"data: {json.dumps({'type': 'round1_start', 'round': 1, 'name': event['name'], 'model_count': event['model_count']})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Round 1: {event['name']} - {event['model_count']} models stating positions",
                            pl.EventCategory.STAGE,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "position_complete":
                        yield f"data: {json.dumps({'type': 'position_complete', 'model': event['model'], 'label': event['label'], 'position': event['position'], 'cost': event.get('cost', {})})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"{event['label']} stated position",
                            pl.EventCategory.MODEL,
                            pl.Verbosity.STANDARD
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "round1_complete":
                        yield f"data: {json.dumps({'type': 'round1_complete', 'positions': event['positions'], 'total_cost': event['total_cost']})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Round 1 complete: All positions collected",
                            pl.EventCategory.SUCCESS,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "round2_start":
                        yield f"data: {json.dumps({'type': 'round2_start', 'round': 2, 'name': event['name'], 'critique_pairs': event['critique_pairs']})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Round 2: {event['name']} - Models critiquing opponents",
                            pl.EventCategory.STAGE,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "critique_complete":
                        yield f"data: {json.dumps({'type': 'debate_critique_complete', 'critic': event['critic'], 'critic_label': event['critic_label'], 'target': event['target'], 'target_label': event['target_label'], 'critique': event['critique'], 'cost': event.get('cost', {})})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"{event['critic_label']} critiqued {event['target_label']}",
                            pl.EventCategory.MODEL,
                            pl.Verbosity.STANDARD
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "round2_complete":
                        yield f"data: {json.dumps({'type': 'round2_complete', 'critiques': event['critiques'], 'total_cost': event['total_cost']})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Round 2 complete: All critiques collected",
                            pl.EventCategory.SUCCESS,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "round3_start":
                        yield f"data: {json.dumps({'type': 'round3_start', 'round': 3, 'name': event['name'], 'model_count': event['model_count']})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Round 3: {event['name']} - Models defending positions",
                            pl.EventCategory.STAGE,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "rebuttal_complete":
                        yield f"data: {json.dumps({'type': 'rebuttal_complete', 'model': event['model'], 'label': event['label'], 'rebuttal': event['rebuttal'], 'cost': event.get('cost', {})})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"{event['label']} defended position",
                            pl.EventCategory.MODEL,
                            pl.Verbosity.STANDARD
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "round3_complete":
                        yield f"data: {json.dumps({'type': 'round3_complete', 'rebuttals': event['rebuttals'], 'total_cost': event['total_cost']})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Round 3 complete: All rebuttals collected",
                            pl.EventCategory.SUCCESS,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "judgment_start":
                        yield f"data: {json.dumps({'type': 'judgment_start', 'model': event['model']})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Chairman {event['model'].split('/')[-1]} evaluating debate",
                            pl.EventCategory.STAGE,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "judgment_token":
                        yield f"data: {json.dumps({'type': 'judgment_token', 'content': event['content'], 'model': event['model']})}\n\n"

                    elif event_type == "judgment_complete":
                        yield f"data: {json.dumps({'type': 'judgment_complete', 'judgment': event['judgment'], 'model': event['model'], 'cost': event.get('cost', {})})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Chairman judgment complete",
                            pl.EventCategory.SUCCESS,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "judgment_error":
                        yield f"data: {json.dumps({'type': 'judgment_error', 'error': event['error'], 'model': event.get('model')})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Judgment error: {event['error']}",
                            pl.EventCategory.ERROR,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "debate_complete":
                        debate_result = event
                        yield f"data: {json.dumps({'type': 'debate_complete', 'positions': event['positions'], 'critiques': event['critiques'], 'rebuttals': event['rebuttals'], 'judgment': event['judgment'], 'model_to_label': event['model_to_label'], 'label_to_model': event['label_to_model'], 'num_rounds': event['num_rounds'], 'total_cost': event['total_cost']})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Debate complete: {event['num_rounds']} rounds",
                            pl.EventCategory.SUCCESS,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                # Calculate costs for debate
                if debate_result:
                    costs = {
                        "debate": debate_result.get("total_cost", {}),
                        "total": debate_result.get("total_cost", {}),
                    }
                    yield f"data: {json.dumps({'type': 'costs_complete', 'data': costs})}\n\n"

                # Wait for title generation
                if title_task:
                    title = await title_task
                    storage.update_conversation_title(conversation_id, title)
                    yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

                    proc_event = emit_process(pl.title_generated(title))
                    if proc_event:
                        yield proc_event

                # Save debate results as assistant message
                # Structure: stage1=positions, stage2=critiques+rebuttals, stage3=judgment
                if debate_result:
                    stage1_results = [{"model": p["model"], "response": p["position"]} for p in debate_result.get("positions", [])]
                    stage2_results = [{"model": c["critic"], "ranking": c["critique"]} for c in debate_result.get("critiques", [])]
                    stage3_result = {
                        "model": chairman_model,
                        "response": debate_result.get("judgment", ""),
                        "debate_mode": True,
                        "num_rounds": debate_result.get("num_rounds", 3),
                        "rebuttals": debate_result.get("rebuttals", []),
                        "model_to_label": debate_result.get("model_to_label", {}),
                        "label_to_model": debate_result.get("label_to_model", {}),
                    }

                    storage.add_assistant_message(
                        conversation_id,
                        stage1_results,
                        stage2_results,
                        stage3_result
                    )

                # Send completion event
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"
                return  # Exit early - debate mode is complete

            # ================================================================
            # DECOMPOSITION MODE - Alternative flow (map-reduce for complex questions)
            # ================================================================
            if request.use_decomposition:
                # Process event: Decomposition mode starting
                proc_event = emit_process(pl.create_process_event(
                    f"Starting decomposition mode - analyzing question complexity",
                    pl.EventCategory.STAGE,
                    pl.Verbosity.BASIC
                ))
                if proc_event:
                    yield proc_event

                # Run the full decomposition with streaming
                decomposition_result = None
                async for event in decompose.run_decomposition_streaming(
                    effective_query,
                    council_models=council_models,
                    chairman_model=chairman_model,
                ):
                    event_type = event["type"]

                    if event_type == "decomposition_start":
                        yield f"data: {json.dumps({'type': 'decomposition_start', 'question': event['question'], 'council_models': event['council_models'], 'chairman_model': event['chairman_model'], 'max_sub_questions': event['max_sub_questions']})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Analyzing question complexity...",
                            pl.EventCategory.INFO,
                            pl.Verbosity.STANDARD
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "complexity_analyzed":
                        yield f"data: {json.dumps({'type': 'complexity_analyzed', 'should_decompose': event['should_decompose'], 'confidence': event['confidence'], 'reasoning': event['reasoning']})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Complexity: {'Decomposition needed' if event['should_decompose'] else 'Simple question'} (confidence: {event['confidence']:.2f})",
                            pl.EventCategory.INFO,
                            pl.Verbosity.STANDARD
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "decomposition_skip":
                        yield f"data: {json.dumps({'type': 'decomposition_skip', 'reason': event['reason'], 'confidence': event['confidence']})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Question not complex enough for decomposition - using normal flow",
                            pl.EventCategory.INFO,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                        # Fall through to normal council flow
                        break

                    elif event_type == "sub_questions_generated":
                        yield f"data: {json.dumps({'type': 'sub_questions_generated', 'sub_questions': event['sub_questions'], 'count': event['count'], 'cost': event.get('cost', {})})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Generated {event['count']} sub-questions",
                            pl.EventCategory.SUCCESS,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "sub_council_start":
                        yield f"data: {json.dumps({'type': 'sub_council_start', 'sub_index': event['sub_index'], 'sub_question': event['sub_question'], 'total_sub_questions': event['total_sub_questions']})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Sub-question {event['sub_index'] + 1}/{event['total_sub_questions']}: Starting mini-council",
                            pl.EventCategory.STAGE,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "sub_council_response":
                        yield f"data: {json.dumps({'type': 'sub_council_response', 'sub_index': event['sub_index'], 'sub_question': event['sub_question'], 'model': event['model'], 'response': event['response'], 'cost': event.get('cost', {})})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"{event['model'].split('/')[-1]} answered sub-question {event['sub_index'] + 1}",
                            pl.EventCategory.MODEL,
                            pl.Verbosity.VERBOSE
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "sub_council_complete":
                        yield f"data: {json.dumps({'type': 'sub_council_complete', 'sub_index': event['sub_index'], 'sub_question': event['sub_question'], 'best_response': event.get('best_response'), 'model_count': event['model_count'], 'cost': event.get('cost', {})})}\n\n"

                        best_model = event.get('best_response', {}).get('model', 'Unknown')
                        proc_event = emit_process(pl.create_process_event(
                            f"Sub-question {event['sub_index'] + 1} complete - best: {best_model.split('/')[-1]}",
                            pl.EventCategory.SUCCESS,
                            pl.Verbosity.STANDARD
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "all_sub_councils_complete":
                        yield f"data: {json.dumps({'type': 'all_sub_councils_complete', 'sub_results_count': event['sub_results_count'], 'total_responses': event['total_responses']})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"All {event['sub_results_count']} sub-questions answered ({event['total_responses']} total responses)",
                            pl.EventCategory.SUCCESS,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "merge_start":
                        yield f"data: {json.dumps({'type': 'merge_start', 'model': event['model'], 'sub_questions_count': event['sub_questions_count']})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Chairman {event['model'].split('/')[-1]} merging {event['sub_questions_count']} sub-answers",
                            pl.EventCategory.STAGE,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "merge_token":
                        yield f"data: {json.dumps({'type': 'merge_token', 'content': event['content'], 'model': event['model']})}\n\n"

                    elif event_type == "merge_complete":
                        yield f"data: {json.dumps({'type': 'merge_complete', 'content': event['content'], 'model': event['model'], 'cost': event.get('cost', {})})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Merge complete - final response ready",
                            pl.EventCategory.SUCCESS,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "merge_error":
                        yield f"data: {json.dumps({'type': 'merge_error', 'error': event['error'], 'model': event.get('model')})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Merge error: {event['error']}",
                            pl.EventCategory.ERROR,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                    elif event_type == "decomposition_complete":
                        decomposition_result = event
                        yield f"data: {json.dumps({'type': 'decomposition_complete', 'sub_questions': event['sub_questions'], 'sub_results': event['sub_results'], 'final_response': event['final_response'], 'chairman_model': event['chairman_model'], 'total_cost': event['total_cost']})}\n\n"

                        proc_event = emit_process(pl.create_process_event(
                            f"Decomposition complete: {len(event['sub_questions'])} sub-questions merged",
                            pl.EventCategory.SUCCESS,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                # If decomposition completed successfully
                if decomposition_result:
                    # Calculate costs for decomposition
                    costs = {
                        "decomposition": decomposition_result.get("total_cost", {}),
                        "total": decomposition_result.get("total_cost", {}),
                    }
                    yield f"data: {json.dumps({'type': 'costs_complete', 'data': costs})}\n\n"

                    # Wait for title generation
                    if title_task:
                        title = await title_task
                        storage.update_conversation_title(conversation_id, title)
                        yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

                        proc_event = emit_process(pl.title_generated(title))
                        if proc_event:
                            yield proc_event

                    # Save decomposition results as assistant message
                    # Structure: stage1=sub_results, stage2=empty, stage3=merged response
                    sub_results = decomposition_result.get("sub_results", [])
                    stage1_results = [
                        {"model": sr.get("best_model", "Unknown"), "response": sr.get("best_answer", ""), "sub_question": sr.get("sub_question")}
                        for sr in sub_results
                    ]
                    stage2_results = []  # No rankings in decomposition mode
                    stage3_result = {
                        "model": decomposition_result.get("chairman_model", chairman_model),
                        "response": decomposition_result.get("final_response", ""),
                        "decomposition_mode": True,
                        "sub_questions": decomposition_result.get("sub_questions", []),
                        "sub_results": sub_results,
                    }

                    storage.add_assistant_message(
                        conversation_id,
                        stage1_results,
                        stage2_results,
                        stage3_result
                    )

                    # Send completion event
                    yield f"data: {json.dumps({'type': 'complete'})}\n\n"
                    return  # Exit early - decomposition mode is complete

                # If decomposition was skipped, continue to normal council flow below

            # ================================================================
            # NORMAL COUNCIL FLOW (3-stage process)
            # ================================================================

            # Get use_cot setting
            use_cot = request.use_cot

            # Dynamic routing: classify question and select appropriate model pool
            use_dynamic_routing = request.use_dynamic_routing
            routing_info = None
            routed_models = None

            if use_dynamic_routing:
                # Emit routing start event
                yield f"data: {json.dumps({'type': 'routing_start'})}\n\n"

                # Process event: Routing starting
                proc_event = emit_process(pl.create_process_event(
                    "Classifying question for dynamic routing...",
                    pl.EventCategory.INFO,
                    pl.Verbosity.STANDARD
                ))
                if proc_event:
                    yield proc_event

                # Classify the question
                custom_pools = get_routing_pools()
                routing_info = await router.route_query(effective_query, council_models, custom_pools)
                routed_models = routing_info.get("models")

                # Emit routing complete event
                yield f"data: {json.dumps({'type': 'routing_complete', 'data': routing_info})}\n\n"

                # Process event: Routing complete
                category_name = routing_info.get("category", "general").capitalize()
                confidence_pct = int(routing_info.get("confidence", 0) * 100)
                model_count = len(routed_models) if routed_models else 0
                proc_event = emit_process(pl.create_process_event(
                    f"Routed to {category_name} pool ({model_count} models, {confidence_pct}% confidence): {routing_info.get('reasoning', '')}",
                    pl.EventCategory.SUCCESS,
                    pl.Verbosity.STANDARD
                ))
                if proc_event:
                    yield proc_event

                # Use routed models instead of all council models
                council_models = routed_models

            # Confidence-Gated Escalation: Start with Tier 1, escalate to Tier 2 if confidence is low
            use_escalation = request.use_escalation and not use_dynamic_routing  # Routing takes precedence
            escalation_info = None
            escalated = False
            current_tier = None

            if use_escalation:
                # Start with Tier 1 models
                tier1_models = config_api.get_tier1_models()
                tier2_models = config_api.get_tier2_models()
                current_tier = 1

                # Emit tier1_start event
                yield f"data: {json.dumps({'type': 'tier1_start', 'models': tier1_models})}\n\n"

                # Process event: Tier 1 starting
                proc_event = emit_process(pl.create_process_event(
                    f"Tier 1 assessment: {len(tier1_models)} cost-effective models",
                    pl.EventCategory.INFO,
                    pl.Verbosity.STANDARD
                ))
                if proc_event:
                    yield proc_event

                # Use Tier 1 models for initial Stage 1
                council_models = tier1_models

            # Stage 1: Collect responses with streaming
            yield f"data: {json.dumps({'type': 'stage1_start', 'use_cot': use_cot, 'use_dynamic_routing': use_dynamic_routing, 'routing_info': routing_info, 'use_escalation': use_escalation, 'current_tier': current_tier})}\n\n"

            # Process event: Stage 1 starting
            proc_event = emit_process(pl.stage_start(1, "Collect Individual Responses"))
            if proc_event:
                yield proc_event

            # Process event: Querying models in parallel
            proc_event = emit_process(pl.models_queried_parallel(council_models, 1))
            if proc_event:
                yield proc_event

            stage1_results = []
            aggregate_confidence = None
            model_token_counts = {}  # Track token counts for verbose logging
            models_to_use = routed_models if use_dynamic_routing else council_models

            async for event in stage1_collect_responses_streaming(effective_query, active_system_prompt, use_cot, models_to_use):
                if event["type"] == "stage1_token":
                    # Stream individual tokens to frontend
                    token_event = {'type': 'stage1_token', 'model': event['model'], 'content': event['content']}
                    if current_tier:
                        token_event['tier'] = current_tier
                    yield f"data: {json.dumps(token_event)}\n\n"

                    # Track token counts for verbose logging
                    model = event["model"]
                    model_token_counts[model] = model_token_counts.get(model, 0) + 1

                elif event["type"] == "stage1_reasoning_token":
                    # Stream reasoning tokens to frontend
                    reasoning_event = {'type': 'stage1_reasoning_token', 'model': event['model'], 'content': event['content']}
                    if current_tier:
                        reasoning_event['tier'] = current_tier
                    yield f"data: {json.dumps(reasoning_event)}\n\n"

                elif event["type"] == "stage1_model_complete":
                    # A single model has finished - emit event for frontend
                    model_result = {
                        "model": event["model"],
                        "response": event["response"],
                        "confidence": event.get("confidence"),
                        "reasoning_details": event.get("reasoning_details"),
                        "usage": event.get("usage", {}),
                        "cost": event.get("cost", {}),
                    }
                    if current_tier:
                        model_result['tier'] = current_tier
                    yield f"data: {json.dumps({'type': 'stage1_model_complete', 'data': model_result})}\n\n"

                    # Process event: Model completed
                    tokens = event.get("usage", {}).get("completion_tokens")
                    proc_event = emit_process(pl.model_query_complete(event["model"], 1, tokens))
                    if proc_event:
                        yield proc_event

                    # Process event: Confidence parsed (verbose)
                    proc_event = emit_process(pl.confidence_parsed(event["model"], event.get("confidence")))
                    if proc_event:
                        yield proc_event

                elif event["type"] == "stage1_complete":
                    # All models finished
                    stage1_results = event["results"]
                    aggregate_confidence = event["aggregate_confidence"]

                    # Mark results with tier if escalation is enabled
                    if current_tier:
                        for result in stage1_results:
                            result['tier'] = current_tier

                    # Check if escalation is needed (only for Tier 1)
                    if use_escalation and current_tier == 1:
                        # Emit tier1_complete event
                        yield f"data: {json.dumps({'type': 'tier1_complete', 'data': stage1_results, 'metadata': {'aggregate_confidence': aggregate_confidence}})}\n\n"

                        # Check if escalation is needed
                        should_escalate_flag, escalation_info = escalation.should_escalate(aggregate_confidence, stage1_results)

                        if should_escalate_flag:
                            escalated = True

                            # Process event: Escalation triggered
                            reasons = escalation_info.get('reasons', [])
                            proc_event = emit_process(pl.create_process_event(
                                f"Escalation triggered: {'; '.join(reasons[:2])}",
                                pl.EventCategory.WARNING,
                                pl.Verbosity.BASIC
                            ))
                            if proc_event:
                                yield proc_event

                            # Emit escalation_triggered event
                            yield f"data: {json.dumps({'type': 'escalation_triggered', 'data': escalation_info})}\n\n"

                            # Emit tier2_start event
                            yield f"data: {json.dumps({'type': 'tier2_start', 'models': tier2_models})}\n\n"

                            # Process event: Tier 2 starting
                            proc_event = emit_process(pl.create_process_event(
                                f"Tier 2 escalation: {len(tier2_models)} premium models",
                                pl.EventCategory.INFO,
                                pl.Verbosity.STANDARD
                            ))
                            if proc_event:
                                yield proc_event

                            # Save Tier 1 results
                            tier1_results = stage1_results

                            # Run Tier 2 models
                            current_tier = 2
                            tier2_results = []

                            async for tier2_event in stage1_collect_responses_streaming(effective_query, active_system_prompt, use_cot, tier2_models):
                                if tier2_event["type"] == "stage1_token":
                                    token_event = {'type': 'stage1_token', 'model': tier2_event['model'], 'content': tier2_event['content'], 'tier': 2}
                                    yield f"data: {json.dumps(token_event)}\n\n"

                                elif tier2_event["type"] == "stage1_reasoning_token":
                                    reasoning_event = {'type': 'stage1_reasoning_token', 'model': tier2_event['model'], 'content': tier2_event['content'], 'tier': 2}
                                    yield f"data: {json.dumps(reasoning_event)}\n\n"

                                elif tier2_event["type"] == "stage1_model_complete":
                                    model_result = {
                                        "model": tier2_event["model"],
                                        "response": tier2_event["response"],
                                        "confidence": tier2_event.get("confidence"),
                                        "reasoning_details": tier2_event.get("reasoning_details"),
                                        "usage": tier2_event.get("usage", {}),
                                        "cost": tier2_event.get("cost", {}),
                                        "tier": 2,
                                    }
                                    yield f"data: {json.dumps({'type': 'stage1_model_complete', 'data': model_result})}\n\n"

                                    # Process event: Tier 2 model completed
                                    tokens = tier2_event.get("usage", {}).get("completion_tokens")
                                    proc_event = emit_process(pl.model_query_complete(tier2_event["model"], 1, tokens))
                                    if proc_event:
                                        yield proc_event

                                elif tier2_event["type"] == "stage1_complete":
                                    tier2_results = tier2_event["results"]
                                    # Mark Tier 2 results
                                    for result in tier2_results:
                                        result['tier'] = 2

                                    # Merge Tier 1 and Tier 2 results
                                    stage1_results = escalation.merge_tier_results(tier1_results, tier2_results)

                                    # Recalculate aggregate confidence with all results
                                    from .council import calculate_aggregate_confidence
                                    aggregate_confidence = calculate_aggregate_confidence(stage1_results)

                                elif tier2_event["type"] == "stage1_error":
                                    yield f"data: {json.dumps({'type': 'stage1_error', 'model': tier2_event['model'], 'error': tier2_event['error'], 'tier': 2})}\n\n"

                            # Add escalation info to final escalation_info
                            escalation_info['escalated'] = True
                            escalation_info['tier1_model_count'] = len(tier1_results)
                            escalation_info['tier2_model_count'] = len(tier2_results)
                            escalation_info['total_model_count'] = len(stage1_results)
                        else:
                            # No escalation needed
                            escalation_info['escalated'] = False
                            escalation_info['tier1_model_count'] = len(stage1_results)
                            escalation_info['tier2_model_count'] = 0
                            escalation_info['total_model_count'] = len(stage1_results)

                            # Process event: No escalation needed
                            proc_event = emit_process(pl.create_process_event(
                                f"No escalation needed: confidence sufficient",
                                pl.EventCategory.SUCCESS,
                                pl.Verbosity.STANDARD
                            ))
                            if proc_event:
                                yield proc_event

                    # Emit final stage1_complete with all results
                    complete_metadata = {'aggregate_confidence': aggregate_confidence}
                    if use_escalation:
                        complete_metadata['escalation_info'] = escalation_info
                    yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results, 'metadata': complete_metadata})}\n\n"

                    # Process event: Stage 1 complete
                    stage1_duration = (time.time() - stage_start_time) * 1000
                    proc_event = emit_process(pl.stage_complete(1, "Collect Individual Responses", stage1_duration))
                    if proc_event:
                        yield proc_event

                    # Process event: Aggregate confidence
                    if aggregate_confidence and aggregate_confidence.get("average"):
                        proc_event = emit_process(pl.aggregate_confidence_calculated(
                            aggregate_confidence["average"],
                            aggregate_confidence["count"],
                            aggregate_confidence["total_models"]
                        ))
                        if proc_event:
                            yield proc_event

                elif event["type"] == "stage1_error":
                    # Model error - emit but continue with other models
                    yield f"data: {json.dumps({'type': 'stage1_error', 'model': event['model'], 'error': event['error']})}\n\n"

                    # Process event: Model error
                    proc_event = emit_process(pl.model_query_error(event["model"], event["error"]))
                    if proc_event:
                        yield proc_event

            # If no models succeeded, return error
            if not stage1_results:
                yield f"data: {json.dumps({'type': 'error', 'message': 'All models failed to respond'})}\n\n"
                return

            # Stage 2: Collect rankings (not streamed - relatively fast batch operation)
            stage_start_time = time.time()
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"

            # Process event: Stage 2 starting
            proc_event = emit_process(pl.stage_start(2, "Peer Ranking"))
            if proc_event:
                yield proc_event

            # Process event: Anonymizing responses
            proc_event = emit_process(pl.anonymizing_responses(len(stage1_results)))
            if proc_event:
                yield proc_event

            stage2_results, label_to_model = await stage2_collect_rankings(effective_query, stage1_results, use_cot, models=council_models)

            # Calculate aggregate rankings (weighted or unweighted based on request)
            use_weighted = request.use_weighted_consensus
            aggregate_rankings = weights.calculate_weighted_aggregate_rankings(
                stage2_results, label_to_model, use_weights=use_weighted
            )
            weights_info = weights.get_weights_summary() if use_weighted else None

            # Process events: Rankings parsed (verbose)
            for result in stage2_results:
                proc_event = emit_process(pl.ranking_parsed(result["model"], result.get("parsed_ranking", [])))
                if proc_event:
                    yield proc_event

            # Include weights info in stage2 metadata
            stage2_metadata = {
                'label_to_model': label_to_model,
                'aggregate_rankings': aggregate_rankings,
                'use_weighted_consensus': use_weighted,
            }
            if weights_info:
                stage2_metadata['weights_info'] = weights_info
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': stage2_metadata})}\n\n"

            # Process event: Stage 2 complete
            stage2_duration = (time.time() - stage_start_time) * 1000
            proc_event = emit_process(pl.stage_complete(2, "Peer Ranking", stage2_duration))
            if proc_event:
                yield proc_event

            # Process event: Aggregate rankings
            if aggregate_rankings:
                top = aggregate_rankings[0]
                # Use weighted_average_rank if available, otherwise average_rank
                rank_key = "weighted_average_rank" if use_weighted else "average_rank"
                proc_event = emit_process(pl.aggregate_rankings_calculated(top["model"], top.get(rank_key, top["average_rank"])))
                if proc_event:
                    yield proc_event

            # Process event: Weighted consensus info
            if use_weighted and weights_info:
                if weights_info.get("has_historical_data"):
                    proc_event = emit_process(pl.create_process_event(
                        f"Weighted consensus: {weights_info['models_with_history']} models with history, weights {weights_info['weight_range']['min']:.2f}-{weights_info['weight_range']['max']:.2f}",
                        pl.EventCategory.DATA,
                        pl.Verbosity.VERBOSE
                    ))
                else:
                    proc_event = emit_process(pl.create_process_event(
                        "Weighted consensus: No historical data yet (equal weights)",
                        pl.EventCategory.INFO,
                        pl.Verbosity.VERBOSE
                    ))
                if proc_event:
                    yield proc_event

            # Check for early consensus exit
            use_early_consensus = request.use_early_consensus
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

                    # Process event: Consensus detected
                    proc_event = emit_process(pl.create_process_event(
                        f"Early consensus detected: {consensus_info.get('consensus_model')}",
                        pl.EventCategory.SUCCESS,
                        pl.Verbosity.BASIC
                    ))
                    if proc_event:
                        yield proc_event

                    # Emit consensus detected event
                    yield f"data: {json.dumps({'type': 'consensus_detected', 'data': consensus_info})}\n\n"

                    # Create stage3_result from consensus response (no chairman needed)
                    stage3_result = {
                        "model": consensus_info.get("consensus_model"),
                        "response": consensus_info.get("consensus_response"),
                        "is_consensus": True,
                        "consensus_reason": consensus_info.get("reason"),
                        "usage": {},
                        "cost": {},
                    }

                    # Emit stage3_complete with consensus data
                    yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result, 'is_consensus': True, 'consensus_info': consensus_info})}\n\n"

                    # Process event: Stage 3 skipped
                    proc_event = emit_process(pl.create_process_event(
                        "Stage 3 skipped due to early consensus",
                        pl.EventCategory.INFO,
                        pl.Verbosity.STANDARD
                    ))
                    if proc_event:
                        yield proc_event
                else:
                    # Process event: No consensus found
                    proc_event = emit_process(pl.create_process_event(
                        f"No consensus: {consensus_info.get('reason', 'threshold not met')}",
                        pl.EventCategory.INFO,
                        pl.Verbosity.STANDARD
                    ))
                    if proc_event:
                        yield proc_event

            # Stage 3: Synthesize final answer with streaming (if not early exit)
            if not early_exit:
                stage_start_time = time.time()
                use_multi_chairman = request.use_multi_chairman

                if use_multi_chairman:
                    # Multi-Chairman mode: Multiple chairmen synthesize, then supreme chairman selects
                    yield f"data: {json.dumps({'type': 'stage3_start', 'use_multi_chairman': True})}\n\n"

                    # Process event: Stage 3 starting with multi-chairman
                    proc_event = emit_process(pl.stage_start(3, "Multi-Chairman Synthesis"))
                    if proc_event:
                        yield proc_event

                    # Process event: Multi-chairman models
                    multi_chairman_models = get_multi_chairman_models()
                    proc_event = emit_process(pl.create_process_event(
                        f"Multi-chairman pool: {', '.join(multi_chairman_models)}",
                        pl.EventCategory.INFO,
                        pl.Verbosity.STANDARD
                    ))
                    if proc_event:
                        yield proc_event

                    stage3_result = None
                    syntheses = []

                    async for event in stage3_multi_chairman_streaming(effective_query, stage1_results, stage2_results):
                        if event["type"] == "multi_synthesis_start":
                            yield f"data: {json.dumps({'type': 'multi_synthesis_start'})}\n\n"

                        elif event["type"] == "synthesis_complete":
                            # A chairman has finished synthesizing
                            synthesis = {
                                "model": event["model"],
                                "response": event["response"],
                                "usage": event.get("usage", {}),
                                "cost": event.get("cost", {}),
                            }
                            syntheses.append(synthesis)
                            yield f"data: {json.dumps({'type': 'synthesis_complete', 'data': synthesis})}\n\n"

                            # Process event: Chairman synthesis complete
                            proc_event = emit_process(pl.create_process_event(
                                f"Synthesis from {event['model']} complete",
                                pl.EventCategory.SUCCESS,
                                pl.Verbosity.STANDARD
                            ))
                            if proc_event:
                                yield proc_event

                        elif event["type"] == "multi_synthesis_complete":
                            yield f"data: {json.dumps({'type': 'multi_synthesis_complete', 'syntheses': event['syntheses']})}\n\n"

                        elif event["type"] == "selection_start":
                            yield f"data: {json.dumps({'type': 'selection_start'})}\n\n"

                            # Process event: Supreme chairman selection starting
                            chairman_model = get_chairman_model()
                            proc_event = emit_process(pl.create_process_event(
                                f"Supreme chairman ({chairman_model}) evaluating syntheses",
                                pl.EventCategory.MODEL,
                                pl.Verbosity.STANDARD
                            ))
                            if proc_event:
                                yield proc_event

                        elif event["type"] == "selection_token":
                            # Stream tokens from supreme chairman
                            yield f"data: {json.dumps({'type': 'selection_token', 'content': event['content'], 'model': event['model']})}\n\n"

                        elif event["type"] == "selection_complete":
                            result = event["result"]
                            stage3_result = {
                                "model": result["model"],
                                "response": result["response"],
                                "selected_synthesis": result.get("selected_synthesis"),
                                "selection_reasoning": result.get("selection_reasoning"),
                                "syntheses": result.get("syntheses", syntheses),
                                "label_to_model": result.get("label_to_model", {}),
                                "usage": result.get("usage", {}),
                                "cost": result.get("cost", {}),
                            }
                            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result, 'use_multi_chairman': True})}\n\n"

                            # Process event: Stage 3 complete
                            stage3_duration = (time.time() - stage_start_time) * 1000
                            proc_event = emit_process(pl.stage_complete(3, "Multi-Chairman Synthesis", stage3_duration))
                            if proc_event:
                                yield proc_event

                            # Process event: Selection reasoning
                            if result.get("selected_synthesis"):
                                proc_event = emit_process(pl.create_process_event(
                                    f"Selected synthesis from: {result['selected_synthesis']}",
                                    pl.EventCategory.SUCCESS,
                                    pl.Verbosity.VERBOSE
                                ))
                                if proc_event:
                                    yield proc_event

                        elif event["type"] == "selection_error":
                            yield f"data: {json.dumps({'type': 'stage3_error', 'error': event['error']})}\n\n"
                            # Use fallback result with first synthesis
                            if syntheses:
                                stage3_result = syntheses[0]
                            else:
                                stage3_result = {
                                    "model": "unknown",
                                    "response": "Error: Unable to generate synthesis.",
                                    "usage": {},
                                    "cost": {},
                                }

                    # Ensure we have a stage3_result
                    if stage3_result is None:
                        stage3_result = {
                            "model": "unknown",
                            "response": "Error: Stage 3 did not complete.",
                            "usage": {},
                            "cost": {},
                        }

                else:
                    # Standard single chairman mode
                    yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"

                    # Process event: Stage 3 starting
                    proc_event = emit_process(pl.stage_start(3, "Chairman Synthesis"))
                    if proc_event:
                        yield proc_event

                    # Process event: Chairman synthesizing
                    chairman_model = chairman_model or get_chairman_model()
                    proc_event = emit_process(pl.chairman_synthesizing(chairman_model))
                    if proc_event:
                        yield proc_event

                    stage3_result = None

                    async for event in stage3_synthesize_final_streaming(effective_query, stage1_results, stage2_results, model=chairman_model):
                        if event["type"] == "stage3_token":
                            # Stream tokens from chairman
                            yield f"data: {json.dumps({'type': 'stage3_token', 'content': event['content'], 'model': event['model']})}\n\n"

                        elif event["type"] == "stage3_complete":
                            stage3_result = {
                                "model": event["model"],
                                "response": event["response"],
                                "usage": event.get("usage", {}),
                                "cost": event.get("cost", {}),
                            }
                            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

                            # Process event: Stage 3 complete
                            stage3_duration = (time.time() - stage_start_time) * 1000
                            proc_event = emit_process(pl.stage_complete(3, "Chairman Synthesis", stage3_duration))
                            if proc_event:
                                yield proc_event

                        elif event["type"] == "stage3_error":
                            yield f"data: {json.dumps({'type': 'stage3_error', 'error': event['error']})}\n\n"
                            # Use fallback result
                            stage3_result = {
                                "model": event.get("model", "unknown"),
                                "response": "Error: Unable to generate final synthesis.",
                                "usage": {},
                                "cost": {},
                            }

                    # Ensure we have a stage3_result
                    if stage3_result is None:
                        stage3_result = {
                            "model": "unknown",
                            "response": "Error: Stage 3 did not complete.",
                            "usage": {},
                            "cost": {},
                        }

            # Iterative Refinement: critique and revise the synthesis
            use_refinement = request.use_refinement and not early_exit
            refinement_result = None
            refinement_iterations = []

            if use_refinement and stage3_result and stage3_result.get("response"):
                # Clamp max iterations to valid range
                max_iterations = max(1, min(5, request.refinement_max_iterations))

                # Process event: Refinement starting
                proc_event = emit_process(pl.create_process_event(
                    f"Starting iterative refinement (max {max_iterations} iterations)",
                    pl.EventCategory.STAGE,
                    pl.Verbosity.BASIC
                ))
                if proc_event:
                    yield proc_event

                yield f"data: {json.dumps({'type': 'refinement_start', 'max_iterations': max_iterations})}\n\n"

                # Run refinement loop with streaming
                initial_draft = stage3_result.get("response", "")
                refinement_cost = {"prompt_tokens": 0, "completion_tokens": 0, "total": 0}

                async for ref_event in refinement.run_refinement_loop_streaming(
                    question=effective_query,
                    initial_draft=initial_draft,
                    max_iterations=max_iterations,
                ):
                    if ref_event["type"] == "refinement_start":
                        # Already emitted above
                        pass

                    elif ref_event["type"] == "iteration_start":
                        yield f"data: {json.dumps({'type': 'iteration_start', 'iteration': ref_event['iteration']})}\n\n"

                        # Process event: Iteration starting
                        proc_event = emit_process(pl.create_process_event(
                            f"Refinement iteration {ref_event['iteration']} starting",
                            pl.EventCategory.INFO,
                            pl.Verbosity.STANDARD
                        ))
                        if proc_event:
                            yield proc_event

                    elif ref_event["type"] == "critiques_start":
                        yield f"data: {json.dumps({'type': 'critiques_start', 'iteration': ref_event['iteration'], 'model_count': ref_event['model_count']})}\n\n"

                        # Process event: Collecting critiques
                        proc_event = emit_process(pl.create_process_event(
                            f"Collecting critiques from {ref_event['model_count']} models",
                            pl.EventCategory.MODEL,
                            pl.Verbosity.STANDARD
                        ))
                        if proc_event:
                            yield proc_event

                    elif ref_event["type"] == "critique_complete":
                        yield f"data: {json.dumps({'type': 'critique_complete', 'iteration': ref_event['iteration'], 'model': ref_event['model'], 'critique': ref_event['critique'], 'is_substantive': ref_event['is_substantive']})}\n\n"

                        # Process event: Critique received
                        substantive_text = "substantive" if ref_event["is_substantive"] else "non-substantive"
                        proc_event = emit_process(pl.create_process_event(
                            f"Critique from {ref_event['model'].split('/')[-1]}: {substantive_text}",
                            pl.EventCategory.INFO,
                            pl.Verbosity.VERBOSE
                        ))
                        if proc_event:
                            yield proc_event

                    elif ref_event["type"] == "critiques_complete":
                        yield f"data: {json.dumps({'type': 'critiques_complete', 'iteration': ref_event['iteration'], 'substantive_count': ref_event['substantive_count'], 'critiques': ref_event['critiques']})}\n\n"

                        # Process event: Critiques summary
                        proc_event = emit_process(pl.create_process_event(
                            f"Critiques collected: {ref_event['substantive_count']} substantive",
                            pl.EventCategory.DATA,
                            pl.Verbosity.STANDARD
                        ))
                        if proc_event:
                            yield proc_event

                    elif ref_event["type"] == "revision_start":
                        yield f"data: {json.dumps({'type': 'revision_start', 'iteration': ref_event['iteration'], 'model': ref_event['model']})}\n\n"

                        # Process event: Revision starting
                        proc_event = emit_process(pl.create_process_event(
                            f"Chairman revising based on critiques",
                            pl.EventCategory.MODEL,
                            pl.Verbosity.STANDARD
                        ))
                        if proc_event:
                            yield proc_event

                    elif ref_event["type"] == "revision_token":
                        yield f"data: {json.dumps({'type': 'revision_token', 'iteration': ref_event['iteration'], 'content': ref_event['content'], 'model': ref_event['model']})}\n\n"

                    elif ref_event["type"] == "revision_complete":
                        yield f"data: {json.dumps({'type': 'revision_complete', 'iteration': ref_event['iteration'], 'content': ref_event['content'], 'model': ref_event['model']})}\n\n"

                        # Process event: Revision complete
                        proc_event = emit_process(pl.create_process_event(
                            f"Revision complete for iteration {ref_event['iteration']}",
                            pl.EventCategory.SUCCESS,
                            pl.Verbosity.STANDARD
                        ))
                        if proc_event:
                            yield proc_event

                    elif ref_event["type"] == "revision_error":
                        yield f"data: {json.dumps({'type': 'revision_error', 'iteration': ref_event['iteration'], 'error': ref_event['error']})}\n\n"

                        # Process event: Revision error
                        proc_event = emit_process(pl.create_process_event(
                            f"Revision error: {ref_event['error']}",
                            pl.EventCategory.ERROR,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                    elif ref_event["type"] == "iteration_complete":
                        yield f"data: {json.dumps({'type': 'iteration_complete', 'iteration': ref_event['iteration'], 'revision': ref_event['revision']})}\n\n"

                    elif ref_event["type"] == "refinement_converged":
                        yield f"data: {json.dumps({'type': 'refinement_converged', 'iteration': ref_event['iteration'], 'reason': ref_event['reason'], 'final_response': ref_event['final_response']})}\n\n"

                        # Process event: Refinement converged
                        proc_event = emit_process(pl.create_process_event(
                            f"Refinement converged: {ref_event['reason']}",
                            pl.EventCategory.SUCCESS,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                    elif ref_event["type"] == "refinement_complete":
                        refinement_result = ref_event
                        refinement_iterations = ref_event.get("iterations", [])

                        yield f"data: {json.dumps({'type': 'refinement_complete', 'iterations': refinement_iterations, 'final_response': ref_event['final_response'], 'total_iterations': ref_event['total_iterations'], 'converged': ref_event['converged'], 'total_cost': ref_event['total_cost']})}\n\n"

                        # Update stage3_result with refined response
                        stage3_result["response"] = ref_event["final_response"]
                        stage3_result["refinement_applied"] = True
                        stage3_result["refinement_iterations"] = ref_event["total_iterations"]
                        stage3_result["refinement_converged"] = ref_event["converged"]

                        # Track refinement costs
                        refinement_cost = ref_event.get("total_cost", {})

                        # Process event: Refinement complete
                        proc_event = emit_process(pl.create_process_event(
                            f"Refinement complete: {ref_event['total_iterations']} iterations, {'converged' if ref_event['converged'] else 'max iterations'}",
                            pl.EventCategory.SUCCESS,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

            # Adversarial Validation: Have a devil's advocate review the synthesis
            use_adversary = request.use_adversary and not early_exit
            adversary_result = None

            if use_adversary and stage3_result and stage3_result.get("response"):
                current_synthesis = stage3_result.get("response", "")

                # Process event: Adversarial validation starting
                proc_event = emit_process(pl.create_process_event(
                    "Starting adversarial validation (devil's advocate review)",
                    pl.EventCategory.STAGE,
                    pl.Verbosity.BASIC
                ))
                if proc_event:
                    yield proc_event

                adversary_cost = {"prompt_tokens": 0, "completion_tokens": 0, "total": 0}

                async for adv_event in adversary.run_adversarial_validation_streaming(
                    question=effective_query,
                    synthesis=current_synthesis,
                ):
                    if adv_event["type"] == "adversary_start":
                        yield f"data: {json.dumps({'type': 'adversary_start', 'adversary_model': adv_event['adversary_model']})}\n\n"

                        # Process event: Adversary model reviewing
                        proc_event = emit_process(pl.create_process_event(
                            f"Adversary ({adv_event['adversary_model']}) reviewing synthesis",
                            pl.EventCategory.MODEL,
                            pl.Verbosity.STANDARD
                        ))
                        if proc_event:
                            yield proc_event

                    elif adv_event["type"] == "adversary_token":
                        yield f"data: {json.dumps({'type': 'adversary_token', 'model': adv_event['model'], 'content': adv_event['content']})}\n\n"

                    elif adv_event["type"] == "adversary_complete":
                        yield f"data: {json.dumps({'type': 'adversary_complete', 'model': adv_event['model'], 'critique': adv_event['critique'], 'has_issues': adv_event['has_issues'], 'severity': adv_event['severity']})}\n\n"

                        # Process event: Adversary review complete
                        if adv_event["has_issues"]:
                            proc_event = emit_process(pl.create_process_event(
                                f"Issues found ({adv_event['severity']}): revision needed",
                                pl.EventCategory.WARNING,
                                pl.Verbosity.STANDARD
                            ))
                        else:
                            proc_event = emit_process(pl.create_process_event(
                                "No significant issues found",
                                pl.EventCategory.SUCCESS,
                                pl.Verbosity.STANDARD
                            ))
                        if proc_event:
                            yield proc_event

                    elif adv_event["type"] == "adversary_error":
                        yield f"data: {json.dumps({'type': 'adversary_error', 'model': adv_event.get('model'), 'error': adv_event['error']})}\n\n"

                        # Process event: Adversary error
                        proc_event = emit_process(pl.create_process_event(
                            f"Adversary error: {adv_event['error']}",
                            pl.EventCategory.ERROR,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

                    elif adv_event["type"] == "adversary_revision_start":
                        yield f"data: {json.dumps({'type': 'adversary_revision_start', 'chairman_model': adv_event['chairman_model'], 'severity': adv_event['severity']})}\n\n"

                        # Process event: Chairman revising based on adversary feedback
                        proc_event = emit_process(pl.create_process_event(
                            f"Chairman revising based on adversary critique",
                            pl.EventCategory.MODEL,
                            pl.Verbosity.STANDARD
                        ))
                        if proc_event:
                            yield proc_event

                    elif adv_event["type"] == "adversary_revision_token":
                        yield f"data: {json.dumps({'type': 'adversary_revision_token', 'model': adv_event['model'], 'content': adv_event['content']})}\n\n"

                    elif adv_event["type"] == "adversary_revision_complete":
                        yield f"data: {json.dumps({'type': 'adversary_revision_complete', 'model': adv_event['model'], 'response': adv_event['response']})}\n\n"

                        # Process event: Revision complete
                        proc_event = emit_process(pl.create_process_event(
                            "Adversary-triggered revision complete",
                            pl.EventCategory.SUCCESS,
                            pl.Verbosity.STANDARD
                        ))
                        if proc_event:
                            yield proc_event

                    elif adv_event["type"] == "adversary_revision_error":
                        yield f"data: {json.dumps({'type': 'adversary_revision_error', 'model': adv_event.get('model'), 'error': adv_event['error']})}\n\n"

                    elif adv_event["type"] == "adversary_validation_complete":
                        adversary_result = adv_event

                        yield f"data: {json.dumps({'type': 'adversary_validation_complete', 'issues_found': adv_event['issues_found'], 'severity': adv_event['severity'], 'revised': adv_event['revised'], 'final_response': adv_event['final_response']})}\n\n"

                        # Update stage3_result with validated/revised response
                        stage3_result["response"] = adv_event["final_response"]
                        stage3_result["adversary_applied"] = True
                        stage3_result["adversary_issues_found"] = adv_event["issues_found"]
                        stage3_result["adversary_severity"] = adv_event["severity"]
                        stage3_result["adversary_revised"] = adv_event["revised"]

                        # Track adversary costs
                        adversary_cost = adv_event.get("total_cost", {})

                        # Process event: Adversarial validation complete
                        status = "revised" if adv_event["revised"] else ("passed" if not adv_event["issues_found"] else "minor issues noted")
                        proc_event = emit_process(pl.create_process_event(
                            f"Adversarial validation complete: {status}",
                            pl.EventCategory.SUCCESS,
                            pl.Verbosity.BASIC
                        ))
                        if proc_event:
                            yield proc_event

            # Calculate total costs across all stages
            costs = calculate_total_costs(stage1_results, stage2_results, stage3_result)
            yield f"data: {json.dumps({'type': 'costs_complete', 'data': costs})}\n\n"

            # Process event: Total cost
            if costs.get("total", {}).get("total"):
                proc_event = emit_process(pl.total_cost_calculated(costs["total"]["total"]))
                if proc_event:
                    yield proc_event

            # Record analytics for performance dashboard
            try:
                analytics.record_query_result(
                    stage1_results=stage1_results,
                    stage2_results=stage2_results,
                    stage3_result=stage3_result,
                    aggregate_rankings=aggregate_rankings,
                    query_duration_ms=None  # Timing not tracked for streaming
                )
                # Process event: Analytics recorded (verbose)
                proc_event = emit_process(pl.analytics_recorded())
                if proc_event:
                    yield proc_event
            except Exception as analytics_error:
                # Don't fail the query if analytics recording fails
                print(f"Warning: Failed to record analytics: {analytics_error}")

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

                # Process event: Title generated
                proc_event = emit_process(pl.title_generated(title))
                if proc_event:
                    yield proc_event

            # Save complete assistant message
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result
            )

            # Store in cache if caching is enabled
            if request.use_cache:
                try:
                    # Build metadata for cache entry
                    cache_metadata = {
                        "costs": costs,
                        "aggregate_rankings": aggregate_rankings,
                        "label_to_model": label_to_model,
                        "aggregate_confidence": aggregate_confidence if 'aggregate_confidence' in dir() else None,
                    }

                    # Build full response object
                    cache_response = {
                        "stage1": stage1_results,
                        "stage2": stage2_results,
                        "stage3": stage3_result,
                        "metadata": cache_metadata,
                    }

                    # Add to cache
                    cache_entry = await cache.add_cache_entry(
                        query=request.content,
                        response=cache_response,
                        system_prompt=request.system_prompt,
                    )

                    # Process event: Cache entry added
                    proc_event = emit_process(pl.create_process_event(
                        f"Response cached (ID: {cache_entry.get('id', 'unknown')[:16]}...)",
                        pl.EventCategory.INFO,
                        pl.Verbosity.STANDARD
                    ))
                    if proc_event:
                        yield proc_event

                    yield f"data: {json.dumps({'type': 'cache_stored', 'cache_id': cache_entry.get('id'), 'cache_size': cache_entry.get('cache_size')})}\n\n"

                except Exception as cache_error:
                    # Don't fail the query if caching fails
                    print(f"Warning: Failed to cache response: {cache_error}")

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            raise

    # Background deliberation orchestration:
    # Deliberation task is decoupled from the HTTP SSE socket so F5 / client disconnect
    # never cancels the background computation.
    ctx = ACTIVE_DELIBERATION_CONTEXTS.get(conversation_id)
    if not ctx or (ctx.task and ctx.task.done()):
        ctx = DeliberationContext(conversation_id)
        ACTIVE_DELIBERATION_CONTEXTS[conversation_id] = ctx

        async def _background_pump():
            storage.set_conversation_status(conversation_id, "deliberating")
            try:
                async for chunk in _execute_deliberation_stream():
                    ctx.broadcast(chunk)
            except asyncio.CancelledError:
                storage.set_conversation_status(conversation_id, "aborted")
                ctx.broadcast(f"data: {json.dumps({'type': 'aborted', 'message': 'Deliberation aborted by user'})}\n\n")
                raise
            except Exception as exc:
                storage.set_conversation_status(conversation_id, "error", error=str(exc))
                ctx.broadcast(f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n")
            finally:
                ctx.done = True
                ctx.broadcast(None)
                ACTIVE_DELIBERATION_CONTEXTS.pop(conversation_id, None)
                ACTIVE_DELIBERATIONS.pop(conversation_id, None)
                conv = storage.get_conversation(conversation_id)
                if conv and conv.get("status") == "deliberating":
                    storage.set_conversation_status(conversation_id, "idle")

        worker_task = asyncio.create_task(_background_pump())
        ctx.task = worker_task
        ACTIVE_DELIBERATIONS[conversation_id] = worker_task

    async def client_sse_stream():
        q = ctx.add_subscriber()
        try:
            while True:
                chunk = await q.get()
                if chunk is None:
                    break
                yield chunk
        except asyncio.CancelledError:
            # Client disconnected (page reload, F5, tab closed).
            # The background worker_task keeps executing independently!
            pass
        finally:
            ctx.remove_subscriber(q)

    return StreamingResponse(
        client_sse_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============================================================================
# CACHE ENDPOINTS
# ============================================================================


@app.get("/api/cache/config")
async def get_cache_config():
    """
    Get current response cache configuration.

    Returns configuration including similarity threshold, max entries,
    and embedding model used for semantic matching.
    """
    return cache.get_cache_config()


@app.get("/api/cache/info")
async def get_cache_info():
    """
    Get cache information and statistics.

    Returns cache size, hit rate, entries count, and cost savings.
    """
    return cache.get_cache_info()


@app.get("/api/cache/stats")
async def get_cache_stats():
    """
    Get cache hit/miss statistics.

    Returns total queries, cache hits, cache misses, hit rate,
    total cost saved, and total time saved.
    """
    return cache.load_cache_stats()


@app.get("/api/cache/entries")
async def get_cache_entries(
    limit: int = Query(50, description="Maximum entries to return"),
    offset: int = Query(0, description="Number of entries to skip")
):
    """
    Get paginated list of cache entries.

    Returns entries without embeddings (too large), includes query text,
    creation time, hit count, and response preview.
    """
    return cache.get_cache_entries(limit=limit, offset=offset)


@app.delete("/api/cache")
async def clear_cache():
    """
    Clear all cache entries.

    Use with caution - this removes all cached responses.
    """
    return cache.clear_cache()


@app.delete("/api/cache/stats")
async def clear_cache_stats():
    """
    Clear cache statistics.

    Resets hit/miss counts and cost savings tracking.
    """
    return cache.clear_cache_stats()


@app.delete("/api/cache/entries/{cache_id}")
async def delete_cache_entry(cache_id: str):
    """
    Delete a specific cache entry by ID.

    Args:
        cache_id: The ID of the cache entry to delete
    """
    result = cache.delete_cache_entry(cache_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@app.post("/api/cache/search")
async def search_cache_endpoint(
    query: str = Query(..., description="Query text to search for"),
    system_prompt: Optional[str] = Query(None, description="System prompt to match"),
    similarity_threshold: float = Query(0.92, description="Minimum similarity for match")
):
    """
    Search cache for a similar query.

    Returns the cached response if a similar query is found above threshold.
    Useful for testing cache behavior without running a full council query.
    """
    result = await cache.search_cache(
        query=query,
        system_prompt=system_prompt,
        similarity_threshold=similarity_threshold
    )
    if result:
        return {
            "found": True,
            "similarity": result.get("similarity"),
            "cached_query": result.get("cached_query"),
            "cache_id": result.get("cache_id"),
            "created_at": result.get("created_at"),
            "hit_count": result.get("hit_count")
        }
    return {"found": False}


@app.get("/api/embeddings/config")
async def get_embeddings_config():
    """
    Get embedding generation configuration.

    Returns the model used for embeddings, dimensions, and API info.
    """
    return embeddings.get_embedding_config()


@app.post("/api/research/scout")
async def scout_candidates_endpoint(request: ScoutRequest):
    """
    Scout technology, library, or skill candidates across GitHub, web, and local skills.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    return await research.run_research(
        query=request.query.strip(),
        max_candidates=request.max_candidates,
        include_github=request.include_github,
        include_web=request.include_web,
        include_packages=request.include_packages,
        include_local_skills=request.include_local_skills,
    )


@app.get("/api/research/scout")
async def scout_candidates_get_endpoint(
    query: str = Query(..., description="Keywords or technology to search/scout"),
    max_candidates: int = Query(6, description="Max candidate items to return")
):
    """
    GET endpoint to scout technology candidates.
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    return await research.run_research(
        query=query.strip(),
        max_candidates=max_candidates
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
