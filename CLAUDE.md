# CLAUDE.md - Technical Notes for LLM Council

This file contains technical details, architectural decisions, and important implementation notes for future development sessions.

## Project Overview

LLM Council is a 3-stage deliberation system where multiple LLMs collaboratively answer user questions. The key innovation is anonymized peer review in Stage 2, preventing models from playing favorites.

## Architecture

### Backend Structure (`backend/`)

**`config.py`**
- Contains default `COUNCIL_MODELS` (list of OpenRouter model identifiers)
- Contains default `CHAIRMAN_MODEL` (model that synthesizes final answer)
- Uses environment variable `OPENROUTER_API_KEY` from `.env`
- Backend runs on **port 8001** (NOT 8000 - user had another app on 8000)
- Note: These defaults are now overridden by dynamic config in `config_api.py`

**`config_api.py`** - Dynamic Configuration Management
- `load_config()`: Load configuration from JSON file (with defaults fallback)
- `save_config(config)`: Save configuration to JSON file with validation
- `validate_config(config)`: Validate config (minimum 2 models, non-empty strings)
- `get_council_models()`: Get current list of council models (used by council.py)
- `get_chairman_model()`: Get current chairman model (used by council.py)
- `get_multi_chairman_models()`: Get list of multi-chairman models for ensemble synthesis
- `get_routing_pools()`: Get model pools for dynamic routing per question category
- `reset_to_defaults()`: Reset configuration to default values
- `AVAILABLE_MODELS`: List of suggested models for UI dropdown
- Configuration stored in `data/council_config.json`
- Configuration includes `multi_chairman_models` list for multi-chairman synthesis
- Configuration includes `routing_pools` dict mapping categories to model lists
- Configuration includes `tier1_models` list for escalation Tier 1 (fast/cheap)
- Configuration includes `tier2_models` list for escalation Tier 2 (premium)
- Configuration includes escalation thresholds: `escalation_confidence_threshold`, `escalation_min_confidence_threshold`, `escalation_agreement_threshold`
- `get_tier1_models()`: Get Tier 1 models for escalation
- `get_tier2_models()`: Get Tier 2 models for escalation
- `get_escalation_thresholds()`: Get escalation threshold configuration

**`escalation.py`** - Confidence-Gated Escalation Module
- Implements tiered model selection based on confidence and agreement levels
- Queries start with cheaper Tier 1 models and escalate to expensive Tier 2 models only if confidence is low
- **Escalation Triggers** (any triggers escalation):
  - Average confidence below threshold (default: 6.0)
  - Any model confidence below minimum threshold (default: 4)
  - First-place agreement ratio below threshold (default: 50%)
- `get_tier1_models()`: Get Tier 1 (fast/cheap) models from config
- `get_tier2_models()`: Get Tier 2 (premium) models from config
- `get_escalation_thresholds()`: Get current thresholds from config
- `should_escalate(aggregate_confidence, stage1_results, stage2_results, label_to_model)`:
  - Determines if escalation to Tier 2 is needed based on Tier 1 results
  - Returns tuple: (should_escalate, escalation_info)
  - escalation_info contains: reasons, metrics, triggers
- `merge_tier_results(tier1_results, tier2_results)`:
  - Combines Tier 1 and Tier 2 results into single list
  - Marks each result with its tier for display
- `get_tier_info()`: Get tier configuration info for display
  - Returns: tier1_models, tier2_models, thresholds, descriptions, escalation_rules
- `TIER_INFO`: Display info per tier (name, label, description, color)

**`refinement.py`** - Iterative Refinement Loop Module
- Implements critique-and-revise cycles where council critiques chairman's synthesis
- Chairman revises based on valid critiques until quality converges
- **Refinement Flow**:
  1. Chairman generates initial synthesis (Stage 3)
  2. Council models critique the synthesis (identify issues, suggest improvements)
  3. Chairman revises based on substantive critiques
  4. Repeat until converged or max iterations reached
- **Convergence Detection**:
  - Tracks "substantive" vs "non-substantive" critiques
  - Non-substantive critiques contain only praise (e.g., "looks good", "well done")
  - Converges when fewer than `min_critiques_for_revision` substantive critiques
- **Configuration Constants**:
  - `DEFAULT_MAX_ITERATIONS`: 2 (max critique-revise cycles)
  - `DEFAULT_MIN_CRITIQUES_FOR_REVISION`: 2 (minimum substantive critiques to continue)
  - `NON_SUBSTANTIVE_PHRASES`: List of phrases indicating positive feedback
- `is_substantive_critique(text)`: Determines if critique has actionable feedback
- `count_substantive_critiques(critiques)`: Count substantive critiques in list
- `create_critique_prompt(question, draft)`: Generate critique request for council
- `create_revision_prompt(question, draft, critiques)`: Generate revision request for chairman
- `collect_critiques(question, draft, models)`: Parallel query council for critiques
  - Returns tuple: (critiques list, total cost dict)
- `generate_revision(question, draft, critiques, chairman)`: Generate revised synthesis
  - Returns tuple: (revised text, cost dict)
- `generate_revision_streaming(question, draft, critiques, chairman)`: Streaming version
  - Yields events: `revision_token`, `revision_complete`, `revision_error`
- `run_refinement_loop(question, initial_draft, max_iterations, ...)`: Non-streaming version
  - Returns dict with: iterations, final_response, total_iterations, total_cost, converged
- `run_refinement_loop_streaming(question, initial_draft, max_iterations, ...)`: Streaming version
  - Yields events: `refinement_start`, `iteration_start`, `critiques_start`, `critique_complete`,
    `critiques_complete`, `revision_start`, `revision_token`, `revision_complete`,
    `iteration_complete`, `refinement_converged`, `refinement_complete`
- `get_refinement_config()`: Get current refinement configuration

**`adversary.py`** - Adversarial Validation Module
- Implements "devil's advocate" review where an adversary model critiques the chairman's synthesis
- If significant issues are found, the chairman revises the response
- **Adversarial Validation Flow**:
  1. Chairman generates synthesis (Stage 3 or post-refinement)
  2. Adversary model reviews synthesis for flaws, errors, biases, weaknesses
  3. Adversary assigns severity level (critical, major, minor, none)
  4. If severity is critical or major, chairman revises based on critique
  5. Final response is either original (if no issues) or revised version
- **Severity Levels**:
  - `SEVERITY_CRITICAL`: Fundamental flaws requiring immediate revision
  - `SEVERITY_MAJOR`: Significant issues that should be addressed
  - `SEVERITY_MINOR`: Small issues that don't warrant revision
  - `SEVERITY_NONE`: No issues found, synthesis is validated
- **Configuration Constants**:
  - `DEFAULT_ADVERSARY_MODEL`: `google/gemini-2.0-flash-001` (fast, critical reviewer)
  - `NO_ISSUES_PHRASES`: Phrases indicating no problems found ("no issues", "well-structured", etc.)
  - `REVISION_THRESHOLD`: List of severities that trigger revision (`critical`, `major`)
- `has_genuine_issues(critique)`: Determines if critique contains real issues vs praise
  - Uses pattern matching for no-issue phrases
  - Returns boolean indicating if issues exist
- `parse_severity(critique)`: Extracts severity level from critique text
  - Searches for "SEVERITY: X" pattern
  - Returns one of: critical, major, minor, none
- `create_adversary_prompt(question, synthesis)`: Generate review request for adversary
  - Instructs adversary to act as devil's advocate
  - Requests specific format: Issues, SEVERITY, Recommendations
- `create_revision_prompt(question, synthesis, critique)`: Generate revision request for chairman
  - Includes original synthesis and adversary's critique
  - Instructs chairman to address identified issues
- `run_adversarial_validation_streaming(question, synthesis, adversary_model, chairman_model)`:
  - Main streaming function for adversarial validation
  - Yields events: `adversary_start`, `adversary_token`, `adversary_complete`,
    `adversary_revision_start`, `adversary_revision_token`, `adversary_revision_complete`,
    `adversary_validation_complete`
  - Returns final state with: critique, has_issues, severity, revised, revision, adversary_model
- `get_adversary_config()`: Get current adversary configuration for API

**`debate.py`** - Debate Mode Module
- Implements multi-round structured debates where models argue positions and critique each other
- **Alternative Flow**: When debate mode is enabled, it bypasses the normal 3-stage council process entirely
- **Debate Flow**:
  1. Round 1 (Position): All council models state their initial answer/position on the question
  2. Round 2 (Critique): Each model critiques another model's position (anonymized labels A, B, C...)
  3. Round 3 (Rebuttal): Each model defends their position against critiques received (optional, configurable)
  4. Judgment: Chairman evaluates the full debate transcript and synthesizes the best answer
- **Configuration Constants**:
  - `DEFAULT_NUM_ROUNDS`: 3 (includes rebuttal round)
  - `DEFAULT_INCLUDE_REBUTTAL`: True (whether to include Round 3)
- **Prompt Templates**:
  - `POSITION_PROMPT_TEMPLATE`: Asks model for clear, well-reasoned position
  - `CRITIQUE_PROMPT_TEMPLATE`: Asks model to critique another position (anonymized)
  - `REBUTTAL_PROMPT_TEMPLATE`: Asks model to defend position against critique
  - `JUDGMENT_PROMPT_TEMPLATE`: Asks chairman to evaluate debate and synthesize best answer
- **Critique Pairing**: Uses rotation system where each model critiques the next
  - Model 0 critiques Model 1's position, Model 1 critiques Model 2's, etc.
  - Last model critiques first model's position (circular)
  - `get_critique_pairs(models)`: Returns list of (critic_model, target_model, target_label) tuples
- **Helper Functions**:
  - `format_debate_transcript(positions, critiques, rebuttals, label_to_model, include_rebuttal)`:
    - Formats complete debate for chairman's judgment
    - Returns formatted string with all rounds
  - `get_debate_config()`: Returns configuration for API
- **Main Orchestration**:
  - `run_debate_streaming(question, include_rebuttal, council_models, chairman_model)`:
    - Orchestrates complete debate flow with real-time streaming
    - Yields events for each phase (positions, critiques, rebuttals, judgment)
    - Returns final result with full debate transcript and judgment
- **SSE Event Types**:
  - `debate_start`: Debate beginning (includes models, num_rounds, include_rebuttal)
  - `round1_start`: Position round beginning
  - `position_complete`: Model finished stating position
  - `round1_complete`: All positions collected
  - `round2_start`: Critique round beginning
  - `critique_complete`: Model finished critiquing
  - `round2_complete`: All critiques collected
  - `round3_start`: Rebuttal round beginning (only if include_rebuttal=True)
  - `rebuttal_complete`: Model finished rebuttal
  - `round3_complete`: All rebuttals collected
  - `judgment_start`: Chairman evaluation beginning
  - `judgment_token`: Token from chairman during judgment
  - `judgment_complete`: Judgment finished
  - `debate_complete`: Full debate process complete

**`decompose.py`** - Sub-Question Decomposition Module
- Implements map-reduce pattern: complex questions split into sub-questions, each answered by mini-councils
- **Alternative Flow**: When decomposition mode is enabled and question is complex enough, bypasses normal 3-stage process
- **Decomposition Flow**:
  1. Complexity Detection: LLM + keyword heuristics determine if question needs decomposition
  2. Decomposition: Complex question split into 2-5 simpler sub-questions
  3. Sub-Council: All council models answer each sub-question (mini Stage 1)
  4. Best Selection: Best answer selected for each sub-question (highest confidence)
  5. Merge: Chairman merges all best sub-answers into comprehensive final response
- **Configuration Constants**:
  - `DEFAULT_MAX_SUB_QUESTIONS`: 5 (maximum sub-questions to generate)
  - `DEFAULT_MIN_SUB_QUESTIONS`: 2 (minimum sub-questions required)
  - `COMPLEXITY_THRESHOLD`: 0.6 (confidence threshold for decomposition)
  - `DECOMPOSER_MODEL`: `google/gemini-2.0-flash-001` (fast model for decomposition tasks)
- **Prompt Templates**:
  - `COMPLEXITY_DETECTION_PROMPT`: Analyzes if question is complex enough
  - `DECOMPOSITION_PROMPT`: Generates sub-questions from complex question
  - `SUB_QUESTION_PROMPT`: Answers individual sub-questions
  - `MERGE_PROMPT`: Merges sub-answers into final comprehensive response
- **Complexity Detection**:
  - `COMPLEXITY_KEYWORDS`: Lists of keywords indicating complex questions
  - `has_complexity_keywords(text)`: Quick heuristic check for complexity indicators
  - `detect_complexity(question)`: LLM-based complexity analysis with confidence
    - Returns tuple: (is_complex bool, confidence float, reasoning string)
- **Main Functions**:
  - `decompose_question(question, max_sub_questions)`: Generate sub-questions from complex question
    - Uses DECOMPOSER_MODEL for efficiency
    - Returns list of sub-question strings
  - `run_sub_council(sub_question, council_models)`: Run mini-council for one sub-question
    - All models answer the sub-question
    - Returns best answer (highest confidence) with model info
  - `merge_sub_answers(question, sub_questions, sub_answers, chairman_model)`: Merge sub-answers
    - Chairman synthesizes comprehensive response from all sub-answers
    - Returns merged response string
  - `merge_sub_answers_streaming(question, sub_questions, sub_answers, chairman_model)`:
    - Streaming version of merge
    - Yields `merge_token`, `merge_complete`, `merge_error` events
  - `run_decomposition_streaming(question, council_models, chairman_model, max_sub_questions)`:
    - Main orchestration function for complete decomposition flow
    - Yields events for all phases (complexity, decomposition, sub-councils, merge)
- **SSE Event Types**:
  - `decomposition_start`: Decomposition mode beginning
  - `complexity_analyzed`: Complexity detection complete (includes is_complex, confidence, reasoning)
  - `decomposition_skip`: Question not complex enough, falling through to normal council
  - `sub_questions_generated`: Sub-questions created (includes sub_questions array, count)
  - `sub_council_start`: Beginning to process a sub-question (includes index)
  - `sub_council_response`: A model responded to sub-question
  - `sub_council_complete`: Sub-question fully answered (includes index, sub_question, best_answer, best_model)
  - `all_sub_councils_complete`: All sub-questions answered (includes results array)
  - `merge_start`: Chairman beginning to merge (includes chairman_model)
  - `merge_token`: Token from chairman during merge
  - `merge_complete`: Merge finished (includes response)
  - `decomposition_complete`: Full decomposition complete (includes sub_questions, sub_results, final_response, chairman_model)
