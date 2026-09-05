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
  isDeliberating,
  onAbortDeliberation,
  onTagsChange,
}) {
  const [input, setInput] = useState('');
  const [showTagEditor, setShowTagEditor] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState('0.0');
  const [copiedADR, setCopiedADR] = useState(false);
  const [expandedResearch, setExpandedResearch] = useState({});
  const messagesEndRef = useRef(null);

  const activeDeliberating = Boolean(isLoading || isDeliberating || conversation?.status === 'deliberating');

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
    if (activeDeliberating) {
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
  }, [activeDeliberating]);

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
                {conversation.council_name || activeCouncil?.name}
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
              {copiedADR ? 'ADR Copied' : 'Copy ADR'}
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

                  {/* Autonomous Technology Scouting & Candidate Discovery Showcase */}
                  {(msg.metadata?.research?.researched || msg.researchMeta?.researched) && (
                    (() => {
                      const rMeta = msg.metadata?.research || msg.researchMeta;
                      const isExpanded = expandedResearch[index] !== false; // expanded by default
                      const candidates = rMeta?.candidates || [];
                      return (
                        <div className="research-discovery-container">
                          <div
                            className="research-badge-banner"
                            onClick={() => setExpandedResearch(prev => ({ ...prev, [index]: isExpanded ? false : true }))}
                            title="Click to toggle scouted technology candidates dossier"
                          >
                            <div className="research-banner-left">
                              <span className="research-badge-icon">🔬</span>
                              <span className="research-badge-label">Research Scouting:</span>
                              {rMeta.search_terms && (
                                <span className="research-terms-chip">
                                  "{rMeta.search_terms}"
                                </span>
                              )}
                              <span className="research-count-badge">
                                {rMeta.candidate_count || candidates.length} candidates scouted
                              </span>
                            </div>
                            <span className="research-accordion-toggle">
                              {isExpanded ? '▲ Hide Dossier' : '▼ View Candidates'}
                            </span>
                          </div>

                          {isExpanded && candidates.length > 0 && (
                            <div className="research-candidates-grid">
                              {candidates.map((c, cIdx) => (
                                <div key={cIdx} className={`candidate-card source-${c.source || 'web'}`}>
                                  <div className="candidate-card-header">
                                    <span className={`candidate-source-tag source-tag-${c.source || 'web'}`}>
                                      {c.source === 'github' && '🐙 GitHub'}
                                      {c.source === 'local-skill' && '🧩 Skill'}
                                      {c.source === 'package' && '📦 Package'}
                                      {c.source === 'web' && '📰 Tech Article'}
                                    </span>
                                    {c.url && !c.url.startsWith('local://') ? (
                                      <a
                                        href={c.url}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="candidate-title-link"
                                      >
                                        {c.title} ↗
                                      </a>
                                    ) : (
                                      <span className="candidate-title-text">{c.title}</span>
                                    )}
                                  </div>

                                  {c.description && <p className="candidate-desc">{c.description}</p>}

                                  <div className="candidate-meta-bar">
                                    {c.stars !== undefined && (
                                      <span className="candidate-stat stars" title="GitHub Stars">
                                        {c.stars} stars
                                      </span>
                                    )}
                                    {c.forks !== undefined && (
                                      <span className="candidate-stat forks" title="Forks">
                                        {c.forks} forks
                                      </span>
                                    )}
                                    {c.license && (
                                      <span className="candidate-stat license" title="License">
                                        {c.license}
                                      </span>
                                    )}
                                    {c.version && (
                                      <span className="candidate-stat version" title="Package Version">
                                        v{c.version}
                                      </span>
                                    )}
                                    {c.topics && c.topics.length > 0 && (
                                      <span className="candidate-topics">
                                        {c.topics.slice(0, 3).map(t => `#${t}`).join(' ')}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })()
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

        {/* Aborted deliberation status banner */}
        {conversation.status === 'aborted' &&
          conversation.messages.length > 0 &&
          conversation.messages[conversation.messages.length - 1]?.role === 'user' && (
            <div className="deliberation-aborted-banner">
              <div className="deliberation-aborted-content">
                <div className="deliberation-aborted-title">Deliberation Cancelled</div>
                <div className="deliberation-aborted-desc">
                  This deliberation was stopped. You can restart it at any time.
                </div>
              </div>
              <button
                type="button"
                className="deliberation-restart-btn"
                onClick={() =>
                  onSendMessage(
                    conversation.messages[conversation.messages.length - 1].content,
                    true
                  )
                }
              >
                <span>Restart</span>
              </button>
            </div>
          )}

        {/* Interrupted or pending deliberation after page reload */}
        {!activeDeliberating &&
          conversation.status !== 'aborted' &&
          conversation.messages.length > 0 &&
          conversation.messages[conversation.messages.length - 1]?.role === 'user' && (
            <div className="pending-deliberation-wrap">
              <div className="pending-deliberation-card">
                <div className="pending-card-header">
                  <span className="pending-card-title">Deliberation Interrupted</span>
                </div>
                <p className="pending-card-desc">
                  This query was submitted, but deliberation was interrupted before completion.
                  Click below to run the council.
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
                  <span>Run Council</span>
                </button>
              </div>
            </div>
          )}

        {/* Active Deliberation Banner with Live Status & Abort Control */}
        {activeDeliberating && (
          <div className="deliberation-active-banner">
            <div className="deliberation-active-info">
              <div className="deliberation-spinner"></div>
              <div className="deliberation-active-text">
                <span className="deliberation-active-title">
                  {(() => {
                    const lastMsg = conversation.messages[conversation.messages.length - 1];
                    if (lastMsg && (lastMsg.isDebating || lastMsg.useDebate || lastMsg.stage3?.debate_mode)) {
                      if (lastMsg.isJudging) return 'Referee / Chairman evaluating...';
                      if (lastMsg.debateRound === 1) return 'Round 1: Collecting initial positions...';
                      if (lastMsg.debateRound === 2) return 'Round 2: Peer critiques in progress...';
                      if (lastMsg.debateRound === 3) return 'Round 3: Rebuttals in progress...';
                      return 'Debate session in progress...';
                    }
                    if (conversation.council_id === 'tech-scout') {
                      return 'Tech Scout & Candidate Radar exploring...';
                    }
                    return 'Council deliberating...';
                  })()}
                </span>
                <span className="deliberation-active-sub">
                  Active task ({elapsedSeconds}s) • Persists across page reload
                </span>
              </div>
            </div>
            {onAbortDeliberation && (
              <button
                type="button"
                className="deliberation-abort-btn"
                onClick={() => onAbortDeliberation(conversation.id)}
                title="Stop the running deliberation"
              >
                <span>Stop</span>
              </button>
            )}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {(!hasMessages ||
        conversation.messages[conversation.messages.length - 1]?.role === 'assistant' ||
        activeDeliberating ||
        conversation.status === 'aborted') && (
        <form className="input-form" onSubmit={handleSubmit}>
          <textarea
            className="message-input"
            placeholder={
              activeDeliberating
                ? 'Council deliberation in progress... (Click Stop to cancel)'
                : 'Ask your question... (Shift+Enter for new line, Enter to send)'
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={activeDeliberating}
            rows={3}
          />
          {activeDeliberating ? (
            <button
              type="button"
              className="abort-button"
              onClick={() => onAbortDeliberation && onAbortDeliberation(conversation.id)}
              title="Stop deliberation"
            >
              <span>Stop</span>
            </button>
          ) : (
            <button
              type="submit"
              className="send-button"
              disabled={!input.trim() || activeDeliberating}
            >
              Send
            </button>
          )}
        </form>
      )}
    </div>
  );
}
