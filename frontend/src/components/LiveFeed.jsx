import ReactMarkdown from 'react-markdown';
import { ConfidenceBadge } from './ConfidenceDisplay';
import { colorForModel, shortModelName, initialsFor, toMentionMarkdown, mentionMarkdownComponents } from './mentionUtils.jsx';
import './LiveFeed.css';

// Discord-inspired continuous log: Stage 1 panelists, Stage 2 peer critiques
// (with @mentions linked back to the model they're referencing), and the
// chairman's Stage 3 verdict, all in one chronological feed instead of
// separate tabs — built for "watching the council talk" rather than
// clicking through evidence one model at a time.

function FeedRow({ modelId, roleTag, roleTagClass, content, confidence, pinned, isStreaming }) {
  const color = pinned ? 'var(--accent-primary)' : colorForModel(modelId);
  return (
    <div className={`feed-row ${pinned ? 'pinned' : ''}`}>
      <div className="feed-avatar" style={{ '--avatar-color': color }}>
        {initialsFor(modelId)}
      </div>
      <div className="feed-body">
        <div className="feed-meta">
          <span className="feed-username" style={{ color }}>
            {shortModelName(modelId)}
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

/**
 * @param {Array} stage1 - [{model, response, confidence, isStreaming?}]
 * @param {Object} streamingResponses - model -> partial text (Stage 1 still streaming)
 * @param {Array} stage2 - [{model, ranking}]
 * @param {Object} labelToModel - anonymized label -> model, for @mention linking
 * @param {Object} stage3 - {model, response}
 * @param {string} stage3StreamingResponse - partial chairman text while streaming
 * @param {string} stage3StreamingModel
 */
export default function LiveFeed({
  stage1,
  streamingResponses,
  stage2,
  labelToModel,
  stage3,
  stage3StreamingResponse,
  stage3StreamingModel,
}) {
  const streamingOnly = Object.keys(streamingResponses || {}).filter(
    (model) => !(stage1 || []).some((r) => r.model === model)
  );

  return (
    <div className="live-feed">
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
      {streamingOnly.map((model) => (
        <FeedRow
          key={`s1-stream-${model}`}
          modelId={model}
          roleTag="PANELIST"
          content={streamingResponses[model]}
          isStreaming
        />
      ))}

      {(stage2 || []).map((rk) => (
        <FeedRow
          key={`s2-${rk.model}`}
          modelId={rk.model}
          roleTag="EVALUATING"
          roleTagClass="evaluating"
          content={toMentionMarkdown(rk.ranking, labelToModel)}
        />
      ))}

      {(stage3?.response || stage3StreamingResponse) && (
        <FeedRow
          modelId={stage3?.model || stage3StreamingModel}
          roleTag="CHAIRMAN — FINAL VERDICT"
          roleTagClass="chairman"
          content={stage3?.response || stage3StreamingResponse}
          isStreaming={!stage3?.response && !!stage3StreamingResponse}
          pinned
        />
      )}
    </div>
  );
}
