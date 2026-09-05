import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import DebateView from './DebateView';
import TagEditor from './TagEditor';
import CostDisplay from './CostDisplay';
import { exportToMarkdown, exportToJSON, exportToADR, copyADRToClipboard } from '../utils/export';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  activeCouncil,
  onSendMessage,
  onNewConversation,
  isLoading,
  onTagsChange,
}) {
  const [input, setInput] = useState('');
  const [showTagEditor, setShowTagEditor] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState('0.0');
  const [copiedADR, setCopiedADR] = useState(false);
  const messagesEndRef = useRef(null);

  const handleCopyADR = async () => {
    if (!conversation) return;
    const success = await copyADRToClipboard(conversation);
    if (success) {
      setCopiedADR(true);
      setTimeout(() => setCopiedADR(false), 2200);
    }
  };

  useEffect(() => {
    let interval = null;
    if (isLoading) {
      const startTime = Date.now();
      setElapsedSeconds('0.0');
      interval = setInterval(() => {
        setElapsedSeconds(((Date.now() - startTime) / 1000).toFixed(1));
      }, 100);
    } else {
      setElapsedSeconds('0.0');
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isLoading]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="empty-state">
          <div className="empty-council-badge">
            <span className="empty-council-icon">{activeCouncil?.icon || '🏛️'}</span>
            <span className="empty-council-name">{activeCouncil?.name || 'LLM Council'}</span>
          </div>
          <h2>Welcome to LLM Council</h2>
          <p>Create a new conversation to start deliberating with the council</p>
          {onNewConversation && (
            <button
              type="button"
              className="new-conversation-hero-btn"
              onClick={() => onNewConversation()}
            >
              + New Conversation
            </button>
          )}
        </div>
      </div>
    );
  }

  const hasMessages = conversation.messages.length > 0;

  return (
    <div className="chat-interface">
      {/* Header with title, tags, and export options */}
      {hasMessages && (
        <div className="chat-header">
          <div className="chat-header-left">
            <h2 className="chat-title">{conversation.title || 'Conversation'}</h2>
            {(conversation.council_name || activeCouncil?.name) && (
              <span className="chat-header-council-pill" title="Council assigned to this deliberation">
                {activeCouncil?.icon || '🏛️'} {conversation.council_name || activeCouncil?.name}
              </span>
            )}
            {conversation.tags && conversation.tags.length > 0 && !showTagEditor && (
              <div className="header-tags">
                {conversation.tags.map((tag) => (
                  <span key={tag} className="header-tag">#{tag}</span>
                ))}
              </div>
            )}
          </div>
          <div className="chat-header-actions">
            <button
              className={`action-btn ${showTagEditor ? 'active' : ''}`}
              onClick={() => setShowTagEditor(!showTagEditor)}
              title="Edit tags"
            >
              Tags
            </button>
            <button
              className={`action-btn action-btn-adr ${copiedADR ? 'copied' : ''}`}
              onClick={handleCopyADR}
              title="Copy decision as Architecture Decision Record (ADR) to clipboard"
            >
              {copiedADR ? '✓ ADR Kopyalandı' : '📋 Copy ADR'}
            </button>
            <button
              className="action-btn"
              onClick={() => exportToADR(conversation)}
              title="Download Architecture Decision Record (ADR) file"
            >
              ADR (.md)
            </button>
            <button
              className="action-btn"
              onClick={() => exportToMarkdown(conversation)}
              title="Export to full Markdown"
            >
              Export MD
            </button>
            <button
              className="action-btn"
              onClick={() => exportToJSON(conversation)}
              title="Export to JSON"
            >
              Export JSON
            </button>
          </div>
        </div>
      )}

      {/* Tag Editor */}
      {hasMessages && showTagEditor && (
        <div className="tag-editor-container">
          <TagEditor
            tags={conversation.tags || []}
            onTagsChange={onTagsChange}
          />
        </div>
      )}

      <div className="messages-container">
        {conversation.messages.length === 0 ? (
          <div className="empty-state">
            <div className="empty-council-badge">
              <span className="empty-council-icon">{activeCouncil?.icon || '🏛️'}</span>
              <span className="empty-council-name">{conversation.council_name || activeCouncil?.name || 'LLM Council'}</span>
            </div>
            <h2>Start a Deliberation</h2>
            <p className="empty-council-desc">
              {activeCouncil?.description || 'Ask a question to consult the expert council'}
            </p>
            {((activeCouncil?.council_models?.length ? activeCouncil.council_models : conversation?.council_models) || []).length > 0 && (
              <div className="empty-council-roster">
                <span className="empty-roster-label">PANEL SEATS</span>
                <div className="empty-roster-list">
                  {(activeCouncil?.council_models?.length ? activeCouncil.council_models : conversation?.council_models).map((m, idx) => {
                    const [modelName, skillId] = m.split('@');
                    return (
                      <span key={idx} className="empty-roster-seat">
                        <span className="empty-seat-model">{modelName}</span>
                        {skillId && <span className="empty-seat-skill">@{skillId}</span>}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        ) : (
          conversation.messages.map((msg, index) => (
            <div key={index} className="message-group">
              {msg.role === 'user' ? (
                <div className="user-message">
                  <div className="message-label">You</div>
                  <div className="message-content">
                    <div className="markdown-content">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="assistant-message">
                  <div className="message-label">
                    {msg.useDebate || msg.isDebating || msg.stage3?.debate_mode ? 'Council Debate' : 'LLM Council'}
                  </div>

                  {/* Automated Context Ingestion Banner */}
                  {(msg.metadata?.ingestion || msg.ingestMeta) && (
                    <div className="ingestion-badge-banner">
                      <span className="ingestion-badge-icon">⚡</span>
                      <span className="ingestion-badge-label">Context Enriched:</span>
                      {(msg.metadata?.ingestion?.target_workspace || msg.ingestMeta?.target_workspace) && (
                        <span className="ingestion-chip workspace" title="Target local workspace dossier injected">
                          📁 {msg.metadata?.ingestion?.target_workspace || msg.ingestMeta?.target_workspace}
                        </span>
                      )}
                      {(msg.metadata?.ingestion?.external_repos || msg.ingestMeta?.external_repos || []).map((repoUrl) => (
                        <a
                          key={repoUrl}
                          href={repoUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="ingestion-chip repo"
                          title="External repository metadata & README fetched"
                        >
                          🐙 {repoUrl.replace('https://github.com/', '')}
                        </a>
                      ))}
                    </div>
                  )}

                  {/* Debate Mode View */}
                  {(msg.useDebate || msg.isDebating || msg.stage3?.debate_mode || (msg.debatePositions && msg.debatePositions.length > 0)) ? (
                    <DebateView
                      positions={
                        (msg.debatePositions && msg.debatePositions.length > 0)
                          ? msg.debatePositions
                          : (msg.stage1?.map(p => ({
                              model: p.model,
                              position: p.response,
                              label: msg.stage3?.model_to_label?.[p.model] || p.label || p.model,
                            })) || [])
                      }
                      critiques={
                        (msg.debateCritiques && msg.debateCritiques.length > 0)
                          ? msg.debateCritiques
                          : (msg.stage2?.map(c => ({
                              critic: c.model,
                              critique: c.ranking,
                              critic_label: msg.stage3?.model_to_label?.[c.model] || c.model,
                              target: c.target,
                              target_label: c.target_label,
                            })) || [])
                      }
                      rebuttals={
                        (msg.debateRebuttals && msg.debateRebuttals.length > 0)
                          ? msg.debateRebuttals
                          : (msg.stage3?.rebuttals || [])
                      }
                      judgment={msg.debateJudgment || msg.stage3?.response || ''}
                      modelToLabel={msg.debateModelToLabel || msg.stage3?.model_to_label || {}}
                      labelToModel={msg.debateLabelToModel || msg.stage3?.label_to_model || {}}
                      numRounds={msg.debateNumRounds || msg.stage3?.num_rounds || 3}
                      isDebating={msg.isDebating || false}
                      currentRound={msg.debateRound || (msg.stage3?.response ? 4 : 1)}
                      judgmentStreaming={msg.debateJudgmentStreaming || ''}
                      isJudging={msg.isJudging || false}
                    />
                  ) : (
                    <>
                      {/* Stage 1 */}
                      {/* Routing Status */}
                      {msg.loading?.routing && (
                        <div className="stage-loading routing-loading">
                          <div className="spinner"></div>
                          <span>Classifying question for dynamic routing...</span>
                        </div>
                      )}

                      {/* Tier 1 Escalation Status */}
                      {msg.loading?.tier1 && !msg.stage1Streaming && (
                        <div className="stage-loading tier-loading">
                          <div className="spinner"></div>
                          <span>Tier 1: Querying cost-effective models...</span>
                        </div>
                      )}

                      {/* Escalation Triggered - Tier 2 Status */}
                      {msg.loading?.tier2 && (
                        <div className="stage-loading tier-loading escalation">
                          <div className="spinner"></div>
                          <span>Escalating to Tier 2: Querying premium models...</span>
                        </div>
                      )}

                      {/* Stage 1 */}
                      {msg.loading?.stage1 && !msg.stage1Streaming && !msg.loading?.tier1 && !msg.loading?.tier2 && (
                        <div className="stage-loading">
                          <div className="spinner"></div>
                          <span>Running Stage 1: Collecting individual responses...</span>
                        </div>
                      )}
                      {(msg.stage1 || msg.stage1Streaming) && (
                        <Stage1
                          responses={msg.stage1 || []}
                          aggregateConfidence={msg.metadata?.aggregate_confidence}
                          streamingResponses={msg.stage1Streaming}
                          streamingReasoning={msg.stage1ReasoningStreaming}
                          isStreaming={msg.loading?.stage1}
                          routingInfo={msg.routingInfo}
                          escalationInfo={msg.escalationInfo}
                        />
                      )}

                      {/* Stage 2 */}
                      {msg.loading?.stage2 && (
                        <div className="stage-loading">
                          <div className="spinner"></div>
                          <span>Running Stage 2: Peer rankings...</span>
                        </div>
                      )}
                      {msg.stage2 && (
                        <Stage2
                          rankings={msg.stage2}
                          labelToModel={msg.metadata?.label_to_model}
                          aggregateRankings={msg.metadata?.aggregate_rankings}
                          useWeightedConsensus={msg.metadata?.use_weighted_consensus}
                          weightsInfo={msg.metadata?.weights_info}
                        />
                      )}

                      {/* Stage 3 */}
                      {msg.loading?.stage3 && !msg.stage3Streaming && !msg.multiSyntheses?.length && !msg.isConsensus && !msg.isRefining && (
                        <div className="stage-loading">
                          <div className="spinner"></div>
                          <span>Running Stage 3: {msg.useMultiChairman ? 'Multi-chairman synthesis...' : 'Final synthesis...'}</span>
                        </div>
                      )}
                      {msg.loading?.refinement && !msg.isRefining && (
                        <div className="stage-loading refinement-loading">
                          <div className="spinner"></div>
                          <span>Starting iterative refinement...</span>
                        </div>
                      )}
                      {(msg.stage3 || msg.stage3Streaming || msg.multiSyntheses?.length > 0 || msg.isConsensus || msg.isRefining || msg.refinementIterations?.length > 0 || msg.isDecomposing || msg.decompositionComplete || msg.subQuestions?.length > 0) && (
                        <Stage3
                          finalResponse={msg.stage3}
                          streamingResponse={msg.stage3Streaming}
                          streamingModel={msg.stage3StreamingModel}
                          isStreaming={msg.loading?.stage3 && !msg.useMultiChairman}
                          useMultiChairman={msg.useMultiChairman}
                          multiSyntheses={msg.multiSyntheses}
                          selectionStreaming={msg.selectionStreaming}
                          isSelecting={msg.isSelecting}
                          isConsensus={msg.isConsensus}
                          consensusInfo={msg.consensusInfo}
                          useRefinement={msg.useRefinement}
                          refinementIterations={msg.refinementIterations}
                          isRefining={msg.isRefining}
                          currentRefinementIteration={msg.currentRefinementIteration}
                          refinementCritiques={msg.refinementCritiques}
                          refinementStreaming={msg.refinementStreaming}
                          refinementMaxIterations={msg.refinementMaxIterations}
                          refinementConverged={msg.refinementConverged}
                          useDecomposition={msg.useDecomposition}
                          subQuestions={msg.subQuestions}
                          subResults={msg.subResults}
                          isDecomposing={msg.isDecomposing}
                          currentSubQuestion={msg.currentSubQuestion}
                          totalSubQuestions={msg.totalSubQuestions}
                          mergeStreaming={msg.mergeStreaming}
                          isMerging={msg.isMerging}
                          decompositionFinalResponse={msg.decompositionFinalResponse}
                          chairmanModel={msg.chairmanModel}
                          complexityInfo={msg.complexityInfo}
                          decompositionSkipped={msg.decompositionSkipped}
                          decompositionComplete={msg.decompositionComplete}
                        />
                      )}
                    </>
                  )}

                  {/* Cost Display */}
                  {msg.metadata?.costs && (
                    <CostDisplay costs={msg.metadata.costs} expanded={true} />
                  )}
                </div>
              )}
            </div>
          ))
        )}

        {/* Interrupted or pending deliberation after page reload */}
        {!isLoading &&
          conversation.messages.length > 0 &&
          conversation.messages[conversation.messages.length - 1]?.role === 'user' && (
            <div className="pending-deliberation-wrap">
              <div className="pending-deliberation-card">
                <div className="pending-card-header">
                  <span className="pending-card-icon">⏳</span>
                  <span className="pending-card-title">Müzakere Bekliyor / Sayfa Yenilendi</span>
                </div>
                <p className="pending-card-desc">
                  Bu soru gönderilmiş fakat müzakere süreci henüz tamamlanmamış.
                  Aşağıdaki butona basarak konseyi hemen çalıştırabilirsiniz.
                </p>
                <button
                  className="pending-retry-btn"
                  onClick={() =>
                    onSendMessage(
                      conversation.messages[conversation.messages.length - 1].content,
                      true
                    )
                  }
                >
                  <svg
                    width="13"
                    height="13"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="1 4 1 10 7 10"></polyline>
                    <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path>
                  </svg>
                  <span>Konseyi Çalıştır / Yanıt Al</span>
                </button>
              </div>
            </div>
          )}

        {isLoading && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>
              {(() => {
                const lastMsg = conversation.messages[conversation.messages.length - 1];
                if (lastMsg && (lastMsg.isDebating || lastMsg.useDebate || lastMsg.stage3?.debate_mode)) {
                  if (lastMsg.isJudging) return `Hakem / Başkan değerlendiriyor... (${elapsedSeconds}s)`;
                  if (lastMsg.debateRound === 1) return `1. Tur: Pozisyonlar toplanıyor... (${elapsedSeconds}s)`;
                  if (lastMsg.debateRound === 2) return `2. Tur: Eleştiriler yazılıyor... (${elapsedSeconds}s)`;
                  if (lastMsg.debateRound === 3) return `3. Tur: Savunmalar toplanıyor... (${elapsedSeconds}s)`;
                  return `Münazara oturumu sürüyor... (${elapsedSeconds}s)`;
                }
                return `Consulting the council... (${elapsedSeconds}s)`;
              })()}
            </span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {(!hasMessages ||
        conversation.messages[conversation.messages.length - 1]?.role ===
          'assistant') && (
        <form className="input-form" onSubmit={handleSubmit}>
          <textarea
            className="message-input"
            placeholder="Ask your question... (Shift+Enter for new line, Enter to send)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            rows={3}
          />
          <button
            type="submit"
            className="send-button"
            disabled={!input.trim() || isLoading}
          >
            Send
          </button>
        </form>
      )}
    </div>
  );
}