- `get_decomposition_config()`: Get current decomposition configuration for API

**`embeddings.py`** - Embedding Generation Module
- Generates text embeddings for semantic caching using OpenAI's text-embedding-3-small via OpenRouter
- Falls back to hash-based approach if API embeddings fail
- **Configuration Constants**:
  - `EMBEDDINGS_API_URL`: OpenRouter embeddings endpoint
  - `DEFAULT_EMBEDDING_MODEL`: `openai/text-embedding-3-small` (fast and cheap)
  - `EMBEDDING_DIMENSION`: 1536 (dimension of default model)
  - `HASH_EMBEDDING_DIMENSION`: 256 (fallback hash embedding dimension)
- `get_embedding(text, model)`: Async function to generate embedding via OpenRouter API
  - Returns list of floats or None on failure
- `get_hash_embedding(text, dimension)`: Deterministic hash-based embedding fallback
  - Uses SHA256 hashes to create pseudo-embedding vector
  - Works for exact and near-exact matches, not semantically meaningful
  - Normalized to unit length
- `get_embedding_with_fallback(text, model, use_api)`: Main function with automatic fallback
  - Returns dict with: embedding, method ('api' or 'hash'), model, dimension
  - Falls back to hash if API fails or `use_api=False`
- `cosine_similarity(vec1, vec2)`: Calculate cosine similarity between two vectors
  - Returns score between -1 and 1 (1 = identical)
  - Returns 0.0 if vectors have different dimensions
- `find_most_similar(query_embedding, embeddings, threshold)`: Find best match above threshold
  - Returns dict with data, similarity, query or None if no match
- `get_embedding_config()`: Get embedding configuration for API endpoint

**`cache.py`** - Semantic Response Caching Module
- Stores query-response pairs with embeddings for semantic similarity matching
- Returns cached responses for similar queries, saving time and API costs
- **Configuration Constants**:
  - `CACHE_DIR`: `data/cache/` directory for cache storage
  - `CACHE_FILE`: `data/cache/semantic_cache.json` for cached entries
  - `CACHE_STATS_FILE`: `data/cache/cache_stats.json` for statistics
  - `DEFAULT_SIMILARITY_THRESHOLD`: 0.92 (92% similarity required for cache hit)
  - `DEFAULT_MAX_CACHE_ENTRIES`: 1000 (evicts oldest when exceeded)
  - `DEFAULT_USE_API_EMBEDDINGS`: True (use OpenAI embeddings by default)
- **Cache Entry Structure**:
  - `id`: Unique identifier (timestamp + hash)
  - `query`: Original query text
  - `system_prompt`: Optional system prompt (affects cache key)
  - `embedding`: Vector embedding of query
  - `embedding_method`: 'api' or 'hash'
  - `embedding_model`: Model used for embedding
  - `response`: Full council response (stage1, stage2, stage3, metadata)
  - `created_at`: Timestamp
  - `hit_count`: Number of times entry was matched
  - `last_hit`: Timestamp of last match
- **Cache Functions**:
  - `ensure_cache_dir()`: Create cache directory if not exists
  - `load_cache()`: Load cache data from JSON file
  - `save_cache(data)`: Save cache data to JSON file
  - `load_cache_stats()`: Load cache statistics
  - `save_cache_stats(stats)`: Save cache statistics with hit rate calculation
  - `record_cache_hit(cost_saved, time_saved_ms)`: Record a cache hit in statistics
  - `record_cache_miss()`: Record a cache miss in statistics
  - `add_cache_entry(query, response, system_prompt, use_api_embeddings, max_entries)`: Add new entry
    - Generates embedding for query
    - Evicts oldest entries if max exceeded
    - Returns dict with id, query, embedding_method, cache_size
  - `search_cache(query, system_prompt, similarity_threshold, use_api_embeddings)`: Search for similar query
    - Generates embedding for query
    - Finds best match above similarity threshold
    - Filters by system_prompt for cache key isolation
    - Updates hit statistics on match
    - Returns dict with response, similarity, cached_query, cache_id, or None
  - `clear_cache()`: Clear all cache entries
  - `clear_cache_stats()`: Reset cache statistics
  - `get_cache_info()`: Get cache size, config, and statistics
  - `delete_cache_entry(cache_id)`: Delete specific entry by ID
  - `get_cache_entries(limit, offset)`: Get paginated list of entries (without embeddings)
  - `get_cache_config()`: Get cache configuration for API endpoint

**`router.py`** - Dynamic Model Routing Module
- Classifies questions into categories and routes to specialized model pools
- **Question Categories**:
  - `CODING`: Programming, debugging, code review, algorithms
  - `CREATIVE`: Writing, brainstorming, storytelling, poetry
  - `FACTUAL`: Research, facts, definitions, historical information
  - `ANALYSIS`: Comparison, evaluation, logical reasoning, strategy
  - `GENERAL`: Broad questions using all configured models
- `CLASSIFIER_MODEL`: Fast model used for classification (Gemini Flash)
- `CATEGORY_KEYWORDS`: Keyword lists for fallback heuristic classification
- `DEFAULT_MODEL_POOLS`: Default model pools optimized per category
- `classify_by_keywords(query)`: Quick heuristic classification using keywords
- `classify_question(query)`: LLM-based classification with confidence score
  - Returns tuple: (category, confidence 0.0-1.0, reasoning)
  - Falls back to keyword classification if LLM fails
- `get_model_pool(category, all_models, custom_pools)`: Get appropriate models
  - Returns intersection of pool and available models
  - Ensures minimum 2 models for council operation
- `route_query(query, all_models, custom_pools)`: Main routing function
  - Returns dict with: category, confidence, reasoning, models, is_routed, model counts
- `CATEGORY_INFO`: Display info per category (name, description, color)

**`multi_chairman.py`** - Multi-Chairman Synthesis Module
- Implements ensemble synthesis where multiple chairman models independently create syntheses
- Supreme chairman evaluates and selects the best synthesis
- Provides diverse synthesis perspectives and quality assurance
- `get_multi_chairman_models()`: Gets list from config (imports from config_api)
- `get_supreme_chairman_model()`: Returns configured chairman model as supreme chairman
- `stage3_multi_chairman_synthesis(user_query, stage1_results, stage2_results)`:
  - Queries all multi-chairman models in parallel
  - Each chairman creates independent synthesis from council responses + rankings
  - Returns list of synthesis dicts with model, response, usage, cost
- `stage3_supreme_chairman_selection(user_query, syntheses)`:
  - Supreme chairman evaluates all syntheses for accuracy, completeness, clarity
  - Selects best synthesis and provides reasoning
  - Uses structured prompt: EVALUATION, SELECTED, REASONING, FINAL RESPONSE
  - Returns dict with selected_synthesis, selection_reasoning, final response
  - Parses response to extract selection letter and map to model
- `stage3_multi_chairman_streaming(user_query, stage1_results, stage2_results)`:
  - Streaming version for real-time display
  - Yields events: `multi_synthesis_start`, `synthesis_complete`, `multi_synthesis_complete`,
    `selection_start`, `selection_token`, `selection_complete`, `selection_error`
- `calculate_multi_chairman_costs(syntheses, selection_result)`:
  - Aggregates costs from all syntheses and selection
  - Returns breakdown: synthesis_costs, selection_cost, total, chairman_count

**`pricing.py`** - Model Pricing and Cost Calculation
- `MODEL_PRICING`: Dict of model identifiers to input/output prices per 1M tokens
- `get_model_pricing(model)`: Get pricing for a specific model (with default fallback)
- `calculate_cost(model, prompt_tokens, completion_tokens)`: Calculate cost breakdown
- `format_cost(cost)`: Format cost for display (e.g., "$0.0012" or "<$0.0001")
- `aggregate_costs(cost_list)`: Sum costs across multiple model calls

**`analytics.py`** - Performance Analytics Storage and Aggregation
- `ANALYTICS_DIR`: Analytics data directory (`data/analytics/`)
- `ANALYTICS_FILE`: JSON file storing all query records (`data/analytics/model_stats.json`)
- `record_query_result()`: Records results of a council query for analytics
  - Captures: model performances, rank positions, confidence scores, costs, timing
  - Called automatically after each council query (both batch and streaming)
- `get_model_statistics()`: Calculates aggregate statistics for all models
  - Returns: win rates, average ranks, confidence averages, costs, token usage
  - Models sorted by win rate (descending)
- `get_recent_queries(limit)`: Returns most recent query records for detailed analysis
- `get_chairman_statistics()`: Returns chairman model usage statistics
- `clear_analytics()`: Clears all analytics data (use with caution)
- Note: Analytics are persisted separately from conversations in `data/analytics/`

**`weights.py`** - Weighted Consensus Voting Module
- Calculates model weights based on historical performance from analytics
- Models that consistently perform well have their votes weighted more heavily
- Weight Calculation Formula:
  - Base weight = 1.0 for all models
  - Performance bonus = (win_rate / 100) * WIN_RATE_FACTOR (1.5)
  - Rank bonus = (1 / average_rank) * RANK_FACTOR (0.5)
  - Confidence bonus = ((avg_confidence - 1) / 9) * CONFIDENCE_FACTOR (0.1)
  - Final weight clamped to MIN_WEIGHT (0.3) to MAX_WEIGHT (2.5)
  - Weights normalized so average across participating models is 1.0
- Constants: `WIN_RATE_FACTOR`, `RANK_FACTOR`, `CONFIDENCE_FACTOR`, `MIN_WEIGHT`, `MAX_WEIGHT`, `MIN_QUERIES_FOR_WEIGHT` (2)
- `get_model_weights(models, include_confidence)`: Calculate weights for models
  - Returns dict with weight, normalized_weight, win_rate, average_rank, total_queries, has_history, weight_explanation
  - Models with fewer than MIN_QUERIES_FOR_WEIGHT queries get default weight 1.0
- `calculate_weighted_aggregate_rankings(stage2_results, label_to_model, use_weights)`:
  - Calculates aggregate rankings using weighted or unweighted votes
  - Returns list with model, average_rank, weighted_average_rank, rankings_count, weights_applied, rank_change
  - Sorted by weighted_average_rank when weights enabled
- `get_weights_summary()`: Get summary for display
  - Returns weights dict, has_historical_data, models_with_history, weight_range, explanation

**`process_logger.py`** - Process Logging Module
- `Verbosity`: IntEnum defining verbosity levels (0-3)
  - `SILENT` (0): No process events
  - `BASIC` (1): Stage transitions only
  - `STANDARD` (2): Stage + model events
  - `VERBOSE` (3): All detailed events including data/statistics
- `EventCategory`: Event type constants for color-coding
  - `STAGE`: Stage transitions (blue)
  - `MODEL`: Model operations (purple)
  - `INFO`: General info (gray)
  - `SUCCESS`: Success events (green)
  - `WARNING`: Warnings (amber)
  - `ERROR`: Errors (red)
  - `DATA`: Data/statistics (teal)
- `create_process_event(message, category, level, details)`: Creates event dict with timestamp
- `should_emit(event_level, current_verbosity)`: Checks if event should be emitted
- Pre-defined event generators for common operations:
  - `stage_start()`, `stage_complete()`: Stage lifecycle events (level 1)
  - `model_query_start()`, `model_query_complete()`, `model_query_error()`: Model events (level 2)
  - `models_queried_parallel()`: Parallel query summary (level 2)
  - `anonymizing_responses()`, `parsing_rankings()`, `ranking_parsed()`: Processing events (level 3)
  - `aggregate_rankings_calculated()`, `confidence_parsed()`, `aggregate_confidence_calculated()`: Data events (level 3)
  - `chairman_synthesizing()`, `total_cost_calculated()`, `analytics_recorded()`, `title_generated()`: Misc events (level 2-3)

**`openrouter.py`**
- `query_model()`: Single async model query (non-streaming)
- `query_models_parallel()`: Parallel queries using `asyncio.gather()` (non-streaming)
- `query_model_streaming()`: Single async model query with token-by-token streaming
  - Yields events: `token`, `reasoning_token`, `complete`, `error`
  - Handles OpenRouter's SSE format for streaming responses
- `query_models_parallel_streaming()`: Parallel streaming queries from all models
  - Uses asyncio queue to merge events from multiple models
  - Events include model identifier for routing to correct tab
- Returns dict with 'content', optional 'reasoning_details', 'usage', and 'cost'
- Graceful degradation: returns None on failure, continues with successful responses
- **Reasoning Model Support**: Captures `reasoning_details` from models like o1, o3 that expose chain-of-thought
- **Cost Tracking**: Captures `usage` (prompt_tokens, completion_tokens) and calculates `cost` per query

**`council.py`** - The Core Logic
- `CONFIDENCE_PROMPT_SUFFIX`: Appended to user queries to request confidence scores (1-10)
- `COT_PROMPT_SUFFIX`: Appended to user queries when CoT mode is enabled to request structured reasoning
  - Requests three sections: **THINKING**, **ANALYSIS**, **CONCLUSION**
  - Forces ALL models to provide explicit structured reasoning
- `parse_cot_response(text)`: Extracts THINKING, ANALYSIS, CONCLUSION sections from response
  - Returns dict with `thinking`, `analysis`, `conclusion` keys, or None if not found
  - Supports multiple formats: `**THINKING:**`, `THINKING:`, etc.
- `extract_response_without_cot(text)`: Returns just the conclusion when CoT is present
- `stage1_collect_responses(user_query, system_prompt=None, use_cot=False, models=None)`: Parallel queries to council models (batch)
  - Accepts optional `system_prompt` parameter that is prepended as a system message
  - Accepts optional `use_cot` parameter to enable Chain-of-Thought structured responses
  - Accepts optional `models` parameter for dynamic routing (overrides default council models)
  - Appends confidence prompt suffix to get 1-10 confidence score from each model
  - When `use_cot=True`, appends CoT prompt and parses structured sections
  - Returns `reasoning_details` if present (for reasoning models like o1, o3)
  - Returns `cot` dict (with thinking, analysis, conclusion) if CoT mode enabled
  - Returns `confidence` score (1-10, or null if not parseable) for each model
  - Returns `usage` and `cost` data for each model response
- `stage1_collect_responses_streaming(user_query, system_prompt=None, use_cot=False, models=None)`: Streaming version
  - Yields token events as models generate responses in parallel
  - Accepts optional `models` parameter for dynamic routing
  - Event types: `stage1_token`, `stage1_reasoning_token`, `stage1_model_complete`, `stage1_complete`, `stage1_error`
  - Enables real-time display of responses as they generate
