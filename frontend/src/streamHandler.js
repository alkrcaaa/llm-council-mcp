/**
 * Stream event dispatcher for LLM Council and Round Table conversations.
 * Decouples SSE event handling from UI components and supports:
 * - Direct live streaming (on user submit)
 * - Stream reconnecting / recovery (on F5, page reload, or tab switch)
 */

export function createStreamDispatcher({
  targetConversationId,
  _setCurrentConversation,
  activeStreamRef,
  setLoadingConversationId,
  loadConversation,
  loadConversations,
  setProcessEvents,
  selectedTag,
}) {
  const setCurrentConversation = (updater) => {
    let updatedAssistantMsg = null;
    _setCurrentConversation((prev) => {
      if (!prev || prev.id !== targetConversationId) {
        return prev;
      }
      let next;
      try {
        next = typeof updater === 'function' ? updater(prev) : updater;
      } catch (err) {
        console.error('Dropped a malformed stream update instead of crashing:', err);
        return prev;
      }
      if (next && next.messages && next.messages.length > 0) {
        const last = next.messages[next.messages.length - 1];
        if (last && last.role === 'assistant') {
          updatedAssistantMsg = last;
        }
      }
      return next;
    });
    if (updatedAssistantMsg) {
      activeStreamRef.current[targetConversationId] = updatedAssistantMsg;
    }
  };

  return (eventType, event) => {
        switch (eventType) {
          case 'roundtable_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.isRoundTable = true;
              if (!lastMsg.roundtableStreaming || event.hop > 1) {
                if (!lastMsg.roundtableStreaming) lastMsg.roundtableStreaming = {};
              } else {
                lastMsg.roundtableStreaming = {};
              }
              (event.target_models || []).forEach((m) => {
                lastMsg.roundtableStreaming[m] = '';
              });
              if (!lastMsg.roundtableResponses || event.hop > 1) {
                if (!lastMsg.roundtableResponses) lastMsg.roundtableResponses = [];
              } else {
                lastMsg.roundtableResponses = [];
              }
              lastMsg.targetModels = event.target_models;
              lastMsg.isBroadcast = event.is_broadcast;
              return { ...prev, messages };
            });
            break;

          case 'roundtable_token':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              if (!lastMsg.roundtableStreaming) lastMsg.roundtableStreaming = {};
              lastMsg.roundtableStreaming[event.model] = (lastMsg.roundtableStreaming[event.model] || '') + event.content;
              return { ...prev, messages };
            });
            break;

          case 'roundtable_model_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              if (!lastMsg.roundtableResponses) lastMsg.roundtableResponses = [];
              lastMsg.roundtableResponses.push({
                model: event.model,
                content: event.content,
                usage: event.usage,
                cost: event.cost,
              });
              if (lastMsg.roundtableStreaming) {
                delete lastMsg.roundtableStreaming[event.model];
              }
              return { ...prev, messages };
            });
            break;

          case 'roundtable_model_error':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              if (!lastMsg.roundtableResponses) lastMsg.roundtableResponses = [];
              lastMsg.roundtableResponses.push({
                model: event.model,
                content: `⚠️ *Model failed to respond: ${event.error || 'Unknown error'}*`,
                isError: true,
              });
              if (lastMsg.roundtableStreaming) {
                delete lastMsg.roundtableStreaming[event.model];
              }
              return { ...prev, messages };
            });
            break;

          case 'roundtable_complete':
            if (activeStreamRef.current) {
              delete activeStreamRef.current[targetConversationId];
            }
            setLoadingConversationId(null);
            loadConversation(targetConversationId);
            loadConversations(selectedTag);
            break;

          case 'context_ingested':
            // Evaluation context enriched with local workspace & external repos
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.ingestMeta = event.metadata;
              return { ...prev, messages };
            });
            break;

          case 'research_complete':
            // Autonomous technology scouting discovered candidates
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.researchMeta = event.metadata;
              return { ...prev, messages };
            });
            break;

          case 'routing_start':
            // Dynamic routing classification starting
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.routing = true;
              return { ...prev, messages };
            });
            break;

          case 'routing_complete':
            // Dynamic routing classification finished
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.routing = false;
              lastMsg.routingInfo = event.data;
              return { ...prev, messages };
            });
            break;

          case 'tier1_start':
            // Tier 1 escalation starting
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.tier1 = true;
              lastMsg.currentTier = 1;
              return { ...prev, messages };
            });
            break;

          case 'tier1_complete':
            // Tier 1 complete, checking if escalation needed
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.tier1 = false;
              return { ...prev, messages };
            });
            break;

          case 'escalation_triggered':
            // Escalation is triggered, Tier 2 will run
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.escalated = true;
              lastMsg.escalationInfo = event.data;
              return { ...prev, messages };
            });
            break;

          case 'tier2_start':
            // Tier 2 escalation starting
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.tier2 = true;
              lastMsg.currentTier = 2;
              return { ...prev, messages };
            });
            break;

          case 'stage1_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.stage1 = true;
              // Initialize streaming state for Stage 1
              lastMsg.stage1Streaming = {};
              lastMsg.stage1ReasoningStreaming = {};
              return { ...prev, messages };
            });
            break;

          case 'stage1_token':
            // Accumulate tokens for a specific model
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              const model = event.model;
              // Initialize or append to streaming content
              if (!lastMsg.stage1Streaming) {
                lastMsg.stage1Streaming = {};
              }
              lastMsg.stage1Streaming[model] = (lastMsg.stage1Streaming[model] || '') + event.content;
              return { ...prev, messages };
            });
            break;

          case 'stage1_reasoning_token':
            // Accumulate reasoning tokens for a specific model
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              const model = event.model;
              if (!lastMsg.stage1ReasoningStreaming) {
                lastMsg.stage1ReasoningStreaming = {};
              }
              lastMsg.stage1ReasoningStreaming[model] = (lastMsg.stage1ReasoningStreaming[model] || '') + event.content;
              return { ...prev, messages };
            });
            break;

          case 'stage1_model_complete':
            // A single model has finished - update its entry in stage1
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              // Initialize stage1 array if needed
              if (!lastMsg.stage1) {
                lastMsg.stage1 = [];
              }
              // Add or update the model's response
              const existingIndex = lastMsg.stage1.findIndex(r => r.model === event.data.model);
              if (existingIndex >= 0) {
                lastMsg.stage1[existingIndex] = event.data;
              } else {
                lastMsg.stage1.push(event.data);
              }
              // Clear streaming state for this model
              if (lastMsg.stage1Streaming) {
                delete lastMsg.stage1Streaming[event.data.model];
              }
              if (lastMsg.stage1ReasoningStreaming) {
                delete lastMsg.stage1ReasoningStreaming[event.data.model];
              }
              return { ...prev, messages };
            });
            break;

          case 'stage1_error':
            // Model error during Stage 1 - log but continue
            console.warn('Stage 1 model error:', event.model, event.error);
            break;

          case 'stage1_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.stage1 = event.data;
              lastMsg.loading.stage1 = false;
              lastMsg.loading.tier1 = false;
              lastMsg.loading.tier2 = false;
              // Clear streaming state
              lastMsg.stage1Streaming = null;
              lastMsg.stage1ReasoningStreaming = null;
              // Store aggregate confidence from Stage 1 metadata
              if (event.metadata?.aggregate_confidence) {
                lastMsg.metadata = {
                  ...lastMsg.metadata,
                  aggregate_confidence: event.metadata.aggregate_confidence,
                };
              }
              // Store escalation info from Stage 1 metadata
              if (event.metadata?.escalation_info) {
                lastMsg.escalationInfo = event.metadata.escalation_info;
                lastMsg.escalated = event.metadata.escalation_info.escalated;
              }
              return { ...prev, messages };
            });
            break;

          case 'stage2_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.stage2 = true;
              return { ...prev, messages };
            });
            break;

          case 'stage2_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.stage2 = event.data;
              lastMsg.metadata = {
                ...lastMsg.metadata,
                ...event.metadata,
              };
              lastMsg.loading.stage2 = false;
              return { ...prev, messages };
            });
            break;

          case 'consensus_detected':
            // Early consensus was detected - Stage 3 will be skipped
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.consensusInfo = event.data;
              lastMsg.isConsensus = true;
              return { ...prev, messages };
            });
            break;

          case 'stage3_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.stage3 = true;
              // Check if multi-chairman mode
              if (event.use_multi_chairman) {
                lastMsg.useMultiChairman = true;
                lastMsg.multiSyntheses = [];
              } else {
                // Initialize streaming state for Stage 3
                lastMsg.stage3Streaming = '';
              }
              return { ...prev, messages };
            });
            break;

          case 'multi_synthesis_start':
            // Multi-chairman synthesis starting
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.multiSyntheses = [];
              return { ...prev, messages };
            });
            break;

          case 'synthesis_complete':
            // A chairman has finished synthesizing
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.multiSyntheses = [...(lastMsg.multiSyntheses || []), event.data];
              return { ...prev, messages };
            });
            break;

          case 'multi_synthesis_complete':
            // All chairmen have finished synthesizing
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.multiSyntheses = event.syntheses;
              return { ...prev, messages };
            });
            break;

          case 'selection_start':
            // Supreme chairman selection starting
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.isSelecting = true;
              lastMsg.selectionStreaming = '';
              return { ...prev, messages };
            });
            break;

          case 'selection_token':
            // Supreme chairman token
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.selectionStreaming = (lastMsg.selectionStreaming || '') + event.content;
              return { ...prev, messages };
            });
            break;

          case 'stage3_token':
            // Accumulate tokens for chairman response (single chairman mode)
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.stage3Streaming = (lastMsg.stage3Streaming || '') + event.content;
              // Also store the model for display
              if (!lastMsg.stage3StreamingModel) {
                lastMsg.stage3StreamingModel = event.model;
              }
              return { ...prev, messages };
            });
            break;

          case 'stage3_error':
            console.error('Stage 3 error:', event.error);
            break;

          case 'stage3_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.stage3 = event.data;
              lastMsg.loading.stage3 = false;
              // Clear streaming state
              lastMsg.stage3Streaming = null;
              lastMsg.stage3StreamingModel = null;
              // Clear multi-chairman streaming state
              lastMsg.isSelecting = false;
              lastMsg.selectionStreaming = null;
              // Mark if this was multi-chairman
              if (event.use_multi_chairman) {
                lastMsg.useMultiChairman = true;
              }
              // Mark if this was a consensus exit
              if (event.is_consensus) {
                lastMsg.isConsensus = true;
                lastMsg.consensusInfo = event.consensus_info;
              }
              return { ...prev, messages };
            });
            break;

          case 'costs_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              // Add costs to metadata
              lastMsg.metadata = {
                ...lastMsg.metadata,
                costs: event.data,
              };
              return { ...prev, messages };
            });
            break;

          case 'title_complete':
            // Reload conversations to get updated title
            loadConversations();
            break;

          case 'complete':
            // Stream complete, reload conversations list and clean active stream cache
            if (activeStreamRef.current) {
              delete activeStreamRef.current[targetConversationId];
            }
            loadConversation(targetConversationId);
            loadConversations();
            setLoadingConversationId(null);
            break;

          case 'error':
            console.error('Stream error:', event.message);
            if (activeStreamRef.current) {
              delete activeStreamRef.current[targetConversationId];
            }
            setLoadingConversationId(null);
            break;

          case 'refinement_start':
            // Iterative refinement starting
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.refinement = true;
              lastMsg.isRefining = true;
              lastMsg.refinementIterations = [];
              lastMsg.refinementCritiques = [];
              lastMsg.refinementStreaming = '';
              lastMsg.currentRefinementIteration = 0;
              if (event.max_iterations) {
                lastMsg.refinementMaxIterations = event.max_iterations;
              }
              return { ...prev, messages };
            });
            break;

          case 'iteration_start':
            // New refinement iteration starting
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.currentRefinementIteration = event.iteration;
              lastMsg.refinementCritiques = [];
              lastMsg.refinementStreaming = '';
              return { ...prev, messages };
            });
            break;

          case 'critiques_start':
            // Starting to collect critiques
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.refinementCritiques = [];
              return { ...prev, messages };
            });
            break;

          case 'critique_complete':
            // A single critique has been received
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.refinementCritiques = [...(lastMsg.refinementCritiques || []), {
                model: event.model,
                critique: event.critique,
                is_substantive: event.is_substantive,
              }];
              return { ...prev, messages };
            });
            break;

          case 'critiques_complete':
            // All critiques collected for this iteration
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.refinementCritiques = event.critiques;
              return { ...prev, messages };
            });
            break;

          case 'revision_start':
            // Chairman starting revision
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.refinementStreaming = '';
              return { ...prev, messages };
            });
            break;

          case 'revision_token':
            // Accumulate revision tokens
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.refinementStreaming = (lastMsg.refinementStreaming || '') + event.content;
              return { ...prev, messages };
            });
            break;

          case 'revision_complete':
            // Revision finished for this iteration
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.refinementStreaming = '';
              return { ...prev, messages };
            });
            break;

          case 'iteration_complete':
            // Full iteration complete, add to iterations list
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              const newIteration = {
                iteration: event.iteration,
                critiques: lastMsg.refinementCritiques || [],
                revision: event.revision,
                substantive_critique_count: (lastMsg.refinementCritiques || []).filter(c => c.is_substantive).length,
              };
              lastMsg.refinementIterations = [...(lastMsg.refinementIterations || []), newIteration];
              lastMsg.refinementCritiques = [];
              lastMsg.refinementStreaming = '';
              return { ...prev, messages };
            });
            break;

          case 'refinement_converged':
            // Refinement converged early
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.refinementConverged = true;
              // Add final iteration with convergence info
              const convergenceIteration = {
                iteration: event.iteration,
                critiques: lastMsg.refinementCritiques || [],
                stopped: true,
                stop_reason: event.reason,
                substantive_critique_count: (lastMsg.refinementCritiques || []).filter(c => c.is_substantive).length,
              };
              lastMsg.refinementIterations = [...(lastMsg.refinementIterations || []), convergenceIteration];
              return { ...prev, messages };
            });
            break;

          case 'refinement_complete':
            // Full refinement loop complete
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.refinement = false;
              lastMsg.isRefining = false;
              lastMsg.refinementIterations = event.iterations;
              lastMsg.refinementConverged = event.converged;
              lastMsg.refinementCritiques = [];
              lastMsg.refinementStreaming = '';
              // Update stage3 response with refined version
              if (lastMsg.stage3 && event.final_response) {
                lastMsg.stage3.response = event.final_response;
                lastMsg.stage3.refinement_applied = true;
                lastMsg.stage3.refinement_iterations = event.total_iterations;
                lastMsg.stage3.refinement_converged = event.converged;
              }
              return { ...prev, messages };
            });
            break;

          case 'revision_error':
            // Error during revision
            console.warn('Revision error:', event.error);
            break;

          case 'adversary_start':
            // Adversarial validation starting
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.adversary = true;
              lastMsg.isAdversaryReviewing = true;
              lastMsg.adversaryStreaming = '';
              lastMsg.adversaryModel = event.adversary_model;
              return { ...prev, messages };
            });
            break;

          case 'adversary_token':
            // Accumulate adversary critique tokens
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.adversaryStreaming = (lastMsg.adversaryStreaming || '') + event.content;
              return { ...prev, messages };
            });
            break;

          case 'adversary_complete':
            // Adversary review complete
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.isAdversaryReviewing = false;
              lastMsg.adversaryCritique = event.critique;
              lastMsg.adversaryHasIssues = event.has_issues;
              lastMsg.adversarySeverity = event.severity;
              lastMsg.adversaryStreaming = '';
              return { ...prev, messages };
            });
            break;

          case 'adversary_error':
            // Adversary error
            console.warn('Adversary error:', event.error);
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.isAdversaryReviewing = false;
              lastMsg.loading.adversary = false;
              return { ...prev, messages };
            });
            break;

          case 'adversary_revision_start':
            // Chairman starting revision based on adversary feedback
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.isAdversaryRevising = true;
              lastMsg.adversaryRevisionStreaming = '';
              return { ...prev, messages };
            });
            break;

          case 'adversary_revision_token':
            // Accumulate revision tokens
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.adversaryRevisionStreaming = (lastMsg.adversaryRevisionStreaming || '') + event.content;
              return { ...prev, messages };
            });
            break;

          case 'adversary_revision_complete':
            // Revision complete
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.isAdversaryRevising = false;
              lastMsg.adversaryRevision = event.response;
              lastMsg.adversaryRevisionStreaming = '';
              return { ...prev, messages };
            });
            break;

          case 'adversary_revision_error':
            // Revision error
            console.warn('Adversary revision error:', event.error);
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.isAdversaryRevising = false;
              return { ...prev, messages };
            });
            break;

          case 'adversary_validation_complete':
            // Full adversarial validation complete
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.adversary = false;
              lastMsg.isAdversaryReviewing = false;
              lastMsg.isAdversaryRevising = false;
              lastMsg.adversaryResult = {
                issues_found: event.issues_found,
                severity: event.severity,
                revised: event.revised,
              };
              // Update stage3 response with validated/revised version
              if (lastMsg.stage3 && event.final_response) {
                lastMsg.stage3.response = event.final_response;
                lastMsg.stage3.adversary_applied = true;
                lastMsg.stage3.adversary_issues_found = event.issues_found;
                lastMsg.stage3.adversary_severity = event.severity;
                lastMsg.stage3.adversary_revised = event.revised;
              }
              return { ...prev, messages };
            });
            break;

          // =================================================================
          // Debate Mode Events
          // =================================================================

          case 'debate_start':
            // Debate mode starting
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.isDebating = true;
              lastMsg.debateRound = 0;
              lastMsg.debateModelToLabel = event.model_to_label || {};
              lastMsg.debateLabelToModel = event.label_to_model || {};
              lastMsg.debateNumRounds = event.num_rounds || 3;
              return { ...prev, messages };
            });
            break;

          case 'round1_start':
            // Position round starting
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.debateRound = 1;
              return { ...prev, messages };
            });
            break;

          case 'position_complete':
            // A position has been received
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.debatePositions = [...(lastMsg.debatePositions || []), {
                model: event.model,
                position: event.position,
                label: event.label,
              }];
              return { ...prev, messages };
            });
            break;

          case 'round1_complete':
            // All positions collected
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.debatePositions = event.positions || lastMsg.debatePositions;
              return { ...prev, messages };
            });
            break;

          case 'round2_start':
            // Critique round starting
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.debateRound = 2;
              return { ...prev, messages };
            });
            break;

          case 'debate_critique_complete':
            // A debate critique has been received (different from refinement critique)
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.debateCritiques = [...(lastMsg.debateCritiques || []), {
                critic: event.critic,
                target: event.target,
                critique: event.critique,
                critic_label: event.critic_label,
                target_label: event.target_label,
              }];
              return { ...prev, messages };
            });
            break;

          case 'round2_complete':
            // All critiques collected
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.debateCritiques = event.critiques || lastMsg.debateCritiques;
              return { ...prev, messages };
            });
            break;

          case 'round3_start':
            // Rebuttal round starting
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.debateRound = 3;
              return { ...prev, messages };
            });
            break;

          case 'rebuttal_complete':
            // A rebuttal has been received
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.debateRebuttals = [...(lastMsg.debateRebuttals || []), {
                model: event.model,
                rebuttal: event.rebuttal,
                label: event.label,
              }];
              return { ...prev, messages };
            });
            break;

          case 'round3_complete':
            // All rebuttals collected
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.debateRebuttals = event.rebuttals || lastMsg.debateRebuttals;
              return { ...prev, messages };
            });
            break;

          case 'judgment_start':
            // Chairman judgment starting
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.isJudging = true;
              lastMsg.debateRound = 4; // After all debate rounds
              return { ...prev, messages };
            });
            break;

          case 'judgment_token':
            // Accumulate judgment tokens
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.debateJudgmentStreaming = (lastMsg.debateJudgmentStreaming || '') + event.content;
              return { ...prev, messages };
            });
            break;

          case 'judgment_complete':
            // Judgment finished
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.isJudging = false;
              lastMsg.debateJudgment = event.judgment;
              lastMsg.debateJudgmentStreaming = '';
              return { ...prev, messages };
            });
            break;

          case 'judgment_error':
            // Judgment error
            console.warn('Judgment error:', event.error);
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.isJudging = false;
              return { ...prev, messages };
            });
            break;

          case 'debate_complete':
            // Full debate complete
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.isDebating = false;
              lastMsg.debatePositions = event.positions || lastMsg.debatePositions;
              lastMsg.debateCritiques = event.critiques || lastMsg.debateCritiques;
              lastMsg.debateRebuttals = event.rebuttals || lastMsg.debateRebuttals;
              lastMsg.debateJudgment = event.judgment || lastMsg.debateJudgment;
              lastMsg.debateModelToLabel = event.model_to_label || lastMsg.debateModelToLabel;
              lastMsg.debateLabelToModel = event.label_to_model || lastMsg.debateLabelToModel;
              lastMsg.debateNumRounds = event.num_rounds || lastMsg.debateNumRounds;
              // Set stage3 result with debate info
              lastMsg.stage3 = {
                model: event.chairman || 'Chairman',
                response: event.judgment || '',
                debate_mode: true,
                num_rounds: event.num_rounds || 3,
              };
              return { ...prev, messages };
            });
            break;

          // =================================================================
          // Sub-Question Decomposition Events
          // =================================================================

          case 'decomposition_start':
            // Decomposition mode starting
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.isDecomposing = true;
              lastMsg.subQuestions = [];
              lastMsg.subResults = [];
              return { ...prev, messages };
            });
            break;

          case 'complexity_analyzed':
            // Complexity analysis complete
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.complexityInfo = {
                is_complex: event.is_complex,
                confidence: event.confidence,
                reasoning: event.reasoning,
              };
              return { ...prev, messages };
            });
            break;

          case 'decomposition_skip':
            // Question not complex enough, falling through to normal flow
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.isDecomposing = false;
              lastMsg.decompositionSkipped = true;
              return { ...prev, messages };
            });
            break;

          case 'sub_questions_generated':
            // Sub-questions have been generated
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.subQuestions = event.sub_questions || [];
              lastMsg.totalSubQuestions = event.count || event.sub_questions?.length || 0;
              return { ...prev, messages };
            });
            break;

          case 'sub_council_start':
            // Starting to process a sub-question
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.currentSubQuestion = event.index;
              return { ...prev, messages };
            });
            break;

          case 'sub_council_response':
            // A model has responded to the current sub-question
            // This is intermediate - we wait for sub_council_complete
            break;

          case 'sub_council_complete':
            // A sub-question has been fully answered
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              const newResult = {
                index: event.index,
                sub_question: event.sub_question,
                best_answer: event.best_answer,
                best_model: event.best_model,
              };
              lastMsg.subResults = [...(lastMsg.subResults || []), newResult];
              return { ...prev, messages };
            });
            break;

          case 'all_sub_councils_complete':
            // All sub-questions have been answered
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.subResults = event.results || lastMsg.subResults;
              return { ...prev, messages };
            });
            break;

          case 'merge_start':
            // Chairman starting to merge sub-answers
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.isMerging = true;
              lastMsg.mergeStreaming = '';
              lastMsg.chairmanModel = event.chairman_model;
              return { ...prev, messages };
            });
            break;

          case 'merge_token':
            // Accumulate merge tokens
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.mergeStreaming = (lastMsg.mergeStreaming || '') + event.content;
              return { ...prev, messages };
            });
            break;

          case 'merge_complete':
            // Merge finished
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.isMerging = false;
              lastMsg.mergeStreaming = '';
              // Store the final merged response
              if (event.response) {
                lastMsg.decompositionFinalResponse = event.response;
              }
              return { ...prev, messages };
            });
            break;

          case 'decomposition_complete':
            // Full decomposition complete
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.isDecomposing = false;
              lastMsg.isMerging = false;
              lastMsg.decompositionComplete = true;
              lastMsg.subQuestions = event.sub_questions || lastMsg.subQuestions;
              lastMsg.subResults = event.sub_results || lastMsg.subResults;
              lastMsg.decompositionFinalResponse = event.final_response;
              lastMsg.chairmanModel = event.chairman_model;
              // Set stage3 result with decomposition info
              lastMsg.stage3 = {
                model: event.chairman_model || 'Chairman',
                response: event.final_response || '',
                decomposition_mode: true,
                sub_question_count: event.sub_questions?.length || lastMsg.subQuestions?.length || 0,
              };
              return { ...prev, messages };
            });
            break;

          // =================================================================
          // Semantic Response Caching Events
          // =================================================================

          case 'cache_check_start':
            // Cache check starting
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.cacheChecking = true;
              return { ...prev, messages };
            });
            break;

          case 'cache_hit':
            // Cache hit - response found
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.cacheChecking = false;
              lastMsg.cacheHit = {
                similarity: event.similarity,
                cached_query: event.cached_query,
                cache_id: event.cache_id,
                created_at: event.created_at,
                hit_count: event.hit_count,
              };
              // Set stages from cached response
              if (event.cached_response) {
                lastMsg.stage1 = event.cached_response.stage1 || null;
                lastMsg.stage2 = event.cached_response.stage2 || null;
                lastMsg.stage3 = event.cached_response.stage3 || null;
                lastMsg.metadata = event.cached_response.metadata || null;
              }
              lastMsg.loading.stage1 = false;
              lastMsg.loading.stage2 = false;
              lastMsg.loading.stage3 = false;
              return { ...prev, messages };
            });
            break;

          case 'cache_miss':
            // Cache miss - will run full council
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.cacheChecking = false;
              lastMsg.cacheHit = null;
              return { ...prev, messages };
            });
            break;

          case 'cache_stored':
            // Response stored in cache
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.cacheStored = {
                cache_id: event.cache_id,
                embedding_method: event.embedding_method,
                cache_size: event.cache_size,
              };
              return { ...prev, messages };
            });
            break;

          case 'process':
            // Add process event to the list
            setProcessEvents((prev) => [...prev, event]);
            break;

          default:
            console.log('Unknown event type:', eventType);
        }

  };
}
