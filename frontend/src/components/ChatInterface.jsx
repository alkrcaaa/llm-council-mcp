import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import LiveFeed from './LiveFeed';
import DebateView from './DebateView';
import TagEditor from './TagEditor';
import CostDisplay from './CostDisplay';
import RoundTableMessage from './RoundTableMessage';
import { shortModelName, linkifyUserMentions, mentionMarkdownComponents } from './mentionUtils.jsx';
import { formatSeatLabel } from '../modelLabel.js';
import { exportToMarkdown, exportToJSON, exportToADR, copyADRToClipboard } from '../utils/export';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  activeCouncil,
  activeChatRoster,
  currentUser,
  onSendMessage,
  onNewConversation,
  isLoading,
  isDeliberating,
  onAbortDeliberation,
  onTagsChange,
  onInspectSkill,
  providerLabels = {},
}) {
  const [input, setInput] = useState('');
  const [landingInput, setLandingInput] = useState('');
  const [showTagEditor, setShowTagEditor] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState('0.0');
  const [copiedADR, setCopiedADR] = useState(false);
  const [expandedResearch, setExpandedResearch] = useState({});
  const [feedView, setFeedView] = useState(
    () => localStorage.getItem('feedView') !== 'false'
  );
  const [activeMode, setActiveMode] = useState(
    () => conversation?.conversation_type || 'roundtable'
  );
  const [mentionQuery, setMentionQuery] = useState(null);
  const [mentionIndex, setMentionIndex] = useState(0);
  const [queued, setQueued] = useState(null);
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const prevMessageCountRef = useRef(0);
  const tagEditorRef = useRef(null);
  const tagButtonRef = useRef(null);
  const messageInputRef = useRef(null);

  const isRoundTableConv = conversation?.conversation_type === 'roundtable';
  // A queue belongs to the conversation it was typed in; switching away hides it.
  const queuedMessage = queued && queued.conversationId === conversation?.id ? queued.text : null;
  const activeDeliberating = Boolean(isLoading || isDeliberating || conversation?.status === 'deliberating');

  const handleReplyToModel = (modelId) => {
    const shortName = modelId === 'all' ? 'all' : shortModelName(modelId);
    const tag = `@${shortName} `;
    setInput((prev) => {
      if (prev.includes(tag)) return prev;
      return `${tag}${prev}`;
    });
    messageInputRef.current?.focus();
  };

  const toggleFeedView = () => {
    setFeedView((prev) => {
      const next = !prev;
      localStorage.setItem('feedView', next.toString());
      return next;
    });
  };

  // @mention autocomplete: seats of the council this conversation will use + @all
  const isRoundTable = conversation
    ? conversation.conversation_type === 'roundtable'
    : activeMode === 'roundtable';

  const mentionSeats = isRoundTable
    ? (conversation?.council_models?.length
        ? conversation.council_models
        : (activeChatRoster?.models?.length ? activeChatRoster.models : []))
    : ((activeCouncil?.council_models?.length ? activeCouncil.council_models : conversation?.council_models) || []);

  // Models actually answering in this conversation, shown in the header.
  const activeSeats = isRoundTable
    ? (conversation?.council_models?.length
        ? conversation.council_models
        : (activeChatRoster?.models || []))
    : ((conversation?.council_models?.length
        ? conversation.council_models
        : activeCouncil?.council_models) || []);

  const chairmanSeat = isRoundTable
    ? null
    : (conversation?.chairman_model || activeCouncil?.chairman_model || null);

  const modelMatchesQuery = (model, query) => {
    if (!query) return true;
    const q = query.toLowerCase();
    const short = shortModelName(model).toLowerCase();
    if (short.startsWith(q)) return true;
    if (short.includes('antigravity') && ('antigravity'.startsWith(q) || 'agy'.startsWith(q))) return true;
    if (short.includes('claude') && 'claude'.startsWith(q)) return true;
    return false;
  };

  const mentionMatches = mentionQuery == null
    ? []
    : [
        ...(mentionQuery === '' || 'all'.startsWith(mentionQuery.toLowerCase()) ? ['all'] : []),
        ...mentionSeats.filter((m) => modelMatchesQuery(m, mentionQuery))
      ].slice(0, 6);

  const handleInputChange = (e) => {
    const val = e.target.value;
    setInput(val);
    const cursorPos = e.target.selectionStart;
    const uptoCursor = val.slice(0, cursorPos);
    const match = uptoCursor.match(/(?:^|\s)@(\w*)$/);
    setMentionQuery(match ? match[1] : null);
    if (match) {
      setMentionIndex(0);
    }
  };

  const insertMention = (model) => {
    const el = messageInputRef.current;
    if (!el) return;
    const cursorPos = el.selectionStart;
    const uptoCursor = input.slice(0, cursorPos);
    const match = uptoCursor.match(/(?:^|\s)@(\w*)$/);
    if (!match) return;
    const startIdx = cursorPos - match[0].length + (match[0].startsWith(' ') ? 1 : 0);
    const name = model === 'all' ? 'all' : shortModelName(model);
    const newVal = `${input.slice(0, startIdx)}@${name} ${input.slice(cursorPos)}`;
    setInput(newVal);
    setMentionQuery(null);
    setMentionIndex(0);
    requestAnimationFrame(() => el.focus());
  };

  // Close Tag Editor on click outside or Escape key
  useEffect(() => {
    if (!showTagEditor) return;

    const handleClickOutside = (e) => {
      if (
        tagEditorRef.current &&
        !tagEditorRef.current.contains(e.target) &&
        tagButtonRef.current &&
        !tagButtonRef.current.contains(e.target)
      ) {
        setShowTagEditor(false);
      }
    };

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setShowTagEditor(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [showTagEditor]);

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
      // Anchor deliberation start time to the latest user message timestamp if available (preserves elapsed time across page refresh)
      const userMsgs = (conversation?.messages || []).filter((m) => m.role === 'user');
      const lastUserMsg = userMsgs[userMsgs.length - 1];
      const parsedTime = lastUserMsg?.created_at ? Date.parse(lastUserMsg.created_at) : NaN;
      const startTime = !isNaN(parsedTime) && parsedTime <= Date.now() ? parsedTime : Date.now();

      setElapsedSeconds(((Date.now() - startTime) / 1000).toFixed(1));
      interval = setInterval(() => {
        setElapsedSeconds(((Date.now() - startTime) / 1000).toFixed(1));
      }, 100);
    } else {
      setElapsedSeconds('0.0');
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [activeDeliberating, conversation?.messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const isNearBottom = () => {
    const el = messagesContainerRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 150;
  };

  // Auto-scroll only when a new message is appended (e.g. the user just sent
  // one) or the viewport was already near the bottom — otherwise streaming
  // token updates keep re-triggering this on every render and yank the user
  // back down while they're scrolled up reading earlier messages.
  useEffect(() => {
    const count = conversation?.messages?.length || 0;
    const isNewMessage = count > prevMessageCountRef.current;
    prevMessageCountRef.current = count;
    if (isNewMessage || isNearBottom()) {
      scrollToBottom();
    }
  }, [conversation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    if (!isLoading) {
      onSendMessage(input);
      setInput('');
    } else if (isRoundTableConv) {
      // The backend accepts one stream per conversation; hold the message until
      // the current replies finish instead of swallowing the Enter key.
      const text = queuedMessage ? `${queuedMessage}\n\n${input.trim()}` : input.trim();
      setQueued({ conversationId: conversation?.id, text });
      setInput('');
    }
  };

  useEffect(() => {
    if (!isLoading && queuedMessage) {
      onSendMessage(queuedMessage);
      // Reacting to the isLoading prop falling back to false is the point of this effect.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setQueued(null);
    }
  }, [isLoading, queuedMessage, onSendMessage]);

  const handleKeyDown = (e) => {
    if (mentionQuery != null && mentionMatches.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMentionIndex((prev) => (prev + 1) % mentionMatches.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMentionIndex((prev) => (prev - 1 + mentionMatches.length) % mentionMatches.length);
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        const selected = mentionMatches[mentionIndex] || mentionMatches[0];
        insertMention(selected);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setMentionQuery(null);
        return;
      }
    }
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleLandingSubmit = (e) => {
    e.preventDefault();
    if (!landingInput.trim()) return;
    if (conversation && conversation.id) {
      onSendMessage(landingInput);
    } else if (onNewConversation) {
      onNewConversation(null, landingInput, activeMode);
    }
    setLandingInput('');
  };

  const handleLandingKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleLandingSubmit(e);
    }
  };

  const hasMessages = Boolean(conversation && conversation.messages && conversation.messages.length > 0);

  if (!hasMessages) {
    const displayName = currentUser ? currentUser.charAt(0).toUpperCase() + currentUser.slice(1) : '';
    const isRoundTable = activeMode === 'roundtable';
    const rosterModels = isRoundTable
      ? (activeChatRoster?.models?.length ? activeChatRoster.models : conversation?.council_models || [])
      : ((activeCouncil?.council_models?.length ? activeCouncil.council_models : conversation?.council_models) || []);
    const chairman = isRoundTable ? null : (activeCouncil?.chairman_model || conversation?.chairman_model);
    const hasLocal = rosterModels.some((m) => m.startsWith('local/'));

    return (
      <div className="chat-interface">
        <div className="landing-state">
          <div className="landing-glow" />

          {/* Mode Selector Pill: Round Table (Group Chat) vs Formal Council Deliberation */}
          <div className="landing-mode-selector">
            <button
              type="button"
              className={`landing-mode-btn ${activeMode === 'roundtable' ? 'active' : ''}`}
              onClick={() => setActiveMode('roundtable')}
            >
              Round Table (Group Chat)
            </button>
            <button
              type="button"
              className={`landing-mode-btn ${activeMode === 'deliberation' ? 'active' : ''}`}
              onClick={() => setActiveMode('deliberation')}
            >
              Deliberation (3-Stage ADR)
            </button>
          </div>

          <h1 className="landing-greeting">
            {activeMode === 'roundtable'
              ? (displayName ? `Hello ${displayName}, welcome to the table.` : 'Welcome to the round table.')
              : (displayName ? `Hello ${displayName}, what's on your mind?` : "What's on your mind?")}
          </h1>
          <p className="landing-subtext">
            {activeMode === 'roundtable'
              ? 'Direct multi-agent conversation with unconstrained turn-taking. Mention @all to broadcast or @model to target.'
              : 'Council models propose independent solutions, peer-review each other, and synthesize a final ADR verdict.'}
          </p>

          <form className="landing-composer" onSubmit={handleLandingSubmit}>
            <button
              type="button"
              className="landing-composer-council"
              title={isRoundTable ? `Active table: ${activeChatRoster?.name || 'Round Table'}` : `Active council: ${conversation?.council_name || activeCouncil?.name || 'Default'}`}
            >
              {isRoundTable ? (activeChatRoster?.name || 'Round Table') : (conversation?.council_name || activeCouncil?.name || 'LLM Council')}
            </button>
            <textarea
              className="landing-composer-input"
              placeholder={activeMode === 'roundtable' ? 'Write a message or mention a model (@all, @qwen)...' : "Ask the council..."}
              value={landingInput}
              onChange={(e) => setLandingInput(e.target.value)}
              onKeyDown={handleLandingKeyDown}
              rows={1}
              autoFocus
            />
            <button
              type="submit"
              className="landing-composer-send"
              disabled={!landingInput.trim()}
              title="Start deliberation"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="19" x2="12" y2="5"></line>
                <polyline points="6 11 12 5 18 11"></polyline>
              </svg>
            </button>
          </form>

          {rosterModels.length > 0 && (
            <div className="landing-roster">
              <div className="landing-roster-group">
                <span className="landing-roster-label">
                  {isRoundTable ? 'ROUND TABLE SEATS' : 'PANEL SEATS'}
                </span>
                <div className="landing-roster-chips">
                  {rosterModels.map((m, idx) => {
                    const [modelName, skillId] = m.split('@');
                    const isLocal = modelName.startsWith('local/');
                    const isFree = modelName.includes(':free');
                    return (
                      <span key={idx} className="landing-roster-chip">
                        <span className="landing-chip-name">{shortModelName(modelName)}</span>
                        {isLocal && (
                          <span className="roundtable-tier-badge local" style={{ fontSize: '10px', padding: '1px 5px', marginLeft: '4px' }} title="Runs locally via vLLM/Ollama">
                            Local
                          </span>
                        )}
                        {isFree && !isLocal && (
                          <span className="roundtable-tier-badge free" style={{ fontSize: '10px', padding: '1px 5px', marginLeft: '4px' }} title="Zero cost free tier">
                            Free
                          </span>
                        )}
                        {skillId && (
                          <button
                            type="button"
                            className="landing-chip-skill clickable"
                            onClick={() => onInspectSkill?.(skillId)}
                            title={`Inspect "${skillId}" guidelines & rules`}
                          >
                            @{skillId}
                          </button>
                        )}
                      </span>
                    );
                  })}
                </div>
              </div>
              {chairman && (
                <div className="landing-roster-group">
                  <span className="landing-roster-label chairman">CHAIRMAN</span>
                  <div className="landing-roster-chips">
                    <span className="landing-roster-chip chairman">
                      <span className="landing-chip-name">{shortModelName(chairman)}</span>
                    </span>
                  </div>
                </div>
              )}
              {hasLocal && (
                <div className="local-models-guidance-tip landing-tip">
                  <span>
                    {isRoundTable
                      ? 'Local engineering models (Antigravity, Claude, Qwen) run locally without cloud API rate limits.'
                      : 'This council includes local models. If local shims are offline, switch to Cloud Deliberation from the top menu.'}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="chat-interface">
      {/* Header with title, tags, and export options */}
      {hasMessages && (
        <div className="chat-header">
          <div className="chat-header-left">
            <h2 className="chat-title">{conversation.title || 'Conversation'}</h2>
            {(conversation.council_name || activeCouncil?.name) && (
              <span className="chat-header-council-pill" title={isRoundTableConv ? 'Round-table multi-agent group' : 'Council assigned to this deliberation'}>
                {conversation.council_name || activeCouncil?.name}
              </span>
            )}
            {activeSeats.length > 0 && (
              <div className="chat-header-seats" title="Models answering in this conversation">
                {activeSeats.map((seat) => {
                  const { name, label, skill, full } = formatSeatLabel(seat, providerLabels);
                  return (
                    <span key={full} className="seat-chip" title={full}>
                      <span className="seat-chip-name">{name}</span>
                      {label && <span className="seat-chip-label">{label}</span>}
                      {skill && (
                        <button
                          type="button"
                          className="seat-chip-skill"
                          onClick={() => onInspectSkill?.(skill)}
                          title={`Skill: ${skill}`}
                        >
                          {skill}
                        </button>
                      )}
                    </span>
                  );
                })}
                {chairmanSeat && (
                  <span className="seat-chip chairman" title={`Chairman: ${chairmanSeat}`}>
                    <span className="seat-chip-role">Chair</span>
                    <span className="seat-chip-name">{formatSeatLabel(chairmanSeat, providerLabels).name}</span>
                    {formatSeatLabel(chairmanSeat, providerLabels).label && (
                      <span className="seat-chip-label">
                        {formatSeatLabel(chairmanSeat, providerLabels).label}
                      </span>
                    )}
                  </span>
                )}
              </div>
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
            {!isRoundTableConv && (
              <button
                type="button"
                className={`view-mode-toggle-btn ${feedView ? 'active' : ''}`}
                onClick={toggleFeedView}
                title={feedView ? 'Switch to classic stage tabs' : 'Switch to live deliberation feed'}
              >
                {feedView ? 'Live Feed' : 'Tabs'}
              </button>
            )}
            <button
              ref={tagButtonRef}
              className={`action-btn ${showTagEditor ? 'active' : ''}`}
              onClick={() => setShowTagEditor(!showTagEditor)}
              title="Edit tags"
              aria-expanded={showTagEditor}
            >
              Tags
            </button>
            {!isRoundTableConv && (
              <button
                className={`action-btn action-btn-adr ${copiedADR ? 'copied' : ''}`}
                onClick={handleCopyADR}
                title="Copy decision as Architecture Decision Record (ADR) to clipboard"
              >
                {copiedADR ? 'Copied!' : 'Copy ADR'}
              </button>
            )}
            <button
              className="action-btn"
              onClick={() => exportToMarkdown(conversation)}
              title="Export to full Markdown"
            >
              Export
            </button>
          </div>
        </div>
      )}

      {/* Tag Editor */}
      {hasMessages && showTagEditor && (
        <div ref={tagEditorRef} className="tag-editor-container">
          <TagEditor
            tags={conversation.tags || []}
            onTagsChange={onTagsChange}
            onClose={() => setShowTagEditor(false)}
          />
        </div>
      )}

      <div className="messages-container" ref={messagesContainerRef}>
        {conversation.messages.map((msg, index) => (
            <div key={index} className="message-group">
              {msg.role === 'user' ? (
                <div className="user-message">
                  <div className="message-content">
                    <div className="markdown-content">
                      <ReactMarkdown components={mentionMarkdownComponents}>
                        {linkifyUserMentions(
                          msg.content,
                          mentionSeats
                        )}
                      </ReactMarkdown>
                    </div>
                  </div>
                </div>
              ) : msg.isRoundTable ? (
                <div className="roundtable-responses-feed">
                  {(msg.roundtableResponses || []).map((r, rIdx) => (
                    <RoundTableMessage
                      key={rIdx}
                      model={r.model}
                      content={r.content}
                      cost={r.cost}
                      usage={r.usage}
                      onReplyToModel={handleReplyToModel}
                    />
                  ))}
                  {Object.entries(msg.roundtableStreaming || {}).map(([m, text]) => (
                    <RoundTableMessage
                      key={`stream-${m}`}
                      model={m}
                      content={text}
                      isStreaming
                      onReplyToModel={handleReplyToModel}
                    />
                  ))}
                </div>
              ) : msg.model && !msg.stage1 && !msg.stage3 ? (
                <RoundTableMessage
                  model={msg.model}
                  content={msg.content}
                  cost={msg.cost}
                  usage={msg.usage}
                  onReplyToModel={handleReplyToModel}
                />
              ) : (
                <div className="assistant-message">
                  <div className="assistant-header">
                    <div className="assistant-identity">
                      <span className="assistant-sparkle">✦</span>
                      <span className="assistant-name">
                        {msg.useDebate || msg.isDebating || msg.stage3?.debate_mode ? 'Council Debate' : 'LLM Council'}
                      </span>
                      {(conversation?.council_name || activeCouncil?.name) && (
                        <span className="assistant-council-tag">
                          {conversation.council_name || activeCouncil?.name}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Automated Context Ingestion Banner */}
                  {(msg.metadata?.ingestion || msg.ingestMeta) && (
                    <div className="ingestion-badge-banner">
                      <span className="ingestion-badge-label">Context Enriched:</span>
                      {(msg.metadata?.ingestion?.target_workspace || msg.ingestMeta?.target_workspace) && (
                        <span className="ingestion-chip workspace" title="Target local workspace dossier injected">
                          {msg.metadata?.ingestion?.target_workspace || msg.ingestMeta?.target_workspace}
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
                          {repoUrl.replace('https://github.com/', '')}
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
                              {isExpanded ? 'Hide Dossier' : 'View Candidates'}
                            </span>
                          </div>

                          {isExpanded && candidates.length > 0 && (
                            <div className="research-candidates-grid">
                              {candidates.map((c, cIdx) => (
                                <div key={cIdx} className={`candidate-card source-${c.source || 'web'}`}>
                                  <div className="candidate-card-header">
                                    <span className={`candidate-source-tag source-tag-${c.source || 'web'}`}>
                                      {c.source === 'github' && 'GitHub'}
                                      {c.source === 'local-skill' && 'Skill'}
                                      {c.source === 'package' && 'Package'}
                                      {c.source === 'web' && 'Tech Article'}
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
                      chairmanModel={msg.stage3?.model || msg.chairmanModel || ''}
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
                      {/* Stage 2 loading (feed view merges 1/2/3 into one log, but loading banners stay) */}
                      {msg.loading?.stage2 && (
                        <div className="stage-loading">
                          <div className="spinner"></div>
                          <span>Running Stage 2: Peer rankings...</span>
                        </div>
                      )}

                      {/* Stage 3 loading */}
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

                      {feedView && !(msg.useMultiChairman || msg.multiSyntheses?.length > 0 || msg.isConsensus ||
                        msg.useRefinement || msg.refinementIterations?.length > 0 || msg.useAdversary || msg.adversaryCritique ||
                        msg.useDecomposition || msg.isDecomposing || msg.decompositionComplete || msg.subQuestions?.length > 0) ? (
                        <LiveFeed
                          stage1={msg.stage1}
                          streamingResponses={msg.stage1Streaming}
                          stage2={msg.stage2}
                          labelToModel={msg.metadata?.label_to_model}
                          stage3={msg.stage3}
                          stage3StreamingResponse={msg.stage3Streaming}
                          stage3StreamingModel={msg.stage3StreamingModel}
                        />
                      ) : (
                        <>
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
                          {msg.stage2 && (
                            <Stage2
                              rankings={msg.stage2}
                              labelToModel={msg.metadata?.label_to_model}
                              aggregateRankings={msg.metadata?.aggregate_rankings}
                              useWeightedConsensus={msg.metadata?.use_weighted_consensus}
                              weightsInfo={msg.metadata?.weights_info}
                            />
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
                    </>
                  )}

                  {/* Cost Display */}
                  {msg.metadata?.costs && (
                    <CostDisplay costs={msg.metadata.costs} expanded={true} />
                  )}
                </div>
              )}
            </div>
          ))}

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

        {/* Interrupted or pending deliberation after page reload (Deliberation mode only) */}
        {!isRoundTableConv &&
          !activeDeliberating &&
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

        {/* Active Deliberation Banner with Live Status & Abort Control (Deliberation mode only) */}
        {!isRoundTableConv && activeDeliberating && (
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
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {(isRoundTableConv ||
        conversation.messages[conversation.messages.length - 1]?.role === 'assistant' ||
        activeDeliberating ||
        conversation.status === 'aborted') && (
        <div className="input-form-wrapper">
          <form className="input-form" onSubmit={handleSubmit}>
            {mentionQuery != null && mentionMatches.length > 0 && (
              <div className="mention-autocomplete">
                {mentionMatches.map((model, idx) => (
                  <button
                    key={model}
                    type="button"
                    className={`mention-autocomplete-item ${idx === mentionIndex ? 'selected' : ''}`}
                    onClick={() => insertMention(model)}
                    onMouseEnter={() => setMentionIndex(idx)}
                  >
                    @{model === 'all' ? 'all' : shortModelName(model)}
                  </button>
                ))}
              </div>
            )}
            {queuedMessage && (
              <div className="queued-message">
                <span className="queued-label">Queued</span>
                <span className="queued-text">{queuedMessage}</span>
                <button type="button" className="queued-cancel" onClick={() => setQueued(null)} title="Cancel queued message">
                  ×
                </button>
              </div>
            )}
            <div className="input-inner">
              <textarea
                ref={messageInputRef}
                className="message-input"
                placeholder={
                  isRoundTableConv
                    ? isLoading
                      ? 'Replies are streaming — Enter queues your message...'
                      : 'Write a message or mention a model (@all, @qwen)...'
                    : activeDeliberating
                    ? 'Council deliberation in progress...'
                    : 'Reply or ask a follow-up... (@ to mention a panelist, Enter to send)'
                }
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                disabled={!isRoundTableConv && activeDeliberating}
                rows={2}
              />
              {isRoundTableConv ? (
                isLoading ? (
                  <button
                    type="button"
                    className="input-icon-btn stop"
                    onClick={() => {
                      setQueued(null);
                      if (onAbortDeliberation) onAbortDeliberation(conversation.id);
                    }}
                    title="Stop"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                      <rect x="5" y="5" width="14" height="14" rx="2" />
                    </svg>
                  </button>
                ) : (
                  <button
                    type="submit"
                    className="input-icon-btn send"
                    disabled={!input.trim()}
                    title="Send"
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="12" y1="19" x2="12" y2="5"></line>
                      <polyline points="6 11 12 5 18 11"></polyline>
                    </svg>
                  </button>
                )
              ) : activeDeliberating ? (
                <button
                  type="button"
                  className="input-icon-btn stop"
                  onClick={() => onAbortDeliberation && onAbortDeliberation(conversation.id)}
                  title="Stop deliberation"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                    <rect x="5" y="5" width="14" height="14" rx="2" />
                  </svg>
                </button>
              ) : (
                <button
                  type="submit"
                  className="input-icon-btn send"
                  disabled={!input.trim()}
                  title="Send"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="12" y1="19" x2="12" y2="5"></line>
                    <polyline points="6 11 12 5 18 11"></polyline>
                  </svg>
                </button>
              )}
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