- `stage2_collect_rankings(user_query, stage1_results, use_cot=False)`:
  - Anonymizes responses as "Response A, B, C, etc."
  - Creates `label_to_model` mapping for de-anonymization
  - Prompts models to evaluate and rank (with strict format requirements)
  - When `use_cot=True`, includes full reasoning structure in ranking prompt
  - CoT-aware ranking evaluates: reasoning quality, analysis depth, conclusion accuracy, overall coherence
  - Returns tuple: (rankings_list, label_to_model_dict)
  - Each ranking includes both raw text and `parsed_ranking` list
  - Each ranking includes `usage` and `cost` data
  - Note: Stage 2 is NOT streamed (relatively fast batch operation)
- `stage3_synthesize_final()`: Chairman synthesizes from all responses + rankings (batch)
  - Returns `usage` and `cost` data for chairman query
- `stage3_synthesize_final_streaming()`: Streaming version
  - Yields token events as chairman generates the response
  - Event types: `stage3_token`, `stage3_complete`, `stage3_error`
  - Enables real-time display of final synthesis
- `parse_ranking_from_text()`: Extracts "FINAL RANKING:" section, handles both numbered lists and plain format
- `parse_confidence(text)`: Extracts confidence score (1-10) from model response text
  - Supports multiple formats: "CONFIDENCE: 8", "Confidence: 8", "**CONFIDENCE:** 8", etc.
  - Returns None if no valid confidence found
- `extract_response_without_confidence(text)`: Removes confidence line from response for cleaner display
- `calculate_aggregate_rankings()`: Computes average rank position across all peer evaluations
- `calculate_aggregate_confidence(stage1_results)`: Computes aggregate confidence statistics
  - Returns: average, min, max, count, total_models, distribution (dict of score→count)
- `calculate_total_costs()`: Aggregates costs across all 3 stages into summary
- **Consensus Detection Constants**:
  - `CONSENSUS_MIN_CONFIDENCE = 7`: Minimum average confidence required for consensus
  - `CONSENSUS_MAX_AVG_RANK = 1.5`: Top model's average rank must be ≤ 1.5
  - `CONSENSUS_MIN_AGREEMENT = 0.8`: At least 80% of models must rank top model as #1
- `detect_consensus(stage1_results, stage2_results, label_to_model, aggregate_rankings, aggregate_confidence)`:
  - Determines if strong consensus exists to skip Stage 3 synthesis
  - Checks three criteria: average rank, first-place agreement ratio, confidence threshold
  - Returns dict with: `is_consensus`, `consensus_model`, `consensus_response`, `reason`, `metrics`
  - Metrics include: `average_rank`, `first_place_votes`, `total_voters`, `agreement_ratio`, `average_confidence`
- `run_full_council(user_query, system_prompt, use_cot, use_weighted_consensus, use_early_consensus, use_dynamic_routing)`: Main orchestration function
  - Accepts optional `use_weighted_consensus` parameter (default True) for weighted voting
  - Accepts optional `use_early_consensus` parameter (default False) for consensus-based early exit
  - Accepts optional `use_dynamic_routing` parameter (default False) for question-based model selection
  - When `use_dynamic_routing=True`, calls `router.route_query()` before Stage 1
  - Uses `weights.calculate_weighted_aggregate_rankings()` for weighted mode
  - Calls `detect_consensus()` after Stage 2 when early consensus enabled
  - Skips Stage 3 if consensus detected, returns consensus response directly
  - Records analytics via `analytics.record_query_result()` after completion
  - Returns metadata including `use_weighted_consensus`, `weights_info`, `consensus_info`, `early_exit`, `use_dynamic_routing`, `routing_info`
  - Tracks query duration in milliseconds for performance analysis

**`storage.py`**
- JSON-based conversation storage in `data/conversations/`
- Each conversation: `{id, created_at, title, tags[], messages[]}`
- Assistant messages contain: `{role, stage1, stage2, stage3}`
- Note: metadata (label_to_model, aggregate_rankings) is NOT persisted to storage, only returned via API
- **Tagging Functions**:
  - `update_conversation_tags(id, tags)`: Update tags for a conversation
  - `get_all_tags()`: Get all unique tags across conversations
  - `filter_conversations_by_tag(tag)`: Filter conversations by tag

**`main.py`**
- FastAPI app with CORS enabled for localhost:5173 and localhost:3000
- POST `/api/conversations/{id}/message` returns metadata in addition to stages
- Metadata includes: label_to_model mapping, aggregate_rankings, aggregate_confidence, and costs breakdown
- Both `/message` and `/message/stream` endpoints accept optional `system_prompt` parameter
- Both endpoints accept optional `verbosity` parameter (0-3) for process monitoring
- Both endpoints accept optional `use_cot` parameter (boolean) for Chain-of-Thought mode
- Both endpoints accept optional `use_multi_chairman` parameter (boolean) for Multi-Chairman mode
- Both endpoints accept optional `use_weighted_consensus` parameter (boolean, default True) for Weighted Consensus
- Both endpoints accept optional `use_early_consensus` parameter (boolean, default False) for Early Consensus Exit
- Both endpoints accept optional `use_dynamic_routing` parameter (boolean, default False) for Dynamic Model Routing
- Both endpoints accept optional `use_escalation` parameter (boolean, default False) for Confidence-Gated Escalation
- Both endpoints accept optional `use_refinement` parameter (boolean, default False) for Iterative Refinement
- Both endpoints accept optional `refinement_max_iterations` parameter (integer, default 2, range 1-5)
- Both endpoints accept optional `use_adversary` parameter (boolean, default False) for Adversarial Validation
- Both endpoints accept optional `use_debate` parameter (boolean, default False) for Debate Mode
- Both endpoints accept optional `include_rebuttal` parameter (boolean, default True) for including Round 3 in debates
- Both endpoints accept optional `use_decomposition` parameter (boolean, default False) for Sub-Question Decomposition
- Both endpoints accept optional `use_cache` parameter (boolean, default False) for Semantic Response Caching
- Both endpoints accept optional `cache_similarity_threshold` parameter (float, default 0.92) for cache match threshold
- **Streaming Endpoint** (`/message/stream`): Real-time token streaming via SSE
  - Event types for token-level streaming:
    - `cache_check_start`: Cache lookup beginning (only if `use_cache=True`)
    - `cache_hit`: Cache hit found (includes similarity, cached_query, cache_id, cached_response, created_at, hit_count)
    - `cache_miss`: No cache match found, proceeding with full council
    - `cache_stored`: New response stored in cache (includes cache_id, embedding_method, cache_size)
    - `routing_start`: Dynamic routing classification begins (only if `use_dynamic_routing=True`)
    - `routing_complete`: Routing finished (includes category, confidence, reasoning, selected models)
    - `tier1_start`: Tier 1 escalation begins (only if `use_escalation=True`, includes tier1 models)
    - `tier1_complete`: Tier 1 assessment complete (includes aggregate_confidence)
    - `escalation_triggered`: Escalating to Tier 2 (includes escalation_info with reasons, metrics)
    - `tier2_start`: Tier 2 escalation begins (includes tier2 models)
    - `stage1_start`: Stage 1 begins (includes `use_cot`, `use_dynamic_routing`, `routing_info`, `use_escalation`, `current_tier`)
    - `stage1_token`: Token from a council model (includes model identifier, optional tier if escalation)
    - `stage1_reasoning_token`: Reasoning token from a council model (includes optional tier)
    - `stage1_model_complete`: A single model has finished responding (includes `cot` dict if CoT enabled, optional tier)
    - `stage1_complete`: All Stage 1 models have finished (includes aggregate_confidence, escalation_info metadata)
    - `stage1_error`: Error from a specific model (continues with other models)
    - `stage2_start`: Stage 2 begins
    - `stage2_complete`: Stage 2 finished (includes label_to_model, aggregate_rankings, use_weighted_consensus, weights_info metadata)
    - `consensus_detected`: Early consensus detected, Stage 3 will be skipped (includes consensus_info with model, response, metrics)
    - `stage3_start`: Stage 3 begins (includes `use_multi_chairman` boolean)
    - `stage3_token`: Token from chairman model (single chairman mode)
    - `stage3_complete`: Stage 3 finished (includes `use_multi_chairman` if multi-chairman mode, `is_consensus` and `consensus_info` if consensus exit)
    - `stage3_error`: Chairman model error
    - `multi_synthesis_start`: Multi-chairman synthesis begins (multi-chairman mode only)
    - `synthesis_complete`: A chairman has finished synthesizing (multi-chairman mode only)
    - `multi_synthesis_complete`: All chairmen have finished synthesizing (multi-chairman mode only)
    - `selection_start`: Supreme chairman selection begins (multi-chairman mode only)
    - `selection_token`: Token from supreme chairman (multi-chairman mode only)
    - `refinement_start`: Iterative refinement beginning (only if `use_refinement=True`, includes max_iterations)
    - `iteration_start`: New refinement iteration beginning (includes iteration number)
    - `critiques_start`: Council critique collection starting (includes iteration, model_count)
    - `critique_complete`: A single model's critique received (includes model, critique, is_substantive)
    - `critiques_complete`: All critiques collected for iteration (includes substantive_count, critiques)
    - `revision_start`: Chairman revision starting (includes iteration, model)
    - `revision_token`: Token from chairman during revision (includes iteration, content, model)
    - `revision_complete`: Revision finished for iteration (includes iteration, content, model, cost)
    - `iteration_complete`: Full refinement iteration finished (includes iteration, revision)
    - `refinement_converged`: Refinement stopped early (includes iteration, reason, final_response)
    - `refinement_complete`: Refinement loop finished (includes iterations, final_response, total_iterations, converged, total_cost)
    - `revision_error`: Error during revision (includes iteration, error, model)
    - `adversary_start`: Adversarial validation beginning (only if `use_adversary=True`, includes adversary_model)
    - `adversary_token`: Token from adversary model during critique (includes content, model)
    - `adversary_complete`: Adversary critique finished (includes critique, has_issues, severity, model)
    - `adversary_revision_start`: Chairman revision starting based on adversary critique (includes model)
    - `adversary_revision_token`: Token from chairman during adversary-triggered revision (includes content, model)
    - `adversary_revision_complete`: Adversary-triggered revision finished (includes revision, model, cost)
    - `adversary_validation_complete`: Full adversarial validation finished (includes critique, has_issues, severity, revised, revision, adversary_model)
    - `debate_start`: Debate mode beginning (only if `use_debate=True`, includes models, num_rounds, include_rebuttal, model_to_label, label_to_model)
    - `round1_start`: Position round beginning
    - `position_complete`: Model finished stating position (includes label, model, position)
    - `round1_complete`: All positions collected (includes positions array)
    - `round2_start`: Critique round beginning
    - `debate_critique_complete`: Model finished critiquing (includes critic_label, target_label, critique)
    - `round2_complete`: All critiques collected (includes critiques array)
    - `round3_start`: Rebuttal round beginning (only if include_rebuttal=True)
    - `rebuttal_complete`: Model finished rebuttal (includes label, model, rebuttal)
    - `round3_complete`: All rebuttals collected (includes rebuttals array)
    - `judgment_start`: Chairman evaluation beginning (includes model)
    - `judgment_token`: Token from chairman during judgment (includes content, model)
    - `judgment_complete`: Judgment finished (includes judgment, model, cost)
    - `debate_complete`: Full debate process complete (includes positions, critiques, rebuttals, judgment, model_to_label, label_to_model, num_rounds, total_cost)
    - `decomposition_start`: Decomposition mode beginning (only if `use_decomposition=True`)
    - `complexity_analyzed`: Complexity detection complete (includes is_complex, confidence, reasoning)
    - `decomposition_skip`: Question not complex enough, falling through to normal council
    - `sub_questions_generated`: Sub-questions created (includes sub_questions array, count)
    - `sub_council_start`: Beginning to process a sub-question (includes index)
    - `sub_council_response`: A model responded to sub-question (includes index, model, response)
    - `sub_council_complete`: Sub-question fully answered (includes index, sub_question, best_answer, best_model)
    - `all_sub_councils_complete`: All sub-questions answered (includes results array)
    - `merge_start`: Chairman beginning to merge sub-answers (includes chairman_model)
    - `merge_token`: Token from chairman during merge (includes content)
    - `merge_complete`: Merge finished (includes response)
    - `decomposition_complete`: Full decomposition complete (includes sub_questions, sub_results, final_response, chairman_model)
    - `costs_complete`: Cost breakdown calculated
    - `title_complete`: Conversation title generated
    - `complete`: Full process complete
    - `error`: An error occurred
    - `process`: Process monitor event (includes message, category, timestamp)
- **Tag Endpoints**:
  - `GET /api/conversations?tag=X`: Filter conversations by tag
  - `PUT /api/conversations/{id}/tags`: Update conversation tags
  - `GET /api/tags`: Get all unique tags
- **Config Endpoints**:
  - `GET /api/config`: Get current model configuration
  - `PUT /api/config`: Update model configuration (validates minimum 2 models)
  - `POST /api/config/reset`: Reset configuration to defaults
  - `GET /api/config/models`: Get list of suggested models for dropdown
- **Analytics Endpoints**:
  - `GET /api/analytics`: Get comprehensive model performance statistics (win rates, ranks, costs)
  - `GET /api/analytics/recent?limit=N`: Get recent query records for detailed analysis
  - `GET /api/analytics/chairman`: Get chairman model usage statistics
  - `DELETE /api/analytics`: Clear all analytics data (use with caution)
- **Weights Endpoints**:
  - `GET /api/weights`: Get all model weights based on historical performance
  - `GET /api/weights/{model}`: Get weight for a specific model
- **Routing Endpoints**:
  - `GET /api/routing/pools`: Get current routing pool configuration per category
  - `POST /api/routing/classify?query=X`: Test classify a question without running full query
- **Escalation Endpoints**:
  - `GET /api/escalation/tiers`: Get current tier configuration (tier1_models, tier2_models, thresholds, descriptions)
  - `GET /api/escalation/thresholds`: Get current escalation thresholds
- **Refinement Endpoints**:
  - `GET /api/refinement/config`: Get refinement configuration (default_max_iterations, min_critiques_for_revision, non_substantive_phrases)
- **Adversary Endpoints**:
  - `GET /api/adversary/config`: Get adversary configuration (adversary_model, severity_levels, revision_threshold, no_issues_phrases)
- **Debate Endpoints**:
  - `GET /api/debate/config`: Get debate configuration (default_num_rounds, include_rebuttal, round_names, description)
