import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { ConfidenceBadge } from './ConfidenceDisplay';
import { colorForModel, shortModelName, initialsFor, toMentionMarkdown, mentionMarkdownComponents } from './mentionUtils.jsx';
import { getAgentProfile } from '../agentProfiles';
import './LiveFeed.css';

function FeedRow({ modelId, roleTag, roleTagClass, content, confidence, isStreaming }) {
  const profile = getAgentProfile(modelId);
  const color = profile.color || colorForModel(modelId);
  const displayName = profile.displayName || shortModelName(modelId);

  return (
    <div className="feed-row">
      <div className="feed-avatar" style={{ '--avatar-color': color }}>
        {profile.avatarUrl ? (
          <img src={profile.avatarUrl} alt={displayName} className="feed-avatar-img" />
        ) : (
          profile.initials || initialsFor(modelId)
        )}
      </div>
      <div className="feed-body">
        <div className="feed-meta">
          <span className="feed-username" style={{ color }}>
            {displayName}
          </span>
          {roleTag && <span className={`feed-role-tag ${roleTagClass || ''}`}>{roleTag}</span>}
          {confidence != null && <ConfidenceBadge confidence={confidence} />}
          {isStreaming && <span className="feed-streaming-dot" title="Generating…" />}
        </div>
        <div className="feed-content markdown-content">
          <ReactMarkdown components={mentionMarkdownComponents}>{content || ''}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

export default function LiveFeed({
  stage1,
  streamingResponses,
  stage2,
  labelToModel,
  stage3,
  stage3StreamingResponse,
  stage3StreamingModel,
}) {
  const hasStage3 = Boolean(stage3?.response || stage3StreamingResponse);
  const isStage3Streaming = !stage3?.response && Boolean(stage3StreamingResponse);

  // Auto-expand deliberation while deliberation is active, collapse once final verdict arrives
  const [deliberationExpanded, setDeliberationExpanded] = useState(() => !hasStage3);
  const [copiedVerdict, setCopiedVerdict] = useState(false);

  const streamingOnly = Object.keys(streamingResponses || {}).filter(
    (model) => !(stage1 || []).some((r) => r.model === model)
  );

  const totalDeliberationCount = (stage1?.length || 0) + streamingOnly.length + (stage2?.length || 0);
  const isDeliberating = streamingOnly.length > 0 || (stage1 || []).some((r) => r.isStreaming);

  const verdictContent = stage3?.response || stage3StreamingResponse || '';
  const verdictModel = stage3?.model || stage3StreamingModel || 'Chairman';

  const handleCopyVerdict = () => {
    if (!verdictContent) return;
    navigator.clipboard.writeText(verdictContent);
    setCopiedVerdict(true);
    setTimeout(() => setCopiedVerdict(false), 2000);
  };

  return (
    <div className="live-feed">
      {/* Intermediate Deliberation Phase (Stage 1 Panelists & Stage 2 Peer Reviews) */}
      {totalDeliberationCount > 0 && (
        <div className="feed-deliberation-container">
          <button
            type="button"
            className={`feed-deliberation-toggle ${deliberationExpanded ? 'expanded' : ''}`}
            onClick={() => setDeliberationExpanded(!deliberationExpanded)}
            title="Click to toggle intermediate council deliberation details"
          >
            <div className="feed-deliberation-title">
              <span className="feed-deliberation-label">Council Deliberation</span>
              <span className="feed-deliberation-count-chip">
                {totalDeliberationCount} contributions
              </span>
              {isDeliberating && (
                <span className="feed-deliberation-active-pill">
                  <span className="pulse-dot"></span> Deliberating
                </span>
              )}
            </div>
            <span className="feed-deliberation-action">
              {deliberationExpanded ? 'Collapse ▲' : 'Show Details ▼'}
            </span>
          </button>

          {deliberationExpanded && (
            <div className="feed-deliberation-body">
              {/* Stage 1 Completed Panelists */}
              {(stage1 || []).map((r) => (
                <FeedRow
                  key={`s1-${r.model}`}
                  modelId={r.model}
                  roleTag="PANELIST"
                  content={r.response}
                  confidence={r.confidence}
                  isStreaming={r.isStreaming}
                />
              ))}

              {/* Stage 1 Streaming Only */}
              {streamingOnly.map((model) => (
                <FeedRow
                  key={`s1-stream-${model}`}
                  modelId={model}
                  roleTag="PANELIST"
                  content={streamingResponses[model]}
                  isStreaming
                />
              ))}

              {/* Stage 2 Peer Critiques */}
              {(stage2 || []).map((rk) => (
                <FeedRow
                  key={`s2-${rk.model}`}
                  modelId={rk.model}
                  roleTag="EVALUATING"
                  roleTagClass="evaluating"
                  content={toMentionMarkdown(rk.ranking, labelToModel)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Hero: Final Verdict Card */}
      {hasStage3 && (
        <div className={`feed-verdict-card ${isStage3Streaming ? 'streaming' : ''}`}>
          <div className="verdict-header">
            <div className="verdict-title-wrap">
              <span className="verdict-sparkle-icon">✦</span>
              <span className="verdict-heading">Council Decision</span>
              <span className="verdict-model-chip">
                {shortModelName(verdictModel)}
                <span className="verdict-chairman-badge">Chairman</span>
              </span>
              {isStage3Streaming && (
                <span className="verdict-streaming-chip">
                  <span className="pulse-dot"></span> Synthesizing
                </span>
              )}
            </div>

            {verdictContent && !isStage3Streaming && (
              <button
                type="button"
                className={`verdict-copy-btn ${copiedVerdict ? 'copied' : ''}`}
                onClick={handleCopyVerdict}
                title="Copy final answer"
              >
                {copiedVerdict ? '✓ Copied' : 'Copy'}
              </button>
            )}
          </div>

          <div className="verdict-content markdown-content">
            <ReactMarkdown components={mentionMarkdownComponents}>{verdictContent}</ReactMarkdown>
            {isStage3Streaming && <span className="verdict-cursor"></span>}
          </div>
        </div>
      )}
    </div>
  );
}
