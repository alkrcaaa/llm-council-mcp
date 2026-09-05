/**
 * API client for the LLM Council backend.
 */

// Use the same host the frontend was loaded from so this also works when
// viewed from another device on the LAN (e.g. http://192.168.x.x:5173).
const API_BASE = `http://${window.location.hostname}:8001`;

export const api = {
  /**
   * List all conversations, optionally filtered by tag.
   * @param {string} tag - Optional tag to filter by
   */
  async listConversations(tag = null) {
    const url = tag
      ? `${API_BASE}/api/conversations?tag=${encodeURIComponent(tag)}`
      : `${API_BASE}/api/conversations`;
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error('Failed to list conversations');
    }
    return response.json();
  },

  /**
   * Create a new conversation.
   * @param {string} [councilId] - Optional council profile ID to bind
   */
  async createConversation(councilId = null) {
    const validCouncilId = typeof councilId === 'string' && councilId.trim() ? councilId.trim() : null;
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(validCouncilId ? { council_id: validCouncilId } : {}),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Failed to create conversation' }));
      throw new Error(err.detail || 'Failed to create conversation');
    }
    return response.json();
  },

  /**
   * Get all council profiles and active council ID.
   */
  async getCouncils() {
    const response = await fetch(`${API_BASE}/api/councils`);
    if (!response.ok) {
      throw new Error('Failed to get councils');
    }
    return response.json();
  },

  /**
   * Get currently active council profile.
   */
  async getActiveCouncil() {
    const response = await fetch(`${API_BASE}/api/councils/active`);
    if (!response.ok) {
      throw new Error('Failed to get active council');
    }
    return response.json();
  },

  /**
   * Activate a council profile by ID.
   */
  async activateCouncil(councilId) {
    const response = await fetch(`${API_BASE}/api/councils/${encodeURIComponent(councilId)}/activate`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error('Failed to activate council');
    }
    return response.json();
  },

  /**
   * Create a new custom council profile.
   */
  async createCouncil(councilData) {
    const response = await fetch(`${API_BASE}/api/councils`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(councilData),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Failed to create council' }));
      throw new Error(err.detail || 'Failed to create council');
    }
    return response.json();
  },

  /**
   * Update a council profile.
   */
  async updateCouncil(councilId, updates) {
    const response = await fetch(`${API_BASE}/api/councils/${encodeURIComponent(councilId)}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updates),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Failed to update council' }));
      throw new Error(err.detail || 'Failed to update council');
    }
    return response.json();
  },

  /**
   * Delete a custom council profile.
   */
  async deleteCouncil(councilId) {
    const response = await fetch(`${API_BASE}/api/councils/${encodeURIComponent(councilId)}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Failed to delete council' }));
      throw new Error(err.detail || 'Failed to delete council');
    }
    return response.json();
  },

  /**
   * Switch the council bound to a specific conversation.
   */
  async updateConversationCouncil(conversationId, councilId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/council`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ council_id: councilId }),
    });
    if (!response.ok) {
      throw new Error('Failed to update conversation council');
    }
    return response.json();
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`
    );
    if (!response.ok) {
      throw new Error('Failed to get conversation');
    }
    return response.json();
  },

  /**
   * Delete a specific conversation.
   * @param {string} conversationId - The conversation ID
   */
  async deleteConversation(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`,
      {
        method: 'DELETE',
      }
    );
    if (!response.ok) {
      throw new Error('Failed to delete conversation');
    }
    return response.json();
  },

  /**
   * Update tags for a conversation.
   * @param {string} conversationId - The conversation ID
   * @param {string[]} tags - Array of tag strings
   */
  async updateTags(conversationId, tags) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/tags`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ tags }),
      }
    );
    if (!response.ok) {
      throw new Error('Failed to update tags');
    }
    return response.json();
  },

  /**
   * Get all unique tags across all conversations.
   */
  async getAllTags() {
    const response = await fetch(`${API_BASE}/api/tags`);
    if (!response.ok) {
      throw new Error('Failed to get tags');
    }
    return response.json();
  },

  /**
   * Get current model configuration.
   * @returns {Promise<{council_models: string[], chairman_model: string}>}
   */
  async getConfig() {
    const response = await fetch(`${API_BASE}/api/config`);
    if (!response.ok) {
      throw new Error('Failed to get config');
    }
    return response.json();
  },

  /**
   * Update model configuration.
   * @param {string[]} councilModels - Array of model identifiers for the council
   * @param {string} chairmanModel - Model identifier for the chairman
   * @returns {Promise<{council_models: string[], chairman_model: string}>}
   */
  async updateConfig(councilModels, chairmanModel) {
    const response = await fetch(`${API_BASE}/api/config`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        council_models: councilModels,
        chairman_model: chairmanModel,
      }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to update config');
    }
    return response.json();
  },

  /**
   * Reset configuration to defaults.
   * @returns {Promise<{council_models: string[], chairman_model: string}>}
   */
  async resetConfig() {
    const response = await fetch(`${API_BASE}/api/config/reset`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error('Failed to reset config');
    }
    return response.json();
  },

  /**
   * Get list of available models for suggestions.
   * @returns {Promise<{models: string[]}>}
   */
  async getAvailableModels() {
    const response = await fetch(`${API_BASE}/api/config/models`);
    if (!response.ok) {
      throw new Error('Failed to get available models');
    }
    return response.json();
  },

  /**
   * Get list of available domain skills from dev-agent-kit.
   * @returns {Promise<{skills: Array<{id: string, title: string, description: string, category: string, badge: string}>}>}
   */
  async getSkills() {
    const response = await fetch(`${API_BASE}/api/skills`);
    if (!response.ok) {
      throw new Error('Failed to get skills');
    }
    return response.json();
  },

  /**
   * Get list of discoverable local workspace projects for context evaluation.
   */
  async getWorkspaces() {
    const response = await fetch(`${API_BASE}/api/workspaces`);
    if (!response.ok) {
      throw new Error('Failed to get workspaces');
    }
    return response.json();
  },

  /**
   * Send a message in a conversation.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {string} systemPrompt - Optional system prompt
   * @param {string} targetWorkspace - Optional local workspace project
   */
  async sendMessage(conversationId, content, systemPrompt = null, targetWorkspace = null) {
    const body = { content };
    if (systemPrompt) {
      body.system_prompt = systemPrompt;
    }
    if (targetWorkspace) {
      body.target_workspace = targetWorkspace;
    }

    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      }
    );
    if (!response.ok) {
      throw new Error('Failed to send message');
    }
    return response.json();
  },

  // =========================================================================
  // Analytics API
  // =========================================================================

  /**
   * Get comprehensive model performance statistics.
   * @returns {Promise<{models: Object, summary: Object}>}
   */
  async getAnalytics() {
    const response = await fetch(`${API_BASE}/api/analytics`);
    if (!response.ok) {
      throw new Error('Failed to get analytics');
    }
    return response.json();
  },

  /**
   * Get recent query records for detailed analysis.
   * @param {number} limit - Maximum number of queries to return (default 50)
   * @returns {Promise<{queries: Array}>}
   */
  async getRecentQueries(limit = 50) {
    const response = await fetch(`${API_BASE}/api/analytics/recent?limit=${limit}`);
    if (!response.ok) {
      throw new Error('Failed to get recent queries');
    }
    return response.json();
  },

  /**
   * Get chairman model usage statistics.
   * @returns {Promise<{models: Object, total_syntheses: number}>}
   */
  async getChairmanAnalytics() {
    const response = await fetch(`${API_BASE}/api/analytics/chairman`);
    if (!response.ok) {
      throw new Error('Failed to get chairman analytics');
    }
    return response.json();
  },

  /**
   * Clear all analytics data.
   * WARNING: This permanently deletes all recorded statistics.
   * @returns {Promise<{status: string, message: string}>}
   */
  async clearAnalytics() {
    const response = await fetch(`${API_BASE}/api/analytics`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Failed to clear analytics');
    }
    return response.json();
  },

  // =========================================================================
  // Weights API
  // =========================================================================

  /**
   * Get model weights based on historical performance.
   * @returns {Promise<{weights: Object, has_historical_data: boolean, models_with_history: number, weight_range: Object, explanation: string}>}
   */
  async getWeights() {
    const response = await fetch(`${API_BASE}/api/weights`);
    if (!response.ok) {
      throw new Error('Failed to get weights');
    }
    return response.json();
  },

  /**
   * Get weight for a specific model.
   * @param {string} model - The model identifier
   * @returns {Promise<{weight: number, normalized_weight: number, win_rate: number, average_rank: number, total_queries: number, has_history: boolean, weight_explanation: string}>}
   */
  async getModelWeight(model) {
    const response = await fetch(`${API_BASE}/api/weights/${encodeURIComponent(model)}`);
    if (!response.ok) {
      throw new Error('Failed to get model weight');
    }
    return response.json();
  },

  // =========================================================================
  // Routing API
  // =========================================================================

  /**
   * Get routing pool configuration.
   * @returns {Promise<{pools: Object, categories: Object}>}
   */
  async getRoutingPools() {
    const response = await fetch(`${API_BASE}/api/routing/pools`);
    if (!response.ok) {
      throw new Error('Failed to get routing pools');
    }
    return response.json();
  },

  /**
   * Classify a question without running a full query.
   * @param {string} query - The question to classify
   * @returns {Promise<{category: string, confidence: number, reasoning: string, models: string[], is_routed: boolean}>}
   */
  async classifyQuestion(query) {
    const response = await fetch(`${API_BASE}/api/routing/classify?query=${encodeURIComponent(query)}`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error('Failed to classify question');
    }
    return response.json();
  },

  // =========================================================================
  // Escalation API
  // =========================================================================

  /**
   * Get tier configuration for confidence-gated escalation.
   * @returns {Promise<{tier1_models: string[], tier2_models: string[], thresholds: Object, description: Object, escalation_rules: string[]}>}
   */
  async getEscalationTiers() {
    const response = await fetch(`${API_BASE}/api/escalation/tiers`);
    if (!response.ok) {
      throw new Error('Failed to get escalation tiers');
    }
    return response.json();
  },

  /**
   * Get current escalation thresholds.
   * @returns {Promise<{confidence_threshold: number, min_confidence_threshold: number, agreement_threshold: number}>}
   */
  async getEscalationThresholds() {
    const response = await fetch(`${API_BASE}/api/escalation/thresholds`);
    if (!response.ok) {
      throw new Error('Failed to get escalation thresholds');
    }
    return response.json();
  },

  // =========================================================================
  // Refinement API
  // =========================================================================

  /**
   * Get refinement configuration.
   * @returns {Promise<{default_max_iterations: number, min_critiques_for_revision: number, non_substantive_phrases: string[]}>}
   */
  async getRefinementConfig() {
    const response = await fetch(`${API_BASE}/api/refinement/config`);
    if (!response.ok) {
      throw new Error('Failed to get refinement config');
    }
    return response.json();
  },

  // =========================================================================
  // Adversary API
  // =========================================================================

  /**
   * Get adversarial validation configuration.
   * @returns {Promise<{adversary_model: string, severity_levels: string[], revision_threshold: string[], no_issues_phrases: string[]}>}
   */
  async getAdversaryConfig() {
    const response = await fetch(`${API_BASE}/api/adversary/config`);
    if (!response.ok) {
      throw new Error('Failed to get adversary config');
    }
    return response.json();
  },

  // =========================================================================
  // Debate API
  // =========================================================================

  /**
   * Get debate mode configuration.
   * @returns {Promise<{default_num_rounds: number, include_rebuttal: boolean, round_names: string[], description: string}>}
   */
  async getDebateConfig() {
    const response = await fetch(`${API_BASE}/api/debate/config`);
    if (!response.ok) {
      throw new Error('Failed to get debate config');
    }
    return response.json();
  },

  // =========================================================================
  // Decomposition API
  // =========================================================================

  /**
   * Get sub-question decomposition configuration.
   * @returns {Promise<{default_max_sub_questions: number, complexity_threshold: number, decomposer_model: string, complexity_indicators: string[], description: string}>}
   */
  async getDecompositionConfig() {
    const response = await fetch(`${API_BASE}/api/decomposition/config`);
    if (!response.ok) {
      throw new Error('Failed to get decomposition config');
    }
    return response.json();
  },

  // =========================================================================
  // Cache API
  // =========================================================================

  /**
   * Get cache configuration.
   * @returns {Promise<{similarity_threshold: number, max_cache_entries: number, use_api_embeddings: boolean, embedding_model: string, cache_dir: string, description: string}>}
   */
  async getCacheConfig() {
    const response = await fetch(`${API_BASE}/api/cache/config`);
    if (!response.ok) {
      throw new Error('Failed to get cache config');
    }
    return response.json();
  },

  /**
   * Get cache information and statistics.
   * @returns {Promise<{cache_size: number, max_entries: number, similarity_threshold: number, total_entry_hits: number, stats: Object}>}
   */
  async getCacheInfo() {
    const response = await fetch(`${API_BASE}/api/cache/info`);
    if (!response.ok) {
      throw new Error('Failed to get cache info');
    }
    return response.json();
  },

  /**
   * Get cache hit/miss statistics.
   * @returns {Promise<{total_queries: number, cache_hits: number, cache_misses: number, hit_rate: number, total_cost_saved: number, total_time_saved_ms: number}>}
   */
  async getCacheStats() {
    const response = await fetch(`${API_BASE}/api/cache/stats`);
    if (!response.ok) {
      throw new Error('Failed to get cache stats');
    }
    return response.json();
  },

  /**
   * Get paginated list of cache entries.
   * @param {number} limit - Maximum entries to return (default 50)
   * @param {number} offset - Number of entries to skip (default 0)
   * @returns {Promise<{entries: Array, total: number, limit: number, offset: number, has_more: boolean}>}
   */
  async getCacheEntries(limit = 50, offset = 0) {
    const response = await fetch(`${API_BASE}/api/cache/entries?limit=${limit}&offset=${offset}`);
    if (!response.ok) {
      throw new Error('Failed to get cache entries');
    }
    return response.json();
  },

  /**
   * Clear all cache entries.
   * WARNING: This permanently deletes all cached responses.
   * @returns {Promise<{success: boolean, entries_cleared: number, message: string}>}
   */
  async clearCache() {
    const response = await fetch(`${API_BASE}/api/cache`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Failed to clear cache');
    }
    return response.json();
  },

  /**
   * Clear cache statistics.
   * @returns {Promise<{success: boolean, message: string}>}
   */
  async clearCacheStats() {
    const response = await fetch(`${API_BASE}/api/cache/stats`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Failed to clear cache stats');
    }
    return response.json();
  },

  /**
   * Delete a specific cache entry.
   * @param {string} cacheId - The cache entry ID to delete
   * @returns {Promise<{success: boolean, deleted: string, message: string}>}
   */
  async deleteCacheEntry(cacheId) {
    const response = await fetch(`${API_BASE}/api/cache/entries/${encodeURIComponent(cacheId)}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Failed to delete cache entry');
    }
    return response.json();
  },

  /**
   * Search cache for a similar query.
   * @param {string} query - The query text to search for
   * @param {string} systemPrompt - Optional system prompt to match
   * @param {number} similarityThreshold - Minimum similarity for match (default 0.92)
   * @returns {Promise<{found: boolean, similarity?: number, cached_query?: string, cache_id?: string}>}
   */
  async searchCache(query, systemPrompt = null, similarityThreshold = 0.92) {
    let url = `${API_BASE}/api/cache/search?query=${encodeURIComponent(query)}&similarity_threshold=${similarityThreshold}`;
    if (systemPrompt) {
      url += `&system_prompt=${encodeURIComponent(systemPrompt)}`;
    }
    const response = await fetch(url, { method: 'POST' });
    if (!response.ok) {
      throw new Error('Failed to search cache');
    }
    return response.json();
  },

  /**
   * Get embedding configuration.
   * @returns {Promise<{default_model: string, embedding_dimension: number, hash_dimension: number, api_url: string, description: string}>}
   */
  async getEmbeddingsConfig() {
    const response = await fetch(`${API_BASE}/api/embeddings/config`);
    if (!response.ok) {
      throw new Error('Failed to get embeddings config');
    }
    return response.json();
  },

  // =========================================================================
  // Messaging API
  // =========================================================================

  /**
   * Send a message and receive streaming updates.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {function} onEvent - Callback function for each event: (eventType, data) => void
   * @param {string} systemPrompt - Optional system prompt
   * @param {number} verbosity - Process monitor verbosity level (0-3, default 0)
   * @param {boolean} useCot - Enable Chain-of-Thought mode (default false)
   * @param {boolean} useMultiChairman - Enable Multi-Chairman mode (default false)
   * @param {boolean} useWeightedConsensus - Enable Weighted Consensus mode (default true)
   * @param {boolean} useEarlyConsensus - Enable Early Consensus Exit mode (default false)
   * @param {boolean} useDynamicRouting - Enable Dynamic Model Routing (default false)
   * @param {boolean} useEscalation - Enable Confidence-Gated Escalation (default false)
   * @param {boolean} useRefinement - Enable Iterative Refinement (default false)
   * @param {number} refinementMaxIterations - Max refinement iterations (default 2)
   * @param {boolean} useAdversary - Enable Adversarial Validation (default false)
   * @param {boolean} useDebate - Enable Debate Mode (default false)
   * @param {boolean} includeRebuttal - Include Round 3 rebuttal in debate (default true)
   * @param {boolean} useDecomposition - Enable Sub-Question Decomposition (default false)
   * @param {boolean} useCache - Enable Response Caching (default false)
   * @param {number} cacheSimilarityThreshold - Minimum similarity for cache hit (default 0.92)
   * @param {string} targetWorkspace - Optional local workspace project
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, onEvent, systemPrompt = null, verbosity = 0, useCot = false, useMultiChairman = false, useWeightedConsensus = true, useEarlyConsensus = false, useDynamicRouting = false, useEscalation = false, useRefinement = false, refinementMaxIterations = 2, useAdversary = false, useDebate = false, includeRebuttal = true, useDecomposition = false, useCache = false, cacheSimilarityThreshold = 0.92, councilId = null, targetWorkspace = null) {
    const body = {
      content,
      verbosity,
      use_cot: useCot,
      use_multi_chairman: useMultiChairman,
      use_weighted_consensus: useWeightedConsensus,
      use_early_consensus: useEarlyConsensus,
      use_dynamic_routing: useDynamicRouting,
      use_escalation: useEscalation,
      use_refinement: useRefinement,
      refinement_max_iterations: refinementMaxIterations,
      use_adversary: useAdversary,
      use_debate: useDebate,
      include_rebuttal: includeRebuttal,
      use_decomposition: useDecomposition,
      use_cache: useCache,
      cache_similarity_threshold: cacheSimilarityThreshold,
    };
    if (councilId) {
      body.council_id = councilId;
    }
    if (systemPrompt) {
      body.system_prompt = systemPrompt;
    }
    if (targetWorkspace) {
      body.target_workspace = targetWorkspace;
    }

    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to send message');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const event = JSON.parse(data);
            onEvent(event.type, event);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },
};