- **Decomposition Endpoints**:
  - `GET /api/decomposition/config`: Get decomposition configuration (default_max_sub_questions, complexity_threshold, decomposer_model, complexity_indicators, description)
- **Cache Endpoints**:
  - `GET /api/cache/config`: Get cache configuration (similarity_threshold, max_cache_entries, use_api_embeddings, embedding_model)
  - `GET /api/cache/info`: Get cache info and statistics (cache_size, stats, entry counts by embedding method)
  - `GET /api/cache/stats`: Get cache hit/miss statistics (total_queries, cache_hits, cache_misses, hit_rate, cost_saved, time_saved)
  - `GET /api/cache/entries?limit=N&offset=M`: Get paginated list of cache entries (without embeddings)
  - `DELETE /api/cache`: Clear all cache entries
  - `DELETE /api/cache/stats`: Clear cache statistics
  - `DELETE /api/cache/{cache_id}`: Delete specific cache entry by ID
  - `POST /api/cache/search`: Search cache for similar query (body: query, system_prompt, similarity_threshold)
- **Embeddings Endpoints**:
  - `GET /api/embeddings/config`: Get embedding configuration (default_model, dimensions, api_url)
- Note: Streaming endpoint also records analytics after each query completion

### Frontend Structure (`frontend/src/`)

**`App.jsx`**
- Main orchestration: manages conversations list and current conversation
- Handles message sending and metadata storage
- Important: metadata is stored in the UI state for display but not persisted to backend JSON
- **Streaming Token Handling**: Handles real-time token events from backend
  - State: `stage1Streaming` (partial responses per model), `stage1ReasoningStreaming` (partial reasoning per model)
  - State: `stage3Streaming` (partial chairman response), `stage3StreamingModel` (chairman model name)
  - Accumulates tokens as they arrive and merges with completed responses
  - Passes streaming state to Stage1 and Stage3 components for real-time display
- **System Prompt Feature**: Collapsible settings panel with system prompt textarea
  - State: `systemPrompt` (persisted to localStorage), `showSettings` (toggle visibility)
  - Blue dot indicator shows when system prompt is active
  - System prompt is passed through to all council model queries
- **Tagging Feature**:
  - State: `allTags` (all unique tags), `selectedTag` (filter)
  - `handleTagsChange()`: Updates tags via API
  - `handleTagFilterChange()`: Filters conversations by tag
- **Model Configuration Feature**:
  - State: `showConfigPanel` (toggle visibility)
  - "Configure Models" button in settings bar opens ConfigPanel modal
  - ConfigPanel rendered with overlay backdrop
- **Performance Dashboard Feature**:
  - State: `showDashboard` (toggle visibility)
  - "Dashboard" button in settings bar opens PerformanceDashboard modal
  - Dashboard rendered with overlay backdrop
- **Process Monitor Feature**:
  - State: `showProcessMonitor` (panel visibility), `processVerbosity` (0-3, persisted to localStorage), `processEvents` (event array)
  - "Process" button in settings bar toggles ProcessMonitor side panel
  - `handleVerbosityChange()`: Updates verbosity and persists to localStorage
  - Process events received via `process` SSE event type, accumulated in `processEvents` array
  - Events cleared at start of each new message to show only current query's events
- **Chain-of-Thought Mode Feature**:
  - State: `useCot` (boolean, persisted to localStorage)
  - Toggle in settings panel enables/disables Chain-of-Thought structured reasoning
  - "CoT" indicator badge in settings bar when enabled
  - `handleCotChange()`: Updates CoT setting and persists to localStorage
  - Passed to backend via `use_cot` parameter in sendMessageStream
- **Multi-Chairman Mode Feature**:
  - State: `useMultiChairman` (boolean, persisted to localStorage)
  - Toggle in settings panel enables/disables Multi-Chairman ensemble synthesis
  - "MC" indicator badge in settings bar when enabled
  - `handleMultiChairmanChange()`: Updates setting and persists to localStorage
  - Passed to backend via `use_multi_chairman` parameter in sendMessageStream
  - Handles streaming events: `multi_synthesis_start`, `synthesis_complete`, `multi_synthesis_complete`, `selection_start`, `selection_token`
  - Message state includes: `useMultiChairman`, `multiSyntheses`, `selectionStreaming`, `isSelecting`
- **Weighted Consensus Feature**:
  - State: `useWeightedConsensus` (boolean, default true, persisted to localStorage)
  - Toggle in settings panel enables/disables weighted voting by historical performance
  - "WC" indicator badge in settings bar when enabled (amber/gold color)
  - `handleWeightedConsensusChange()`: Updates setting and persists to localStorage
  - Passed to backend via `use_weighted_consensus` parameter in sendMessageStream
  - Metadata includes `use_weighted_consensus` and `weights_info` for display in Stage2
- **Early Consensus Exit Feature**:
  - State: `useEarlyConsensus` (boolean, default false, persisted to localStorage)
  - Toggle in settings panel enables/disables consensus-based Stage 3 skip
  - "EC" indicator badge in settings bar when enabled (cyan/teal color)
  - `handleEarlyConsensusChange()`: Updates setting and persists to localStorage
  - Passed to backend via `use_early_consensus` parameter in sendMessageStream
  - Handles `consensus_detected` SSE event to display consensus results
  - Message state includes: `isConsensus`, `consensusInfo`
- **Dynamic Model Routing Feature**:
  - State: `useDynamicRouting` (boolean, default false, persisted to localStorage)
  - Toggle in settings panel enables/disables question-based model selection
  - "DR" indicator badge in settings bar when enabled (orange color)
  - `handleDynamicRoutingChange()`: Updates setting and persists to localStorage
  - Passed to backend via `use_dynamic_routing` parameter in sendMessageStream
  - Handles `routing_start` and `routing_complete` SSE events
  - Message state includes: `useDynamicRouting`, `routingInfo`, `loading.routing`
  - routingInfo contains: category, confidence, reasoning, models, is_routed
- **Confidence-Gated Escalation Feature**:
  - State: `useEscalation` (boolean, default false, persisted to localStorage)
  - Toggle in settings panel enables/disables tiered model escalation
  - "CG" indicator badge in settings bar when enabled (pink color)
  - `handleEscalationChange()`: Updates setting and persists to localStorage
  - Passed to backend via `use_escalation` parameter in sendMessageStream
  - Handles `tier1_start`, `tier1_complete`, `escalation_triggered`, `tier2_start` SSE events
  - Message state includes: `useEscalation`, `escalationInfo`, `currentTier`, `escalated`, `loading.tier1`, `loading.tier2`
  - escalationInfo contains: escalated, tier1_model_count, tier2_model_count, total_model_count, reasons, metrics, triggers
  - Note: Escalation is disabled when Dynamic Routing is active (routing takes precedence)
- **Iterative Refinement Feature**:
  - State: `useRefinement` (boolean, default false, persisted to localStorage)
  - State: `refinementMaxIterations` (number, default 2, persisted to localStorage)
  - Toggle in settings panel enables/disables critique-and-revise cycles
  - "IR" indicator badge in settings bar when enabled (purple/violet color)
  - Max iterations dropdown (1-5) appears when refinement is enabled
  - `handleRefinementChange()`: Updates setting and persists to localStorage
  - `handleRefinementMaxIterationsChange()`: Updates max iterations setting
  - Passed to backend via `use_refinement` and `refinement_max_iterations` parameters
  - Handles refinement SSE events: `refinement_start`, `iteration_start`, `critiques_start`, `critique_complete`,
    `critiques_complete`, `revision_start`, `revision_token`, `revision_complete`, `iteration_complete`,
    `refinement_converged`, `refinement_complete`, `revision_error`
  - Message state includes: `useRefinement`, `refinementIterations`, `refinementStreaming`, `refinementCritiques`,
    `isRefining`, `currentRefinementIteration`, `refinementMaxIterations`, `refinementConverged`, `loading.refinement`
- **Adversarial Validation Feature**:
  - State: `useAdversary` (boolean, default false, persisted to localStorage)
  - Toggle in settings panel enables/disables devil's advocate review
  - "AV" indicator badge in settings bar when enabled (red/rose color)
  - `handleAdversaryChange()`: Updates setting and persists to localStorage
  - Passed to backend via `use_adversary` parameter in sendMessageStream
  - Handles adversary SSE events: `adversary_start`, `adversary_token`, `adversary_complete`,
    `adversary_revision_start`, `adversary_revision_token`, `adversary_revision_complete`,
    `adversary_validation_complete`
  - Message state includes: `useAdversary`, `adversaryCritique`, `adversaryHasIssues`, `adversarySeverity`,
    `adversaryRevised`, `adversaryRevision`, `adversaryModel`, `isAdversaryReviewing`, `isAdversaryRevising`,
    `adversaryStreaming`, `adversaryRevisionStreaming`, `loading.adversary`
  - Note: Adversary runs after refinement (if enabled), validating the final synthesis
- **Debate Mode Feature**:
  - State: `useDebate` (boolean, default false, persisted to localStorage)
  - State: `includeRebuttal` (boolean, default true, persisted to localStorage)
  - Toggle in settings panel enables/disables multi-round debate mode
  - "DB" indicator badge in settings bar when enabled (orange/amber color)
  - `handleDebateChange()`: Updates debate setting and persists to localStorage
  - `handleIncludeRebuttalChange()`: Updates rebuttal setting and persists to localStorage
  - Passed to backend via `use_debate` and `include_rebuttal` parameters in sendMessageStream
  - Handles debate SSE events: `debate_start`, `round1_start`, `position_complete`, `round1_complete`,
    `round2_start`, `debate_critique_complete`, `round2_complete`, `round3_start`, `rebuttal_complete`,
    `round3_complete`, `judgment_start`, `judgment_token`, `judgment_complete`, `debate_complete`
  - Message state includes: `useDebate`, `debatePositions`, `debateCritiques`, `debateRebuttals`,
    `debateJudgment`, `debateJudgmentStreaming`, `isDebating`, `isJudging`, `debateRound`,
    `debateModelToLabel`, `debateLabelToModel`, `debateNumRounds`, `loading.debate`
  - Note: Debate mode is an alternative flow that bypasses normal 3-stage council process
- **Sub-Question Decomposition Feature**:
  - State: `useDecomposition` (boolean, default false, persisted to localStorage)
  - Toggle in settings panel enables/disables decomposition mode
  - "DQ" indicator badge in settings bar when enabled (teal/cyan color)
  - `handleDecompositionChange()`: Updates setting and persists to localStorage
  - Passed to backend via `use_decomposition` parameter in sendMessageStream
  - Handles decomposition SSE events: `decomposition_start`, `complexity_analyzed`, `decomposition_skip`,
    `sub_questions_generated`, `sub_council_start`, `sub_council_response`, `sub_council_complete`,
    `all_sub_councils_complete`, `merge_start`, `merge_token`, `merge_complete`, `decomposition_complete`
  - Message state includes: `useDecomposition`, `isDecomposing`, `decompositionSkipped`, `complexityInfo`,
    `subQuestions`, `subResults`, `currentSubQuestion`, `totalSubQuestions`, `mergeStreaming`,
    `isMerging`, `decompositionFinalResponse`, `chairmanModel`, `decompositionComplete`
  - Note: Decomposition mode is an alternative flow that bypasses normal 3-stage council process for complex questions
- **Semantic Response Caching Feature**:
  - State: `useCache` (boolean, default false, persisted to localStorage)
  - Toggle in settings panel enables/disables semantic response caching
  - "CA" indicator badge in settings bar when enabled (green color)
  - `handleCacheChange()`: Updates setting and persists to localStorage
  - Passed to backend via `use_cache` parameter in sendMessageStream
  - Handles cache SSE events: `cache_check_start`, `cache_hit`, `cache_miss`, `cache_stored`
  - Message state includes: `useCache`, `cacheChecking`, `cacheHit`, `cacheStored`
  - On cache hit, all stages populated from cached response and loading states cleared

**`api.js`** - API Client
- Base URL: `http://localhost:8001`
- Conversation APIs: `listConversations()`, `createConversation()`, `getConversation()`, `sendMessage()`, `sendMessageStream()`
  - `sendMessageStream()` accepts optional `verbosity` parameter (0-3) for process monitoring
  - `sendMessageStream()` accepts optional `useCot` parameter (boolean) for Chain-of-Thought mode
  - `sendMessageStream()` accepts optional `useMultiChairman` parameter (boolean) for Multi-Chairman mode
  - `sendMessageStream()` accepts optional `useWeightedConsensus` parameter (boolean, default true) for Weighted Consensus
  - `sendMessageStream()` accepts optional `useEarlyConsensus` parameter (boolean, default false) for Early Consensus Exit
  - `sendMessageStream()` accepts optional `useDynamicRouting` parameter (boolean, default false) for Dynamic Model Routing
  - `sendMessageStream()` accepts optional `useEscalation` parameter (boolean, default false) for Confidence-Gated Escalation
  - `sendMessageStream()` accepts optional `useRefinement` parameter (boolean, default false) for Iterative Refinement
  - `sendMessageStream()` accepts optional `refinementMaxIterations` parameter (number, default 2) for max refinement iterations
  - `sendMessageStream()` accepts optional `useAdversary` parameter (boolean, default false) for Adversarial Validation
  - `sendMessageStream()` accepts optional `useDebate` parameter (boolean, default false) for Debate Mode
  - `sendMessageStream()` accepts optional `includeRebuttal` parameter (boolean, default true) for including Round 3 in debates
  - `sendMessageStream()` accepts optional `useDecomposition` parameter (boolean, default false) for Sub-Question Decomposition
  - `sendMessageStream()` accepts optional `useCache` parameter (boolean, default false) for Semantic Response Caching
  - `sendMessageStream()` accepts optional `cacheSimilarityThreshold` parameter (number, default 0.92) for cache match threshold
- Tag APIs: `updateTags()`, `getAllTags()`
- Routing APIs: `getRoutingPools()`, `classifyQuestion(query)`
- Escalation APIs:
  - `getEscalationTiers()`: Get tier configuration (tier1_models, tier2_models, thresholds, descriptions)
  - `getEscalationThresholds()`: Get escalation threshold configuration
- Refinement APIs:
  - `getRefinementConfig()`: Get refinement configuration (default_max_iterations, min_critiques_for_revision, non_substantive_phrases)
- Adversary APIs:
  - `getAdversaryConfig()`: Get adversary configuration (adversary_model, severity_levels, revision_threshold, no_issues_phrases)
- Debate APIs:
  - `getDebateConfig()`: Get debate configuration (default_num_rounds, include_rebuttal, round_names, description)
