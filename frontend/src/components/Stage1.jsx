import { useState, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import { ConfidenceBadge, AggregateConfidenceSummary } from './ConfidenceDisplay';
import ReasoningView, { CoTBadge } from './ReasoningView';
import { TierBadge, TierSummary, EscalationBanner } from './TierIndicator';
import './Stage1.css';

// Category colors for routing badges
const CATEGORY_COLORS = {
  coding: '#22c55e',    // Green
  creative: '#a855f7',  // Purple
  factual: '#3b82f6',   // Blue
  analysis: '#f59e0b',  // Amber
  general: '#6b7280',   // Gray
};

/**
 * Stage1 - Displays individual model responses with optional reasoning details and confidence.
 *
 * Supports real-time token streaming: as models generate responses, tokens are
 * displayed incrementally. When a model completes, its full response replaces
 * the streaming content.
 *
 * Reasoning models (like OpenAI o1, o3) return a separate "reasoning_details"
 * field containing their chain-of-thought process. This component displays
 * that reasoning in a collapsible section above the final response.
 *
 * Each model also reports a confidence score (1-10) indicating how confident
 * they are in their response. Aggregate confidence is displayed in the header.
 *
 * @param {Object} props
 * @param {Array} props.responses - Array of completed response objects from Stage 1
 *   Each response has: { model, response, confidence?, reasoning_details?, tier? }
 * @param {Object} props.aggregateConfidence - Aggregate confidence statistics
 *   Contains: average, min, max, count, total_models, distribution
 * @param {Object} props.streamingResponses - Map of model -> partial response text (during streaming)
 * @param {Object} props.streamingReasoning - Map of model -> partial reasoning text (during streaming)
 * @param {boolean} props.isStreaming - Whether Stage 1 is currently streaming
 * @param {Object} props.routingInfo - Dynamic routing information (optional)
 *   Contains: category, confidence, reasoning, models, is_routed
 * @param {Object} props.escalationInfo - Escalation information (optional)
 *   Contains: escalated, tier1_model_count, tier2_model_count, total_model_count, reasons, metrics
 */
// Helper to parse model string like "local/qwen3.6-27b@owasp-security"
const parseModelSkill = (modelStr) => {
  if (!modelStr) return { baseModel: '', shortName: '', skillId: '', skillLabel: '' };
  const [baseModel, skillId = ''] = modelStr.split('@');
  const shortName = baseModel.split('/')[1] || baseModel;

  let skillLabel = '';
  if (skillId) {
    if (skillId.includes('security')) skillLabel = 'Security';
    else if (skillId.includes('karpathy') || skillId.includes('architect')) skillLabel = 'Architect';
    else if (skillId.includes('devops')) skillLabel = 'DevOps';
    else if (skillId.includes('testing') || skillId.includes('qa')) skillLabel = 'Quality';
    else if (skillId.includes('review')) skillLabel = 'Reviewer';
    else {
      const clean = skillId.replace(/-(guidelines|handbook|audit|security)/g, '');
      skillLabel = clean.charAt(0).toUpperCase() + clean.slice(1);
    }
  }
  return { baseModel, shortName, skillId, skillLabel };
};

export default function Stage1({
  responses,
  aggregateConfidence,
  streamingResponses,
  streamingReasoning,
  isStreaming,
  routingInfo,
  escalationInfo,
}) {
  const [activeTab, setActiveTab] = useState(0);
  const [showReasoning, setShowReasoning] = useState({});

  // Merge completed responses with streaming responses
  const allResponses = useMemo(() => {
    const completed = responses || [];
    const streaming = streamingResponses || {};

    // Get all models that are streaming but not yet complete
    const streamingModels = Object.keys(streaming).filter(
      (model) => !completed.some((r) => r.model === model)
    );

    // Create placeholder responses for streaming models
    const streamingPlaceholders = streamingModels.map((model) => ({
      model,
      response: streaming[model] || '',
      confidence: null,
      reasoning_details: streamingReasoning?.[model] || null,
      isStreaming: true,
    }));

    // Combine completed and streaming responses
    return [...completed, ...streamingPlaceholders];
  }, [responses, streamingResponses, streamingReasoning]);

  // Auto-select first streaming model if no responses yet
  useEffect(() => {
    if (allResponses.length > 0 && activeTab >= allResponses.length) {
      setActiveTab(0);
    }
  }, [allResponses.length, activeTab]);

  if (allResponses.length === 0) {
    return null;
  }

  // Toggle reasoning visibility for a specific model index
  const toggleReasoning = (index) => {
    setShowReasoning((prev) => ({
      ...prev,
      [index]: !prev[index],
    }));
  };

  // Check if current response has reasoning details or CoT
  const currentResponse = allResponses[activeTab];
  const hasReasoning = currentResponse?.reasoning_details != null;
  const hasCot = currentResponse?.cot != null;
  const isCurrentStreaming = currentResponse?.isStreaming;

  // Format reasoning details for display
  // reasoning_details can be a string or an object with content
  const formatReasoning = (reasoning) => {
    if (!reasoning) return '';
    if (typeof reasoning === 'string') return reasoning;
    if (typeof reasoning === 'object') {
      // OpenRouter may return { type: 'thinking', content: '...' } or similar
      if (reasoning.content) return reasoning.content;
      // Or it might be an array of thinking steps
      if (Array.isArray(reasoning)) {
        return reasoning
          .map((item) => (typeof item === 'string' ? item : item.content || JSON.stringify(item)))
          .join('\n\n');
      }
      return JSON.stringify(reasoning, null, 2);
    }
    return String(reasoning);
  };

  return (
    <div className="stage stage1">
      <div className="stage-header">
        <h3 className="stage-title">Stage 1: Individual Responses</h3>
        {routingInfo && routingInfo.is_routed && (
          <span
            className="routing-badge"
            style={{ background: CATEGORY_COLORS[routingInfo.category] || CATEGORY_COLORS.general }}
            title={`Routed to ${routingInfo.category} pool (${routingInfo.routed_model_count} models, ${Math.round(routingInfo.confidence * 100)}% conf): ${routingInfo.reasoning}`}
          >
            {routingInfo.category.charAt(0).toUpperCase() + routingInfo.category.slice(1)} Pool
          </span>
        )}
        {escalationInfo && <TierSummary escalationInfo={escalationInfo} />}
        {isStreaming && <span className="streaming-indicator">Streaming...</span>}
        <AggregateConfidenceSummary aggregateConfidence={aggregateConfidence} />
      </div>

      {/* Escalation Banner (if escalation was triggered) */}
      {escalationInfo && escalationInfo.escalated && (
        <EscalationBanner escalationInfo={escalationInfo} />
      )}

      <div className="tabs">
        {allResponses.map((resp, index) => {
          const { shortName, skillId, skillLabel } = parseModelSkill(resp.model);
          return (
            <button
              key={resp.model}
              className={`tab ${activeTab === index ? 'active' : ''} ${resp.reasoning_details ? 'has-reasoning' : ''} ${resp.cot ? 'has-cot' : ''} ${resp.isStreaming ? 'streaming' : ''}`}
              onClick={() => setActiveTab(index)}
              title={
                resp.isStreaming
                  ? 'Model is still generating...'
                  : resp.cot
                  ? 'Chain-of-Thought reasoning'
                  : resp.reasoning_details
                  ? 'This model provided reasoning details'
                  : skillId
                  ? `Specialist: ${skillId}`
                  : ''
              }
            >
              <span className="tab-model-name">{shortName}</span>
              {skillId && (
                <span className="tab-skill-pill" title={`Specialization: ${skillId}`}>
                  {skillLabel}
                </span>
              )}
              {resp.tier && <TierBadge tier={resp.tier} />}
              {resp.isStreaming && <span className="streaming-dot"></span>}
              {resp.cot && !resp.isStreaming && <CoTBadge />}
              {resp.reasoning_details && !resp.cot && !resp.isStreaming && (
                <span className="reasoning-indicator">*</span>
              )}
              {!resp.isStreaming && <ConfidenceBadge confidence={resp.confidence} />}
            </button>
          );
        })}
      </div>

      <div className="tab-content">
        <div className="model-name">
          {(() => {
            const { baseModel, skillId, skillLabel } = parseModelSkill(currentResponse.model);
            return (
              <>
                <span className="model-base-title">{baseModel}</span>
                {skillId && (
                  <span className="model-specialist-badge" title={`Domain Skill: ${skillId}`}>
                    <span className="specialist-tag">SPECIALIST</span>
                    <span className="specialist-name">{skillLabel} ({skillId})</span>
                  </span>
                )}
              </>
            );
          })()}
          {isCurrentStreaming && (
            <span className="streaming-badge">Generating...</span>
          )}
          {hasCot && !isCurrentStreaming && (
            <span className="cot-model-badge">Chain-of-Thought</span>
          )}
          {hasReasoning && !hasCot && !isCurrentStreaming && (
            <span className="reasoning-model-badge">Reasoning Model</span>
          )}
        </div>

        {/* Chain-of-Thought Section (structured view) */}
        {hasCot && !isCurrentStreaming && (
          <ReasoningView cot={currentResponse.cot} showAll={false} />
        )}

        {/* Reasoning Details Section (for native reasoning models like o1) */}
        {hasReasoning && !hasCot && (
          <div className="reasoning-section">
            <button
              className={`reasoning-toggle ${showReasoning[activeTab] ? 'expanded' : ''}`}
              onClick={() => toggleReasoning(activeTab)}
            >
              <span className="reasoning-toggle-icon">
                {showReasoning[activeTab] ? '▼' : '▶'}
              </span>
              <span className="reasoning-toggle-text">
                {showReasoning[activeTab] ? 'Hide' : 'Show'} Thinking Process
              </span>
            </button>

            {showReasoning[activeTab] && (
              <div className="reasoning-content">
                <div className="reasoning-header">
                  Chain of Thought
                </div>
                <div className="reasoning-text markdown-content">
                  <ReactMarkdown>
                    {formatReasoning(currentResponse.reasoning_details)}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Final Response - only show separately if not using CoT */}
        {!hasCot && (
          <div className="response-section">
            {hasReasoning && !isCurrentStreaming && (
              <div className="response-label">Final Response</div>
            )}
            <div className={`response-text markdown-content ${isCurrentStreaming ? 'streaming' : ''}`}>
              <ReactMarkdown>{currentResponse.response}</ReactMarkdown>
              {isCurrentStreaming && <span className="streaming-cursor"></span>}
            </div>
          </div>
        )}

        {/* Streaming response while generating with CoT enabled */}
        {hasCot && isCurrentStreaming && (
          <div className="response-section">
            <div className={`response-text markdown-content streaming`}>
              <ReactMarkdown>{currentResponse.response}</ReactMarkdown>
              <span className="streaming-cursor"></span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
