import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { colorForModel, shortModelName, initialsFor, mentionMarkdownComponents } from './mentionUtils.jsx';
import { getAgentProfile } from '../agentProfiles';
import './RoundTableMessage.css';

export default function RoundTableMessage({
  model,
  content,
  isStreaming = false,
  cost,
  usage,
  onReplyToModel,
}) {
  const [copied, setCopied] = useState(false);
  const profile = getAgentProfile(model);
  const isError = Boolean(cost?.isError || isStreaming === false && content?.startsWith('⚠️'));
  const color = isError ? '#ef4444' : (profile.color || colorForModel(model));
  const shortName = profile.displayName || shortModelName(model);
  const isFree = model?.includes(':free');
  const isLocal = model?.startsWith('local/');

  const displayCost = typeof cost === 'number'
    ? cost
    : typeof cost?.total_cost === 'number'
    ? cost.total_cost
    : null;

  const handleCopy = () => {
    if (!content) return;
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`roundtable-bubble-wrap ${isStreaming ? 'streaming' : ''} ${isError ? 'error-bubble' : ''}`}>
      <div className="roundtable-avatar" style={{ '--avatar-color': color }}>
        {profile.avatarUrl ? (
          <img src={profile.avatarUrl} alt={shortName} className="roundtable-avatar-img" />
        ) : (
          profile.initials || initialsFor(model)
        )}
      </div>

      <div className="roundtable-bubble-main">
        <div className="roundtable-bubble-header">
          <div className="roundtable-header-left">
            <span className="roundtable-model-name" style={{ color: color }}>
              {shortName}
            </span>

            {isLocal && (
              <span className="roundtable-tier-badge local" title="Runs locally via vLLM/Ollama">
                Local
              </span>
            )}
            {isFree && !isLocal && (
              <span className="roundtable-tier-badge free" title="Zero cost OpenRouter free tier">
                Free
              </span>
            )}

            {isStreaming && (
              <span className="roundtable-streaming-indicator">
                <span className="roundtable-pulse-dot"></span> Generating...
              </span>
            )}
          </div>

          <div className="roundtable-header-actions">
            {onReplyToModel && !isStreaming && (
              <button
                type="button"
                className="roundtable-reply-btn"
                onClick={() => onReplyToModel(model)}
                title={`Reply directly to @${shortName}`}
              >
                @{shortName}
              </button>
            )}
            {content && !isStreaming && (
              <button
                type="button"
                className={`roundtable-copy-btn ${copied ? 'copied' : ''}`}
                onClick={handleCopy}
                title="Copy message"
              >
                {copied ? 'Copied' : 'Copy'}
              </button>
            )}
          </div>
        </div>

        <div className="roundtable-bubble-content markdown-content">
          {content ? (
            <ReactMarkdown components={mentionMarkdownComponents}>
              {content}
            </ReactMarkdown>
          ) : isStreaming ? (
            <span className="roundtable-typing-dots">
              <span>●</span> <span>●</span> <span>●</span>
            </span>
          ) : null}
          {isStreaming && content && <span className="roundtable-cursor"></span>}
        </div>

        {(displayCost != null || (usage?.total_tokens ?? 0) > 0) && !isStreaming && (
          <div className="roundtable-bubble-footer">
            {Boolean(usage?.total_tokens) && (
              <span className="roundtable-stat-item">
                {usage.total_tokens} tokens
              </span>
            )}
            {displayCost != null && (
              <span className="roundtable-stat-item cost">
                ${displayCost.toFixed(4)}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