- Decomposition APIs:
  - `getDecompositionConfig()`: Get decomposition configuration (default_max_sub_questions, complexity_threshold, decomposer_model, complexity_indicators, description)
- Cache APIs:
  - `getCacheConfig()`: Get cache configuration (similarity_threshold, max_cache_entries, use_api_embeddings, embedding_model)
  - `getCacheInfo()`: Get cache info and statistics (cache_size, stats, entry counts)
  - `getCacheStats()`: Get cache hit/miss statistics
  - `getCacheEntries(limit, offset)`: Get paginated list of cache entries
  - `clearCache()`: Clear all cache entries
  - `clearCacheStats()`: Clear cache statistics
  - `deleteCacheEntry(cacheId)`: Delete specific cache entry
  - `searchCache(query, systemPrompt, similarityThreshold)`: Search cache for similar query
  - `getEmbeddingsConfig()`: Get embedding configuration
- Config APIs: `getConfig()`, `updateConfig()`, `resetConfig()`, `getAvailableModels()`
- Analytics APIs:
  - `getAnalytics()`: Get comprehensive model performance statistics
  - `getRecentQueries(limit)`: Get recent query records
  - `getChairmanAnalytics()`: Get chairman model usage statistics
  - `clearAnalytics()`: Clear all analytics data
- Weights APIs:
  - `getWeights()`: Get model weights based on historical performance
  - `getModelWeight(model)`: Get weight for a specific model

**`utils/export.js`**
- `exportToMarkdown(conversation)`: Generates and downloads Markdown file
- `exportToJSON(conversation)`: Generates and downloads JSON file
- Uses browser Blob API for client-side file generation
- Sanitizes filenames, formats all 3 stages with model names

**`components/TagEditor.jsx`**
- Tag editor component with add/remove functionality
- Suggested tags dropdown for quick selection
- Normalizes tags to lowercase

**`components/ConfigPanel.jsx`**
- Modal panel for model configuration management
- Features:
  - Add/remove/reorder council models with drag buttons
  - Chairman model selection dropdown (can be council member or external)
  - Model autocomplete with suggested models from backend
  - Quick-add buttons for popular models
  - Validation (minimum 2 council models required)
  - Reset to defaults functionality
  - Save/Cancel actions with loading states
  - Error and success message display
- Props: `onClose` callback to close the panel

**`components/PerformanceDashboard.jsx`**
- Modal dashboard displaying model performance analytics
- Features:
  - Summary statistics: total queries, unique models, date range
  - Three tabbed views: Leaderboard, Model Details, Chairman Stats
  - **Leaderboard Tab**: Model ranking sorted by win rate
    - Medal icons for top 3 models
    - Columns: model name, win rate (%), avg rank, avg confidence, query count
    - Color-coded win rates and ranks
  - **Model Details Tab**: Detailed cards for each model
    - Performance stats: wins, average rank, confidence
    - Usage stats: total cost, total tokens
    - Rank distribution bar chart visualization
  - **Chairman Stats Tab**: Chairman model usage statistics
    - Times used, total cost per chairman model
  - Data refresh button and clear data option (with confirmation)
