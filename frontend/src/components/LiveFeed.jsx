import ReactMarkdown from 'react-markdown';
import { ConfidenceBadge } from './ConfidenceDisplay';
import './LiveFeed.css';

// Discord-inspired continuous log: Stage 1 panelists, Stage 2 peer critiques
// (with @mentions linked back to the model they're referencing), and the
// chairman's Stage 3 verdict, all in one chronological feed instead of
// separate tabs — built for "watching the council talk" rather than
// clicking through evidence one model at a time.

const USERNAME_PALETTE = [
  '#f27878', '#f2a65a', '#e0c341', '#8bc98a',
  '#5fc7c7', '#6fa8dc', '#a892e0', '#e08ad0',
];

function hashString(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 31 + str.charCodeAt(i)) >>> 0;
  }
  return hash;
}

export function colorForModel(modelId) {
  if (!modelId) return USERNAME_PALETTE[0];
  return USERNAME_PALETTE[hashString(modelId) % USERNAME_PALETTE.length];
}

function shortModelName(modelId) {
  if (!modelId) return 'Unknown';
  const [baseModel] = modelId.split('@');
  return (baseModel.split('/')[1] || baseModel).replace(':free', '');
}

function initialsFor(modelId) {
  const name = shortModelName(modelId);
  const parts = name.split(/[-_.\s]/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

// Turns anonymized "Response A" style labels into markdown mention links
// (`[@Name](mention:modelId)`) so ReactMarkdown's own parser handles the
// splitting — safer than hand-rolling regex-based text splitting.
function toMentionMarkdown(text, labelToModel) {
  if (!labelToModel || !text) return text || '';
  let result = text;
  Object.entries(labelToModel).forEach(([label, model]) => {
    const name = shortModelName(model);
    result = result.split(label).join(`[@${name}](mention:${encodeURIComponent(model)})`);
  });
  return result;
}

const mentionMarkdownComponents = {
  a({ href, children }) {
    if (href?.startsWith('mention:')) {
      const model = decodeURIComponent(href.slice('mention:'.length));
      return (
        <span className="feed-mention" style={{ '--mention-color': colorForModel(model) }}>
          {children}
        </span>
      );
    }
    return (
      <a href={href} target="_blank" rel="noreferrer">
        {children}
      </a>
    );
  },
};

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