- Props: `onClose` callback to close the dashboard
- Uses purple/indigo color scheme (#667eea) to distinguish from other panels

**`components/ProcessMonitor.jsx`**
- Side panel showing real-time council deliberation events
- Features:
  - Verbosity knob (0-3) controlling event detail level
  - Auto-scrolling event log with scroll position detection
  - Color-coded events by category (stage=blue, model=purple, success=green, warning=amber, error=red, data=teal, info=gray)
  - Timestamps for each event
  - Collapsible panel with toggle button
  - Event count badge when collapsed
  - "Scroll to latest" button when user scrolls up
- Props: `events` (array), `verbosity` (0-3), `onVerbosityChange` (callback), `isOpen` (boolean), `onToggle` (callback)
- Exports additional `VerbosityControl` component for standalone verbosity selection
- Uses dark theme (#1a1a2e background) to distinguish from main content area

**`components/ReasoningView.jsx`**
- Displays Chain-of-Thought structured reasoning (Thinking → Analysis → Conclusion)
- Features:
  - Three collapsible sections with step indicators (1, 2, 3)
  - Color-coded steps: blue (thinking), purple (analysis), green (conclusion)
  - Progress visualization in header showing completed steps
  - Each section expandable/collapsible independently
  - Conclusion shown by default, others collapsed
- Props: `cot` (object with thinking, analysis, conclusion), `showAll` (boolean), `compact` (boolean)
- Exports additional components:
  - `CoTBadge`: Mini badge for tabs indicating CoT is available
  - `CoTToggle`: Toggle control for enabling/disabling CoT mode
- Blue color scheme (#3b82f6) to indicate structured reasoning

**`components/ChatInterface.jsx`**
- Multiline textarea (3 rows, resizable)
- Enter to send, Shift+Enter for new line
- User messages wrapped in markdown-content class for padding
- **Header Features**:
  - Export buttons (MD/JSON)
  - Tags button to toggle TagEditor
  - Current tags displayed in header

**`components/Stage1.jsx`**
- Tab view of individual model responses
- ReactMarkdown rendering with markdown-content wrapper
- Props: `responses` (array), `aggregateConfidence` (object), `streamingResponses` (object), `streamingReasoning` (object), `isStreaming` (boolean), `routingInfo` (object)
- **Dynamic Routing Display**:
  - Shows routing badge in header when routing was applied
  - Badge color matches category: green (coding), purple (creative), blue (factual), amber (analysis), gray (general)
  - Hover tooltip shows confidence percentage and reasoning
- **Real-Time Streaming Support**:
  - Merges completed responses with streaming responses
  - Displays partial responses as models generate them
  - Blue "Streaming..." indicator in header when active
  - Pulsing blue dot on tabs for models still generating
  - Blinking cursor at end of streaming text
  - Auto-handles model tab creation for new streaming models
- **Reasoning Model Support** (for native reasoning models like o1, o3):
  - Detects `reasoning_details` in response data
  - Shows "Reasoning Model" badge and asterisk indicator on tabs
  - Collapsible "Show Thinking Process" section with amber/gold styling
  - Displays chain-of-thought separately from final response
  - Handles various reasoning_details formats (string, object, array)
- **Chain-of-Thought Support** (for structured reasoning via prompts):
  - Detects `cot` object in response data (thinking, analysis, conclusion)
  - Shows "CoT" badge on tabs with structured reasoning
  - Displays ReasoningView component with three-step visualization
  - Blue "Chain-of-Thought" badge in model name area
  - Distinct from native reasoning models (uses blue vs amber theme)
- **Confidence Voting Support**:
  - Shows `ConfidenceBadge` on each tab with model's confidence (1-10)
  - Displays `AggregateConfidenceSummary` in stage header with average confidence
  - Color-coded badges: green (high), teal (good), amber (medium), orange (low), red (very low)
- **Escalation Support** (Confidence-Gated Escalation):
  - Props include `escalationInfo` for tier display
  - Shows `TierBadge` on each model tab indicating T1 or T2
  - Displays `TierSummary` in header showing escalation status
  - Shows `EscalationBanner` when escalation was triggered
  - Banner includes escalation reasons and model counts

**`components/Stage2.jsx`**
- **Critical Feature**: Tab view showing RAW evaluation text from each model
- De-anonymization happens CLIENT-SIDE for display (models receive anonymous labels)
- Shows "Extracted Ranking" below each evaluation so users can validate parsing
- Aggregate rankings shown with average position and vote count
- Explanatory text clarifies that boldface model names are for readability only
- Props: `rankings` (array), `labelToModel` (object), `aggregateRankings` (array), `useWeightedConsensus` (boolean), `weightsInfo` (object)
- **Weighted Consensus Display**:
  - "Weighted" badge in aggregate rankings header when weighted consensus enabled
  - Collapsible weights summary section showing model weights
  - Displays normalized_weight (×) for each model with history
  - Shows win rate and average rank for models with historical data
  - Aggregate rankings show `weighted_average_rank` instead of `average_rank` when weighted
  - Shows rank change indicator (positive/negative) comparing weighted vs unweighted
  - Amber/gold color scheme for weighted consensus UI elements

**`components/Stage3.jsx`**
- Final synthesized answer from chairman
- Green-tinted background (#f0fff0) to highlight conclusion
- Props: `finalResponse` (object), `streamingResponse` (string), `streamingModel` (string), `isStreaming` (boolean)
- **Additional Multi-Chairman Props**: `useMultiChairman` (boolean), `multiSyntheses` (array), `selectionStreaming` (string), `isSelecting` (boolean)
- **Additional Consensus Props**: `isConsensus` (boolean), `consensusInfo` (object)
- **Additional Refinement Props**: `useRefinement` (boolean), `refinementIterations` (array), `isRefining` (boolean), `currentRefinementIteration` (number), `refinementCritiques` (array), `refinementStreaming` (string), `refinementMaxIterations` (number), `refinementConverged` (boolean)
- **Additional Adversary Props**: `useAdversary` (boolean), `adversaryCritique` (string), `adversaryHasIssues` (boolean), `adversarySeverity` (string: critical/major/minor/none), `adversaryRevised` (boolean), `adversaryRevision` (string), `adversaryModel` (string), `isAdversaryReviewing` (boolean), `isAdversaryRevising` (boolean), `adversaryStreaming` (string), `adversaryRevisionStreaming` (string)
- **Additional Debate Props**: `useDebate` (boolean), `debatePositions` (array), `debateCritiques` (array), `debateRebuttals` (array), `debateJudgment` (string), `debateJudgmentStreaming` (string), `isDebating` (boolean), `isJudging` (boolean), `debateRound` (number), `debateModelToLabel` (object), `debateLabelToModel` (object), `debateNumRounds` (number)
- **Additional Decomposition Props**: `useDecomposition` (boolean), `subQuestions` (array), `subResults` (array), `isDecomposing` (boolean), `currentSubQuestion` (number), `totalSubQuestions` (number), `mergeStreaming` (string), `isMerging` (boolean), `decompositionFinalResponse` (string), `chairmanModel` (string), `complexityInfo` (object), `decompositionSkipped` (boolean), `decompositionComplete` (boolean)
- **Real-Time Streaming Support** (single chairman mode):
  - Displays partial response as chairman generates it
  - Green "Streaming..." indicator in header when active
  - "Generating..." badge next to chairman name during streaming
  - Blinking green cursor at end of streaming text
- **Multi-Chairman Mode Support**:
  - Displays "Multi-Chairman" badge in header
  - Renders MultiSynthesis component for ensemble synthesis display
  - Shows "Synthesizing..." or "Selecting..." indicators during process
  - Passes multi-chairman streaming state to MultiSynthesis
- **Early Consensus Exit Support**:
  - Displays "Consensus" badge in header (cyan/teal theme)
  - Green notice box explaining Stage 3 was skipped due to consensus
  - Metrics grid showing: winning model, average rank, first-place votes, confidence
  - Consensus response displayed with "Winner:" label
  - Cyan background (#ecfeff) to distinguish from normal synthesis
- **Iterative Refinement Support**:
  - Displays "Refining..." indicator during active refinement
  - Shows RefinementBadge in header when refinement was applied (with iteration count)
  - Renders RefinementView component below final response showing critique/revision history
  - Purple/violet theme for refinement-related UI elements
  - Imports RefinementView and RefinementBadge from RefinementView.jsx
- **Adversarial Validation Support**:
  - Displays "Validating..." indicator during adversary review
  - Displays "Revising..." indicator during adversary-triggered revision
  - Shows AdversaryBadge in header when adversary was applied (with severity/revised status)
  - Renders AdversaryReview component below RefinementView (if present)
  - Red/rose theme for adversary-related UI elements
  - Imports AdversaryReview and AdversaryBadge from AdversaryReview.jsx
- **Debate Mode Support**:
  - Alternative flow that replaces normal Stage 3 display entirely
  - Shows "Council Debate" title instead of "Stage 3: Final Council Answer"
  - Displays DebateBadge showing number of rounds
  - Shows "Round N..." indicator during active rounds
  - Shows "Judging..." indicator during judgment generation
  - Renders DebateView component with full debate transcript
  - Orange/amber theme for debate-related UI elements
  - Imports DebateView and DebateBadge from DebateView.jsx
- **Sub-Question Decomposition Support**:
  - Alternative flow for complex questions with map-reduce pattern
  - Shows DecompositionBadge with sub-question count in header
  - Shows "Processing N/M..." indicator during sub-council queries
  - Shows "Merging..." indicator during final merge
  - Renders DecomposedView component with full decomposition visualization
  - If question not complex enough, shows "Skipped" state and falls through to normal council
  - Teal/cyan theme (#22d3d1, #14b8a6, #0891b2, #0e7490) for decomposition UI
  - Imports DecomposedView and DecompositionBadge from DecomposedView.jsx

**`components/MultiSynthesis.jsx`**
- Displays multi-chairman synthesis results with tabbed synthesis view
- Props: `result` (complete multi-chairman result), `syntheses` (array during streaming), `selectionStreaming` (string), `isStreaming` (boolean), `isSelecting` (boolean)
- **Synthesis Tabs**:
  - Tab for each chairman's synthesis (labeled A, B, C...)
  - Checkmark icon on selected synthesis
  - Active/selected tab highlighting
  - Shows model name in each tab
- **Supreme Chairman Selection Section**:
  - Shows supreme chairman model name
  - Displays selected synthesis result
  - Collapsible "Show Evaluation Details" with reasoning
  - Yellow/amber theme for selection section
- **Final Response Section**:
  - Displays final selected/improved response
  - Green border to indicate conclusion
- Green color scheme (#22c55e) to match Stage 3 theme

**`components/CostDisplay.jsx`**
- Displays token usage and cost breakdown for a council query
- Two display modes: compact (inline summary) and expanded (full breakdown)
- Shows costs per stage (Stage 1, Stage 2, Stage 3) and total
- Displays token counts (prompt + completion) and USD costs
- Includes `ModelCostBadge` component for inline cost badges
- Green color scheme to indicate cost/value information

**`components/ConfidenceDisplay.jsx`**
- Displays confidence voting data from Stage 1
- Exports three components:
  - `ConfidenceDisplay`: Full or compact view of aggregate confidence stats
  - `ConfidenceBadge`: Inline badge showing individual model's confidence (1-10)
  - `AggregateConfidenceSummary`: Header summary with average confidence
- Color scheme based on confidence level:
  - Very High (9-10): Green (#059669)
  - High (7-8): Teal (#0d9488)
  - Medium (5-6): Amber (#d97706)
  - Low (3-4): Orange (#ea580c)
  - Very Low (1-2): Red (#dc2626)
- Props:
  - `aggregateConfidence`: Object with average, min, max, count, total_models, distribution
  - `compact`: Boolean for inline vs full display
  - `confidence`: Number (1-10) for ConfidenceBadge

**`components/TierIndicator.jsx`**
- Displays tier information for confidence-gated escalation
- Exports four components:
  - `TierIndicator`: Main tier badge showing "Tier 1 Fast" or "Tier 2 Premium"
  - `TierBadge`: Small badge for model tabs showing "T1" or "T2"
  - `EscalationBanner`: Banner displayed when escalation was triggered
    - Shows escalation icon and "Escalated to Premium Models" header
    - Lists reasons for escalation (low confidence, low agreement, etc.)
    - Displays metrics: average_confidence, model counts
  - `TierSummary`: Compact summary in header showing escalation status
    - Green theme for "No escalation needed" (confidence sufficient)
    - Amber theme for "Escalated" with model counts
  - `EscalationToggle`: Toggle control for enabling/disabling escalation mode
- Color scheme:
  - Tier 1: Blue (#3b82f6, #60a5fa) - fast, cost-effective
  - Tier 2: Amber (#f59e0b, #fbbf24) - premium, high-capability
  - Escalation: Pink/amber gradients for warnings
- Props:
  - `tier`: Number (1 or 2) for TierIndicator and TierBadge
  - `escalationInfo`: Object for EscalationBanner and TierSummary
    - Contains: escalated, tier1_model_count, tier2_model_count, total_model_count, reasons, metrics
  - `enabled`, `onChange`: For EscalationToggle

**`components/RefinementView.jsx`**
- Displays iterative refinement iterations showing critique → revision cycles
- Exports three components:
  - `RefinementView`: Main component showing all refinement iterations
    - Collapsible section with header showing iteration count and convergence status
    - Iteration cards displaying critiques and revisions
    - Real-time streaming support during active refinement
    - Progress indicator showing current iteration vs max
  - `RefinementBadge`: Badge showing refinement was applied
    - Displays iteration count (e.g., "2 iterations")
    - Shows "Converged" or "Max reached" status
    - Purple/violet color theme
  - `RefinementToggle`: Toggle control for enabling/disabling refinement mode
    - Includes max iterations dropdown (1-5 range, default 2)
    - Purple theme (#7c3aed, #8b5cf6)
- Color scheme:
  - Primary: Purple/violet (#7c3aed, #8b5cf6, #6d28d9)
  - Substantive critiques: Amber background (#fef3c7)
  - Non-substantive critiques: Gray background (#f3f4f6)
  - Revision sections: Purple gradient backgrounds
- Props:
  - `iterations`: Array of iteration objects (critiques, revision, converged)
  - `finalResponse`: The final refined response text
  - `totalIterations`: Total number of iterations performed
  - `converged`: Boolean indicating if refinement converged early
  - `totalCost`: Optional cost data for refinement
  - `isRefining`: Boolean indicating active refinement
  - `currentIteration`: Current iteration number during streaming
  - `streamingCritiques`: Array of critiques being collected in real-time
  - `streamingRevision`: Partial revision text during streaming
  - `maxIterations`: Maximum configured iterations
- For RefinementBadge: `iterations` (number), `converged` (boolean)
- For RefinementToggle: `enabled`, `onChange`, `maxIterations`, `onMaxIterationsChange`

**`components/AdversaryReview.jsx`**
- Displays adversarial validation results showing devil's advocate review
- Exports three components:
  - `AdversaryReview`: Main component showing critique and optional revision
    - Collapsible section with header showing severity and validation result
    - Adversary model information display
    - Critique section with streaming support during review
    - Revision section (only shown if critical/major issues triggered revision)
    - Result indicator: "Passed" (green), "Revised" (blue), "Issues Noted" (amber)
    - Real-time streaming support during active validation
  - `AdversaryBadge`: Badge showing adversary validation result
    - Displays severity level or "Passed"/"Revised" status
    - Color-coded: green (passed), blue (revised), red (critical), orange (major), amber (minor)
  - `AdversaryToggle`: Toggle control for enabling/disabling adversary mode
    - Red/rose theme (#e11d48, #f87171)
- Color scheme:
  - Primary: Red/rose (#e11d48, #be123c, #f87171, #fda4af)
  - Has issues: Red border/background gradients
  - No issues: Green border/background (#86efac, #dcfce7)
  - Revision section: Blue border/background (#93c5fd, #dbeafe)
- Props for AdversaryReview:
  - `critique`: The adversary's full critique text
  - `hasIssues`: Boolean indicating if genuine issues were found
  - `severity`: Severity level string (critical, major, minor, none)
  - `revised`: Boolean indicating if revision was performed
  - `revision`: The revised response text (if applicable)
  - `adversaryModel`: Model identifier for the adversary
  - `isReviewing`: Boolean indicating adversary is currently reviewing
  - `isRevising`: Boolean indicating chairman is currently revising
  - `streamingCritique`: Partial critique during streaming
  - `streamingRevision`: Partial revision during streaming
- For AdversaryBadge: `hasIssues` (boolean), `severity` (string), `revised` (boolean)
- For AdversaryToggle: `enabled` (boolean), `onChange` (callback)

**`components/DebateView.jsx`**
- Displays multi-round debate visualization with positions, critiques, rebuttals, and judgment
- Exports three components:
  - `DebateView`: Main component showing complete debate flow
    - Collapsible round sections with progress indicators
    - Position cards showing each model's initial answer (Round 1)
    - Critique flows showing critic → target relationships (Round 2)
    - Rebuttal cards showing model defenses (Round 3, optional)
    - Judgment section with streaming support (Final round)
    - Progress bar showing debate round completion
    - Real-time streaming support during active debate
  - `DebateBadge`: Small badge for Stage 3 header showing debate mode
    - Displays number of rounds (e.g., "3 Rounds")
    - Orange/amber color theme
  - `DebateToggle`: Toggle control for enabling/disabling debate mode
    - Includes sub-toggle for including rebuttal round
    - Orange/amber theme (#d97706, #fbbf24)
- Color scheme:
  - Primary: Orange/amber (#fbbf24, #d97706, #92400e, #f59e0b)
  - Positions: Light amber (#fffbeb, #fef3c7)
  - Critiques: Light orange (#fff7ed, #ffedd5)
  - Rebuttals: Light green (#f0fdf4, #dcfce7)
  - Judgment: Yellow gradient (#fef3c7 → #fcd34d)
- Props for DebateView:
  - `positions`: Array of {label, model, position} objects from Round 1
  - `critiques`: Array of {critic_label, target_label, critique} objects from Round 2
  - `rebuttals`: Array of {label, model, rebuttal} objects from Round 3
  - `judgment`: Chairman's final judgment text
  - `modelToLabel`: Mapping from model IDs to labels (A, B, C...)
  - `labelToModel`: Mapping from labels to model IDs
  - `numRounds`: Number of debate rounds (2 or 3)
  - `isDebating`: Boolean indicating debate is in progress
  - `currentRound`: Current round number during streaming
  - `judgmentStreaming`: Partial judgment text during streaming
  - `isJudging`: Boolean indicating chairman is generating judgment
- For DebateBadge: `numRounds` (number)
- For DebateToggle: `enabled` (boolean), `onChange` (callback), `includeRebuttal` (boolean), `onIncludeRebuttalChange` (callback)

**`components/DecomposedView.jsx`**
- Displays sub-question decomposition visualization with map-reduce pattern
- Exports three components:
  - `DecomposedView`: Main component showing full decomposition flow
    - Collapsible sections for sub-questions, sub-answers, and merged response
    - Progress bar showing sub-question processing completion
    - Sub-question cards with status indicators (processing, answered)
    - Sub-answer cards showing best response for each sub-question
    - Merge section with streaming support during final synthesis
    - Skip state display when question not complex enough
    - Real-time streaming support during active decomposition
  - `DecompositionBadge`: Small badge for Stage 3 header showing decomposition was applied
    - Displays sub-question count (e.g., "3 Sub-Q")
    - Teal/cyan color theme
  - `DecompositionToggle`: Toggle control for enabling/disabling decomposition mode
    - Teal/cyan theme (#14b8a6, #0891b2)
- Color scheme:
  - Primary: Teal/cyan (#22d3d1, #14b8a6, #0891b2, #0e7490)
  - Sub-questions: Light cyan backgrounds (#ecfeff, #cffafe)
  - Sub-answers: Slightly darker cyan (#a5f3fc)
  - Merge section: Gradient cyan backgrounds
  - Skipped state: Gray with cyan accents
- Props for DecomposedView:
  - `subQuestions`: Array of sub-questions generated from original question
  - `subResults`: Array of sub-council results with best answers and models
  - `finalResponse`: Merged final response from chairman
  - `chairmanModel`: Model identifier used for merging
  - `isDecomposing`: Boolean indicating decomposition is in progress
  - `currentSubQuestion`: Current sub-question index during streaming
  - `totalSubQuestions`: Total number of sub-questions
  - `mergeStreaming`: Partial merge response during streaming
  - `isMerging`: Boolean indicating merge is in progress
  - `complexityInfo`: Complexity analysis result (is_complex, confidence, reasoning)
  - `wasSkipped`: Boolean indicating decomposition was skipped (question too simple)
- For DecompositionBadge: `subQuestionCount` (number)
- For DecompositionToggle: `enabled` (boolean), `onChange` (callback)

**Styling (`*.css`)**
- Light mode theme (not dark mode)
- Primary color: #4a90e2 (blue)
- Global markdown styling in `index.css` with `.markdown-content` class
- 12px padding on all markdown content to prevent cluttered appearance

## Key Design Decisions

### Stage 2 Prompt Format
The Stage 2 prompt is very specific to ensure parseable output:
```
1. Evaluate each response individually first
2. Provide "FINAL RANKING:" header
3. Numbered list format: "1. Response C", "2. Response A", etc.
4. No additional text after ranking section
```

This strict format allows reliable parsing while still getting thoughtful evaluations.

### De-anonymization Strategy
- Models receive: "Response A", "Response B", etc.
- Backend creates mapping: `{"Response A": "openai/gpt-5.1", ...}`
- Frontend displays model names in **bold** for readability
- Users see explanation that original evaluation used anonymous labels
- This prevents bias while maintaining transparency

### Error Handling Philosophy
- Continue with successful responses if some models fail (graceful degradation)
- Never fail the entire request due to single model failure
- Log errors but don't expose to user unless all models fail

### UI/UX Transparency
- All raw outputs are inspectable via tabs
- Parsed rankings shown below raw text for validation
- Users can verify system's interpretation of model outputs
- This builds trust and allows debugging of edge cases

## Important Implementation Details

### Relative Imports
All backend modules use relative imports (e.g., `from .config import ...`) not absolute imports. This is critical for Python's module system to work correctly when running as `python -m backend.main`.

### Port Configuration
- Backend: 8001 (changed from 8000 to avoid conflict)
- Frontend: 5173 (Vite default)
- Update both `backend/main.py` and `frontend/src/api.js` if changing

### Markdown Rendering
All ReactMarkdown components must be wrapped in `<div className="markdown-content">` for proper spacing. This class is defined globally in `index.css`.

### Model Configuration
Models are now dynamically configurable via the UI (no code changes needed). Configuration is stored in `data/council_config.json` and loaded at runtime. The default configuration (used when no config file exists) is defined in `backend/config_api.py`. Chairman can be same or different from council members. The current default is Gemini as chairman per user preference.

## Common Gotchas

1. **Module Import Errors**: Always run backend as `python -m backend.main` from project root, not from backend directory
2. **CORS Issues**: Frontend must match allowed origins in `main.py` CORS middleware
3. **Ranking Parse Failures**: If models don't follow format, fallback regex extracts any "Response X" patterns in order
4. **Missing Metadata**: Metadata is ephemeral (not persisted), only available in API responses

## Implemented Features

- **Custom System Prompts**: Collapsible settings panel lets users define a system prompt that's prepended to all model queries. Persisted to localStorage.
- **Conversation Export**: Export conversations to Markdown or JSON format. Header toolbar appears when messages exist with "Export MD" and "Export JSON" buttons. Uses browser Blob API for client-side file generation.
- **Question Categories & Tagging**: Tag conversations with topics (coding, writing, analysis, etc.). Features include:
  - Tag filter dropdown in sidebar to filter conversations by tag
  - Tags displayed on conversation items in sidebar
  - "Tags" button in chat header to open TagEditor
  - Suggested tags for quick selection (coding, writing, analysis, research, creative, technical, business, learning)
  - Tags persisted to conversation JSON files
- **Model Configuration UI**: Configure council and chairman models without editing code. Features include:
  - "Configure Models" button in settings bar opens modal panel
  - Add/remove/reorder council models (minimum 2 required)
  - Chairman selection dropdown (can be council member or different model)
  - Model autocomplete with suggested models from OpenRouter
  - Quick-add buttons for popular models
  - Reset to defaults functionality
  - Configuration persisted to `data/council_config.json`
- **Reasoning Model Support**: Special handling for reasoning models (o1, o3, etc.) that expose their thinking process. Features include:
  - Backend captures `reasoning_details` from OpenRouter API responses
  - Stage 1 results include `reasoning_details` field when present
  - Frontend displays "Reasoning Model" badge on tabs with reasoning
  - Collapsible "Show Thinking Process" section with amber/gold styling
  - Chain-of-thought displayed separately from final response
  - Supports various formats (string, object with content, array of steps)
- **Cost Tracking**: Real-time display of token usage and USD costs for each council query. Features include:
  - Backend captures usage data (prompt_tokens, completion_tokens) from OpenRouter API
  - Pricing data for popular models stored in `backend/pricing.py`
  - Costs calculated per model and aggregated per stage and total
  - CostDisplay component shows breakdown by stage with percentage distribution
  - Streaming endpoint emits `costs_complete` event for real-time updates
  - Metadata includes costs in API responses (ephemeral, not persisted)
- **Confidence Voting**: Each model reports a confidence score (1-10) with their response. Features include:
  - Backend appends confidence prompt suffix to Stage 1 queries asking for "CONFIDENCE: [score]"
  - `parse_confidence()` extracts score using multiple regex patterns for robustness
  - `extract_response_without_confidence()` cleans response text for display
  - Individual confidence shown as colored badge on each model tab (1-10 scale)
  - Aggregate confidence (average, min, max, count) displayed in Stage 1 header
  - Color-coded visualization: green (9-10), teal (7-8), amber (5-6), orange (3-4), red (1-2)
  - Streaming endpoint includes `aggregate_confidence` in `stage1_complete` metadata
  - Enables future features: #14 Early Consensus Exit, #18 Confidence-Gated Escalation
- **Streaming Responses**: Real-time token-by-token streaming for Stage 1 and Stage 3. Features include:
  - Backend uses `query_model_streaming()` and `query_models_parallel_streaming()` for streaming queries
  - Stage 1 streams all council model responses in parallel, displaying tokens as they arrive
  - Stage 3 streams the chairman's response in real-time
  - Stage 2 (rankings) remains batch for simplicity (relatively fast operation)
  - Frontend handles `stage1_token`, `stage1_reasoning_token`, `stage3_token` events
  - Visual indicators: "Streaming..." badges, pulsing blue dots on active tabs, blinking cursor
  - Seamless transition from streaming to completed state when models finish
  - Enables better UX - users see responses generating in real-time instead of waiting
  - Enables future features: #9 Debate Mode, #11 Live Process Monitor work optimally with streaming
- **Performance Dashboard**: Analytics dashboard showing model performance over time. Features include:
  - Backend `analytics.py` module records results of every council query
  - Captures: model performances, rank positions, confidence scores, costs, query timing
  - Data stored in `data/analytics/model_stats.json` (separate from conversations)
  - API endpoints: `GET /api/analytics`, `GET /api/analytics/recent`, `GET /api/analytics/chairman`, `DELETE /api/analytics`
  - Frontend PerformanceDashboard component with three tabbed views:
    - **Leaderboard**: Models ranked by win rate with medal icons for top 3
    - **Model Details**: Cards showing detailed stats with rank distribution charts
    - **Chairman Stats**: Chairman model usage and cost breakdown
  - Summary statistics: total queries, unique models, syntheses count, date range
  - Refresh data button and clear all data option (with confirmation prompt)
  - "Dashboard" button in settings bar opens the modal
  - Purple/indigo color scheme (#667eea) to distinguish from config panel
- **Live Process Monitor**: Real-time side panel showing council deliberation events. Features include:
  - Backend `process_logger.py` module with verbosity levels (0=Silent, 1=Basic, 2=Standard, 3=Verbose)
  - Event categories for color-coding: stage (blue), model (purple), success (green), warning (amber), error (red), data (teal), info (gray)
  - Pre-defined event generators for common operations (stage transitions, model queries, parsing, calculations)
  - Streaming endpoint accepts `verbosity` parameter (0-3) and emits `process` events based on level
  - ProcessMonitor side panel component with:
    - Verbosity slider/knob (0-3) with labeled levels
    - Auto-scrolling event log with timestamps
    - Color-coded event display by category
    - Collapsible panel with toggle button
    - Event count badge when collapsed
  - "Process" button in settings bar toggles monitor visibility
  - Verbosity preference persisted to localStorage
  - Dark theme (#1a1a2e) to visually distinguish from main content
  - Works optimally with Streaming Responses feature for real-time event flow
- **Chain-of-Thought Orchestration**: Forces ALL models to provide explicit structured reasoning. Features include:
  - Backend `COT_PROMPT_SUFFIX` appends structured reasoning request (THINKING → ANALYSIS → CONCLUSION)
  - `parse_cot_response()` extracts sections from model responses with multiple format support
  - `stage1_collect_responses()` and streaming version accept `use_cot` parameter
  - Stage 2 ranking evaluates reasoning quality when CoT enabled (reasoning quality, analysis depth, coherence)
  - API endpoints accept `use_cot` boolean parameter
  - Frontend ReasoningView component displays three-step reasoning:
    - Step 1 (blue): Thinking - Initial thoughts and considerations
    - Step 2 (purple): Analysis - Evaluation of approaches
    - Step 3 (green): Conclusion - Final answer
  - Progress visualization in header showing completed reasoning steps
  - Collapsible sections (conclusion expanded by default)
  - CoT toggle in settings panel with slider switch
  - "CoT" indicator badge in settings bar when enabled
  - CoT badges on model tabs showing structured reasoning available
  - Setting persisted to localStorage
  - Distinct from native Reasoning Model support (prompt-based vs API-provided)
- **Multi-Chairman Synthesis**: Ensemble approach where multiple chairman models create independent syntheses. Features include:
  - Backend `multi_chairman.py` module implements two-phase synthesis:
    - Phase A: Multiple chairmen synthesize in parallel from council responses + rankings
    - Phase B: Supreme chairman evaluates and selects the best synthesis
  - `stage3_multi_chairman_synthesis()`: Parallel synthesis from configured multi-chairman models
  - `stage3_supreme_chairman_selection()`: Supreme chairman picks best synthesis with reasoning
  - `stage3_multi_chairman_streaming()`: Streaming version with real-time events
  - Configuration: `multi_chairman_models` list in `data/council_config.json`
  - Default multi-chairman pool: Gemini, Claude, GPT-4
  - Supreme chairman uses configured chairman model
  - API accepts `use_multi_chairman` boolean parameter
  - Streaming events: `multi_synthesis_start`, `synthesis_complete`, `multi_synthesis_complete`, `selection_start`, `selection_token`
  - Frontend MultiSynthesis component displays:
    - Tabbed view of all chairman syntheses (A, B, C...)
    - Supreme chairman selection section with evaluation reasoning
    - Final response with selected synthesis indicator
  - Multi-Chairman toggle in settings panel with green color scheme
  - "MC" indicator badge in settings bar when enabled
  - Selection reasoning collapsible for transparency
  - Setting persisted to localStorage
  - Provides diverse synthesis perspectives and quality assurance through ensemble approach
- **Weighted Consensus Voting**: Models that historically rank well have their votes weighted higher. Features include:
  - Backend `weights.py` module calculates weights from analytics data
  - Weight formula: base (1.0) + win_rate_bonus + rank_bonus + confidence_bonus
  - Weights clamped to 0.3-2.5 range, normalized so average = 1.0
  - Minimum 2 queries required before historical data affects weights
  - `calculate_weighted_aggregate_rankings()` uses weighted votes for ranking
  - API accepts `use_weighted_consensus` boolean parameter (default true)
  - API endpoints: `GET /api/weights`, `GET /api/weights/{model}`
  - Stage 2 metadata includes `use_weighted_consensus` and `weights_info`
  - Frontend Stage2 component displays:
    - "Weighted" badge in aggregate rankings header
    - Collapsible weights summary showing model weights with explanations
    - Weighted average rank (instead of simple average) when enabled
    - Rank change indicator showing impact of weighting
  - Weighted Consensus toggle in settings panel with amber/gold color scheme
  - "WC" indicator badge in settings bar when enabled
  - Setting persisted to localStorage (default true)
  - Uses analytics data from Performance Dashboard feature
- **Early Consensus Exit**: Skip Stage 3 synthesis when council achieves strong consensus. Features include:
  - Backend `detect_consensus()` function checks three criteria after Stage 2:
    - Average rank: top model's weighted average rank must be ≤ 1.5
    - Agreement ratio: at least 80% of models must rank top model as #1
    - Confidence threshold: average confidence must be ≥ 7
  - Consensus detection constants: `CONSENSUS_MAX_AVG_RANK`, `CONSENSUS_MIN_AGREEMENT`, `CONSENSUS_MIN_CONFIDENCE`
  - When consensus detected, Stage 3 chairman synthesis is skipped entirely
  - Consensus response is the top-ranked model's original Stage 1 response
  - API accepts `use_early_consensus` boolean parameter (default false)
  - Streaming endpoint emits `consensus_detected` event with full consensus info
  - `stage3_complete` event includes `is_consensus` and `consensus_info` when consensus triggered
  - Frontend Stage3 component displays special consensus view:
    - Cyan/teal theme (#ecfeff background, #06b6d4 accents)
    - "Consensus" badge in header
    - Green notice explaining Stage 3 was skipped
    - Metrics grid: winning model, average rank, first-place votes, confidence
    - Winner's response displayed prominently
  - Early Consensus toggle in settings panel with cyan color scheme
  - "EC" indicator badge in settings bar when enabled
  - Setting persisted to localStorage (default false)
  - Saves time and cost when models strongly agree on best response
  - Uses confidence data from Confidence Voting feature and rankings from Stage 2
- **Dynamic Model Routing**: Classify questions and route to specialized model pools. Features include:
  - Backend `router.py` module implements question classification and routing
  - Five question categories: CODING, CREATIVE, FACTUAL, ANALYSIS, GENERAL
  - Each category has optimized model pool (e.g., coding pool has best coding models)
  - Fast classifier model (Gemini Flash) determines question category with confidence score
  - Fallback keyword-based classification if LLM classifier fails
  - `classify_question()`: Async LLM classification with reasoning
  - `get_model_pool()`: Returns appropriate models for category (intersection with available)
  - `route_query()`: Main entry point returning full routing info
  - Configuration: `routing_pools` dict in `data/council_config.json`
  - API accepts `use_dynamic_routing` boolean parameter (default false)
  - Streaming endpoint emits `routing_start` and `routing_complete` events
  - `stage1_start` event includes `routing_info` when routing was applied
  - Frontend displays:
    - Routing loading indicator with orange theme during classification
    - Routing badge in Stage 1 header showing detected category
    - Badge color per category: green (coding), purple (creative), blue (factual), amber (analysis), gray (general)
    - Hover tooltip with confidence percentage and classifier reasoning
  - Dynamic Routing toggle in settings panel with orange color scheme
  - "DR" indicator badge in settings bar when enabled
  - Setting persisted to localStorage (default false)
  - Optimizes responses by selecting models best suited for question type
- **Iterative Refinement Loop**: Post-synthesis critique and revision cycles for quality improvement. Features include:
  - Backend `refinement.py` module implements the full refinement loop:
    - `is_substantive_critique()`: Determines if a critique contains actionable feedback
    - `count_substantive_critiques()`: Counts critiques that warrant revision
    - `collect_critiques()`: Council models critique the current synthesis
    - `generate_revision()`: Chairman revises based on substantive critiques
    - `run_refinement_loop_streaming()`: Full streaming refinement orchestration
  - Convergence Detection: Stops when fewer than 2 substantive critiques received
  - Max Iterations: Configurable 1-5 iterations (default 2)
  - Non-Substantive Phrases: Phrases like "no issues", "looks good" are filtered out
  - API accepts `use_refinement` boolean parameter (default false)
  - API accepts `refinement_max_iterations` integer parameter (default 2, range 1-5)
  - Streaming events:
    - `refinement_start`: Refinement beginning with max_iterations
    - `iteration_start`: New iteration starting
    - `critiques_start`: Critique collection beginning
    - `critique_complete`: Individual critique received
    - `critiques_complete`: All critiques collected with substantive_count
    - `revision_start`: Chairman revision beginning
    - `revision_token`: Token from chairman during revision
    - `revision_complete`: Revision finished
    - `iteration_complete`: Full iteration finished
    - `refinement_converged`: Stopped early due to quality convergence
    - `refinement_complete`: All refinement finished
  - RefinementView.jsx component displays:
    - Collapsible section with iteration history
    - Critique cards showing substantive vs non-substantive (amber vs gray)
    - Revision sections with purple gradient backgrounds
    - Progress indicator during active refinement
    - Convergence status display
  - RefinementBadge shows iteration count and convergence status in Stage 3 header
  - Iterative Refinement toggle in settings panel with purple theme (#7c3aed)
  - Max iterations dropdown (1-5) in settings
  - "IR" indicator badge in settings bar when enabled
  - Setting persisted to localStorage (default false)
  - Disabled when Early Consensus Exit triggers (no synthesis to refine)
- **Adversarial Validation**: Devil's advocate review to find flaws in the chairman's synthesis. Features include:
  - Backend `adversary.py` module implements adversarial validation:
    - `has_genuine_issues()`: Determines if critique contains real issues vs praise
    - `parse_severity()`: Extracts severity level from critique text
    - `run_adversarial_validation_streaming()`: Full streaming adversary validation
  - Adversary model acts as devil's advocate, critically reviewing synthesis
  - Assigns severity level: critical, major, minor, or none
  - Revision triggered only for critical/major issues (threshold configurable)
  - Default adversary model: `google/gemini-2.0-flash-001` (fast, critical reviewer)
  - API accepts `use_adversary` boolean parameter (default false)
  - API endpoint: `GET /api/adversary/config`
  - Streaming events:
    - `adversary_start`: Validation beginning with adversary model
    - `adversary_token`: Token from adversary during critique
    - `adversary_complete`: Critique finished with severity assessment
    - `adversary_revision_start`: Chairman revision beginning
    - `adversary_revision_token`: Token from chairman during revision
    - `adversary_revision_complete`: Revision finished
    - `adversary_validation_complete`: Full validation complete
  - AdversaryReview.jsx component displays:
    - Collapsible section with severity badge and validation result
    - Adversary model information
    - Critique text with streaming support
    - Revision section (if critical/major triggered revision)
    - Result indicator: Passed (green), Revised (blue), Issues Noted (amber)
  - AdversaryBadge shows validation result in Stage 3 header
  - Adversarial Validation toggle in settings panel with red/rose theme (#e11d48)
  - "AV" indicator badge in settings bar when enabled
  - Setting persisted to localStorage (default false)
  - Runs after Iterative Refinement (if enabled), validating the final synthesis
  - Provides quality assurance through critical review before delivering final answer
- **Debate Mode**: Multi-round structured debates where models argue positions and critique each other. Features include:
  - Backend `debate.py` module implements complete debate orchestration:
    - `run_debate_streaming()`: Full streaming debate with all rounds and judgment
    - `get_critique_pairs()`: Rotation system pairing critics with targets
    - `format_debate_transcript()`: Formats complete debate for chairman evaluation
    - Prompt templates for position, critique, rebuttal, and judgment phases
  - **Alternative Flow**: Debate mode bypasses the normal 3-stage council process entirely
  - **Debate Flow**:
    - Round 1 (Position): All council models state their initial answer
    - Round 2 (Critique): Each model critiques another model's position (anonymized)
    - Round 3 (Rebuttal): Each model defends their position (optional, configurable)
    - Judgment: Chairman evaluates the full debate and synthesizes best answer
  - API accepts `use_debate` boolean parameter (default false)
  - API accepts `include_rebuttal` boolean parameter (default true)
  - API endpoint: `GET /api/debate/config`
  - Streaming events:
    - `debate_start`: Debate beginning with model assignments
    - `round1_start`, `position_complete`, `round1_complete`: Position round events
    - `round2_start`, `debate_critique_complete`, `round2_complete`: Critique round events
    - `round3_start`, `rebuttal_complete`, `round3_complete`: Rebuttal round events
    - `judgment_start`, `judgment_token`, `judgment_complete`: Judgment events
    - `debate_complete`: Full debate process complete
  - DebateView.jsx component displays:
    - Collapsible round sections with progress indicators
    - Position cards showing each model's initial answer
    - Critique flows showing critic → target relationships
    - Rebuttal cards showing model defenses
    - Judgment section with streaming support
  - DebateBadge shows number of rounds in header
  - Debate Mode toggle in settings panel with orange/amber theme (#d97706)
  - "DB" indicator badge in settings bar when enabled
  - Setting persisted to localStorage (default false)
  - Include rebuttal sub-toggle (default true) controls whether Round 3 is included
  - Provides structured argumentation for complex or controversial questions
- **Sub-Question Decomposition**: Map-reduce pattern for complex questions. Features include:
  - Backend `decompose.py` module implements complete decomposition orchestration:
    - `assess_complexity()`: LLM + keyword heuristics determine if question is complex enough
    - `generate_sub_questions()`: Chairman generates focused sub-questions from original question
    - `run_mini_council()`: Parallel query all council models for a single sub-question
    - `select_best_answer()`: Pick highest confidence answer from mini-council results
    - `merge_sub_answers()`: Chairman synthesizes all best sub-answers into final response
    - `run_decomposition_streaming()`: Full streaming decomposition orchestration
  - **Alternative Flow**: Decomposition replaces normal 3-stage council process for complex questions
  - **Decomposition Flow**:
    - Complexity Assessment: Determine if question benefits from decomposition
    - Sub-Question Generation: Chairman creates 2-5 focused sub-questions
    - Mini-Councils: All council models answer each sub-question in parallel
    - Best Selection: Highest confidence answer selected for each sub-question
    - Merge: Chairman synthesizes best sub-answers into comprehensive final response
  - **Fallthrough Behavior**: If question not complex enough, falls through to normal 3-stage council
  - Complexity Detection: Uses both LLM classification and keyword heuristics
  - Default complexity threshold: 0.6 (60% confidence question is complex)
  - API accepts `use_decomposition` boolean parameter (default false)
  - API endpoint: `GET /api/decomposition/config`
  - Streaming events:
    - `decomposition_start`: Decomposition beginning
    - `complexity_analyzed`: Complexity detection complete with result
    - `decomposition_skip`: Question not complex, falling through to normal council
    - `sub_questions_generated`: Sub-questions created
    - `sub_council_start`: Beginning to process a sub-question
    - `sub_council_response`: A model responded to sub-question
    - `sub_council_complete`: Sub-question fully answered with best answer
    - `all_sub_councils_complete`: All sub-questions answered
    - `merge_start`: Chairman beginning merge
    - `merge_token`: Token from chairman during merge
    - `merge_complete`: Merge finished
    - `decomposition_complete`: Full decomposition complete
  - DecomposedView.jsx component displays:
    - Collapsible sub-questions section with status indicators
    - Sub-answer cards showing best response and model for each
    - Progress bar during processing
    - Merge section with streaming support
    - Skip state when question not complex enough
  - DecompositionBadge shows sub-question count in header
  - Sub-Question Decomposition toggle in settings panel with teal/cyan theme (#14b8a6)
  - "DQ" indicator badge in settings bar when enabled
  - Setting persisted to localStorage (default false)
  - Particularly useful for multi-part questions, research topics, and complex analysis
- **Semantic Response Caching**: Cache responses and return similar past answers. Features include:
  - Backend `embeddings.py` module generates text embeddings:
    - Uses OpenAI's text-embedding-3-small via OpenRouter API
    - Hash-based fallback when API unavailable
    - Cosine similarity for vector comparison
  - Backend `cache.py` module implements semantic caching:
    - Stores query-response pairs with vector embeddings
    - Similarity search finds matching queries above threshold
    - System prompt included in cache key for isolation
    - Statistics tracking for hits, misses, cost saved, time saved
    - Cache entries stored in `data/cache/semantic_cache.json`
    - Statistics stored in `data/cache/cache_stats.json`
  - **Caching Flow**:
    - Cache check runs before debate/decomposition/normal council flow
    - Query embedding generated and compared to cached entries
    - If similarity >= threshold (default 92%), return cached response
    - If no match, run full council and store result in cache
  - Default similarity threshold: 0.92 (92% match required)
  - Maximum cache entries: 1000 (evicts oldest when exceeded)
  - API accepts `use_cache` boolean parameter (default false)
  - API accepts `cache_similarity_threshold` parameter (default 0.92)
  - API endpoints:
    - `GET /api/cache/config`: Get cache configuration
    - `GET /api/cache/info`: Get cache info and statistics
    - `GET /api/cache/stats`: Get hit/miss statistics
    - `GET /api/cache/entries`: Get paginated cache entries
    - `DELETE /api/cache`: Clear all cache entries
    - `DELETE /api/cache/stats`: Clear cache statistics
    - `DELETE /api/cache/{cache_id}`: Delete specific entry
    - `POST /api/cache/search`: Search cache for similar query
  - Streaming events:
    - `cache_check_start`: Cache lookup beginning
    - `cache_hit`: Cache match found with similarity score and cached response
    - `cache_miss`: No cache match, proceeding with full council
    - `cache_stored`: New response stored in cache
  - Frontend App.jsx handles cache events:
    - `cacheChecking`: Loading state during cache lookup
    - `cacheHit`: Contains similarity, cached_query, cache_id, response
    - `cacheStored`: Contains cache_id, embedding_method, cache_size
  - Semantic Response Caching toggle in settings panel with green theme (#10b981)
  - "CA" indicator badge in settings bar when enabled
  - Setting persisted to localStorage (default false)
  - Saves time and API costs by returning cached responses for similar queries
  - Uses OpenAI's embeddings for high-quality semantic matching

## Future Enhancement Ideas

- Custom ranking criteria (not just accuracy/insight)

## Testing Notes

To verify API connectivity and test the system:

1. **Use the API Reference curl commands** - See `docs/API_REFERENCE.md` for ready-to-use curl examples
2. **Interactive API docs** - Visit http://localhost:8001/docs (Swagger UI) when backend is running
3. **Quick connectivity test**:
   ```bash
   curl http://localhost:8001/
   # Should return: {"status":"ok","service":"LLM Council API"}
   ```
4. **Test OpenRouter directly** (to verify API key):
   ```bash
   curl -X POST https://openrouter.ai/api/v1/chat/completions \
     -H "Authorization: Bearer $OPENROUTER_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model": "openai/gpt-4o", "messages": [{"role": "user", "content": "Hi"}]}'
   ```

## Data Flow Summary

```
User Query
    ↓
Semantic Cache Check (if enabled) → [search for similar cached query]
    ↓                                 Frontend: Show "Checking cache..."
    ├─ Cache Hit (similarity >= threshold) → [return cached response immediately]
    │   ↓                                     Frontend: Display cached stage1, stage2, stage3
    │   Complete → [skip all model queries entirely]
    │
    └─ Cache Miss → Continue to council flow below
    ↓
    ├─ Debate Mode (if enabled) → [alternative flow, bypasses normal council process]
    │   ↓
    │   Round 1: Position → [all models state initial position in parallel]
    │   ↓                    Frontend: Display position cards as they complete
    │   ↓
    │   Round 2: Critique → [each model critiques another's position]
    │   ↓                    Frontend: Display critique flows with anonymous labels
    │   ↓
    │   Round 3: Rebuttal (if enabled) → [each model defends their position]
    │   ↓                                 Frontend: Display rebuttal cards
    │   ↓
    │   Judgment: Chairman evaluates debate → [tokens streamed to frontend] → [final judgment]
    │   ↓                                              ↑
    │   └─ Frontend: Display judgment with streaming, full debate transcript in DebateView
    │   ↓
    │   Return: {debate positions, critiques, rebuttals, judgment, model mappings}
    │   ↓
    │   Record Analytics → [query recorded for performance tracking]
    │   ↓
    │   Complete → [skip normal 3-stage process entirely]
    │
    ├─ Sub-Question Decomposition (if enabled) → [alternative flow for complex questions]
    │   ↓
    │   Complexity Assessment → [LLM + keyword heuristics determine if complex]
    │   ↓                       Frontend: Display "Analyzing complexity..."
    │   ↓
    │   ├─ Not Complex → [fall through to normal council flow below]
    │   │                 Frontend: Show "Skipped" state in DecomposedView
    │   │
    │   └─ Complex → Continue decomposition
    │   ↓
    │   Sub-Question Generation → [chairman creates 2-5 focused sub-questions]
    │   ↓                         Frontend: Display sub-question cards
    │   ↓
    │   Mini-Councils: For each sub-question:
    │   ↓   ↓
    │   ↓   Parallel Query → [all council models answer sub-question]
    │   ↓   ↓                 Frontend: Update progress bar, show processing indicator
    │   ↓   ↓
    │   ↓   Best Selection → [highest confidence answer selected]
    │   ↓   ↓                 Frontend: Display sub-answer card with best model
    │   ↓
    │   Merge → [chairman synthesizes best sub-answers into final response]
    │   ↓       Frontend: Stream merge tokens in DecomposedView
    │   ↓
    │   Return: {sub_questions, sub_results, final_response, chairman_model}
    │   ↓
    │   Record Analytics → [query recorded for performance tracking]
    │   ↓
    │   Complete → [skip normal 3-stage process entirely]
    │
    └─ Normal Flow → Continue below
    ↓
Dynamic Routing (if enabled) → [classify question] → [select model pool]
    ↓                                  ↑
    └─ Frontend: Display routing progress, then category badge
    ↓
Stage 1: Parallel streaming queries → [tokens streamed to frontend] → [individual responses]
    ↓      (uses routed models if routing enabled)    ↑
    └─ Frontend: Display partial responses as tokens arrive
    ↓
Stage 2: Anonymize → Parallel ranking queries → [evaluations + parsed rankings]
    ↓                 (batch, not streamed)
Aggregate Rankings Calculation → [sorted by weighted avg position if weighted consensus enabled]
    ↓
Weights Applied (if enabled) → [model weights from analytics boost higher performers]
    ↓
Early Consensus Check (if enabled) → [detect_consensus() checks avg rank, agreement, confidence]
    ↓
    ├─ Consensus Detected → [skip Stage 3, return winning model's response directly]
    │                       Frontend: Display consensus view with metrics
    │
    └─ No Consensus → Continue to Stage 3
    ↓
Stage 3 (Single Chairman Mode):
    Chairman streaming synthesis → [tokens streamed to frontend] → [final response]
    ↓                                         ↑
    └─ Frontend: Display partial synthesis as tokens arrive

Stage 3 (Multi-Chairman Mode):
    ↓
    3A: Multi-chairman parallel synthesis → [synthesis events streamed] → [multiple syntheses]
    ↓                                              ↑
    └─ Frontend: Display each chairman's synthesis in tabs
    ↓
    3B: Supreme chairman selection → [selection tokens streamed] → [final response]
    ↓                                        ↑
    └─ Frontend: Display evaluation and selected synthesis
    ↓
Iterative Refinement (if enabled and not early exit):
    ↓
    For each iteration (up to max_iterations):
        ↓
        Collect Critiques → [council models critique current synthesis]
        ↓                   Frontend: Display streaming critiques
        ↓
        Count Substantive Critiques → [filter "looks good", "no issues", etc.]
        ↓
        ├─ Fewer than 2 substantive → [refinement_converged, stop loop]
        │
        └─ 2+ substantive → Generate Revision
            ↓
            Chairman Revision → [tokens streamed to frontend] → [revised synthesis]
            ↓                             ↑
            └─ Frontend: Display revision in RefinementView
    ↓
Adversarial Validation (if enabled and not early exit):
    ↓
    Adversary Review → [adversary model critiques synthesis]
    ↓                   Frontend: Display streaming critique
    ↓
    Parse Severity → [extract critical/major/minor/none from critique]
    ↓
    ├─ Severity is critical or major → Chairman revises based on critique
    │   ↓
    │   Chairman Revision → [tokens streamed to frontend] → [revised synthesis]
    │   ↓                             ↑
    │   └─ Frontend: Display revision in AdversaryReview
    │
    └─ Severity is minor or none → No revision needed (validation passed)
    ↓
    Final Response = revised version (if critical/major) or original (if minor/none)
    ↓
    Frontend: Display AdversaryReview with critique, severity, and revision (if any)
    ↓
Record Analytics → [model performances, ranks, costs saved to data/analytics/]
    ↓
Store in Cache (if caching enabled) → [save response with query embedding]
    ↓
Return: {stage1, stage2, stage3, metadata}
    ↓
Frontend: Display with tabs + validation UI
```

The entire flow is async/parallel where possible to minimize latency. Streaming provides real-time feedback during the longest operations (Stage 1, Stage 3, Refinement, and Adversarial Validation). Analytics are recorded after each query for the Performance Dashboard. When caching is enabled, responses are stored with semantic embeddings for future similar queries.

<!-- claude-mem-lite:begin v1 -->
## claude-mem-lite — persistent memory

PreToolUse hooks already run `mem_recall` for past lessons before Read/Edit/Write. The calls worth making proactively:

| When | Call |
|------|------|
| Before Edit/Write | hook already recalled; if a `#NN` lesson was injected, cite `#NN` next time you produce user-visible text (citing = adopting the feedback; uncited lessons decay) |
| After fixing a non-trivial bug | `mem_save(type="bugfix", lesson_learned="<root cause + fix>", importance=2)` |
| After a non-obvious architecture decision | `mem_save(type="decision", lesson_learned="<constraint + tradeoff>")` |
| Deferring to a future session | `mem_defer({title, priority:1|2|3, detail})`; when fixed, add `closes_deferred=[N]` to `mem_save` |
| Looking up past work / history | `mem_search "keywords"` · `mem_recent` · `mem_timeline` |

Path cost is round-trips, not milliseconds: the PreToolUse hook above already recalls (0 calls) — prefer it. For an explicit query, if these `mem_*` tools are deferred behind ToolSearch this session, the Bash CLI (exact path in the detail doc) is one call vs two (ToolSearch + call).

Full tool + CLI tables, citation/decay rules, and save discipline → `.claude/plugin_claude_mem_lite.md`
<!-- claude-mem-lite:end -->
